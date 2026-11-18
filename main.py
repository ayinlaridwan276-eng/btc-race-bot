"""cbBTC trend bot for make.fun's "Race a BTC trading bot live for 24 hours".

Strategy, in brief: ride slow multi-hour trends and sit out the chop.
  - Enter long (all cash) only when the fast EMA (75 one-minute closes)
    crosses above the slow EMA (180 closes): the trend has turned up.
  - Exit on whichever comes first: the fast EMA crosses back below the
    slow one, a hard stop 1% below the entry cost, or a trailing stop
    0.8% below the highest close since entry (locks in the rally).
  - After any exit, wait 300 bars before the next entry, so a sideways
    market cannot whipsaw the bot into repeated round trips.
  - A drawdown guard flattens the position and pauses 120 bars if equity
    falls 12% below its peak.

Everything is integer arithmetic on the bar closes (price units, scale 5),
so the same bars always produce the same orders: no clock, no network,
no files outside this repository, no randomness. Standard library only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

FAST_N = 75            # fast EMA length, in one-minute bars
SLOW_N = 180           # slow EMA length, in one-minute bars
STOP_BPS = 100         # hard stop: exit if position value falls 1% below cost
TRAIL_BPS = 80         # trailing stop: exit 0.8% below the highest close since entry
COOLDOWN_BARS = 300    # bars to wait after any exit before a new entry
DD_GUARD_BPS = 1200    # flatten + pause if equity falls 12% below its peak
DD_PAUSE_BARS = 120    # pause after a drawdown-guard exit
MAX_SLIPPAGE_BPS = 10_000  # wide open: fills are at the next open, a few bps away


class TrendBot:
    """One stateful bot; all state is plain ints, reset per run."""

    def __init__(self):
        self.ema_fast = None
        self.ema_slow = None
        self.prev_diff_bps = 0
        self.cross_up = False
        self.cross_dn = False
        self.high_since_entry = 0
        self.last_exit_seq = -10 ** 9
        self.pause_until_seq = -1
        self.peak_equity = 0

    def on_batch(self, state, batch):
        close = self._update(state)
        if close is None:
            return []
        if state.equity > self.peak_equity:
            self.peak_equity = state.equity
        if state.warming_up:
            # Build history only: orders decided on warm-up bars are rejected.
            return []
        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            return self._maybe_exit(state, holding, close)
        return self._maybe_enter(state, close)

    def _update(self, state):
        """Fold the latest close into both EMAs; record any cross this bar."""
        close = state.close(SYMBOL)
        if close is None:
            return None
        if self.ema_fast is None:
            self.ema_fast = close
            self.ema_slow = close
            self.prev_diff_bps = 0
            self.cross_up = False
            self.cross_dn = False
            return close
        self.ema_fast += (close - self.ema_fast) * 2 // (FAST_N + 1)
        self.ema_slow += (close - self.ema_slow) * 2 // (SLOW_N + 1)
        diff_bps = (self.ema_fast - self.ema_slow) * 10_000 // close
        self.cross_up = self.prev_diff_bps <= 0 < diff_bps
        self.cross_dn = self.prev_diff_bps >= 0 > diff_bps
        self.prev_diff_bps = diff_bps
        return close

    def _maybe_exit(self, state, holding, close):
        if close > self.high_since_entry:
            self.high_since_entry = close
        value = state.value(SYMBOL, holding.qty)
        sell = False
        pause = False
        if value * 10_000 < holding.cost * (10_000 - STOP_BPS):
            sell = True  # hard stop below entry cost
        elif close * 10_000 < self.high_since_entry * (10_000 - TRAIL_BPS):
            sell = True  # trailing stop below the run's high
        elif self.cross_dn:
            sell = True  # trend turned down
        elif (self.peak_equity - state.equity) * 10_000 // self.peak_equity >= DD_GUARD_BPS:
            sell = True  # drawdown guard
            pause = True
        if not sell:
            return []
        self.last_exit_seq = state.seq
        if pause:
            self.pause_until_seq = state.seq + DD_PAUSE_BARS
        return [{"side": "sell", "symbol": SYMBOL, "qty": holding.qty,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]

    def _maybe_enter(self, state, close):
        if state.seq < self.pause_until_seq:
            return []
        if state.seq - self.last_exit_seq < COOLDOWN_BARS:
            return []
        if not self.cross_up:
            return []
        min_notional = int(state.hello["fees"]["min_notional_quote_units"])
        notional = state.cash
        room = state.weight_room(SYMBOL)
        if room < notional:
            notional = room
        if notional < min_notional:
            return []
        self.high_since_entry = close
        return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": notional,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(TrendBot().on_batch)
