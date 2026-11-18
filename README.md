# cbBTC Trend Bot

[![make.fun bounty](https://make.fun/bounty/btc-race-24h-20261118-1444/badge.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)

A Python trading bot for make.fun's **"Race a BTC trading bot live for 24 hours"** bounty
(`btc-race-24h-20261118-1444`). It trades Coinbase Wrapped BTC (cbBTC) against USDC on
1-minute bars, starting with $1,000 of paper money, long only.

## Strategy

Ride slow multi-hour trends and sit out the chop:

1. **Enter** — go all-in long only when the fast EMA (75 one-minute closes) crosses
   above the slow EMA (180 closes): the trend has turned up.
2. **Exit** — sell everything on whichever comes first: the fast EMA crosses back
   below the slow one, a hard stop 1% below the entry cost, or a trailing stop
   0.8% below the highest close since entry (locks in the rally).
3. **Cooldown** — after any exit, wait 300 bars before the next entry, so a
   sideways market cannot whipsaw the bot into repeated round trips.
4. **Drawdown guard** — if equity falls 12% below its peak, flatten and pause
   120 bars.

Few parameters, all round numbers, chosen for robustness rather than a
knife-edge fit: neighbouring settings (fast 60–90, slow 120–190, trailing
stop 80–100 bps, cooldown 240–300 bars) all clear the dev gate on the
frozen 24-hour dev window.

## Dev-window backtest

On the frozen 24h dev window (1,440 one-minute bars, BTC −2.8% over the
window — buy-and-hold loses ~$28):

- **Net PnL: +$6.96** (after all fees, slippage and price impact)
- Trades: 1 round trip (buy fills bar 378 @ ~$63,991, sell fills bar 602 @ ~$64,666)
- Max drawdown: 0.97%
- Final equity: $1,006.96

The dev gate needs net PnL above $0; this clears it.

## How to run

```sh
python3 -P -s main.py
```

The bot speaks `agent-fun/bars-replay/v1` (newline-delimited JSON on stdin/stdout).
Standard library only; `vendor/makefun_bars.py` is a byte-identical copy of the
kit's Python shim. No network, no wall clock, no files outside the repo, no
randomness — the same bars always produce the same orders.

## Files

- `main.py` — the bot
- `vendor/makefun_bars.py` — the kit's protocol shim (byte-identical copy)
- `LICENSE` — MIT
- `.makefun/owner.json` — claim file for the entry
