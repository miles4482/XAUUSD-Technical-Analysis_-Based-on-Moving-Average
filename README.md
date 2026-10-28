# XAUUSD Technical Analysis — SMC, ICT, and Moving Averages

Analyze the GOLD (XAUUSD) chart with smart-money structure, ICT dealing ranges, and moving averages. The aim is a high-probability trade, or an explicit decision to stay flat when the location is wrong.

## Current read

**28 October 2026, 17:41 Asia/Dhaka. Futures last 4,060.90. Stay flat until a level breaks.**

Daily structure is bearish (lower high, lower low, price under the falling 20/50/100/200 EMAs). Price is only about 31% back up the active downswing, so it is still in discount. The high-probability idea is a **short at 4,132–4,161** if price reaches that supply after the Fed decision and a 15-minute or 1-hour bearish displacement prints there. Invalidation is a 1-hour close above 4,172. Downside liquidity is 3,989, then 3,955–3,976.

From 17:41 the session plan is: nothing until New York; a half-size sell only on a rejection of 4,078–4,086 or a 15-minute close under 4,029.90; flat again from 21:00; the real sell is 4,132–4,161 and the real buy is a sweep of 3,989 that reclaims 4,000, both around the midnight Fed statement. Details are in [ANALYSIS.md](ANALYSIS.md).

## Reproduce the levels

```bash
python3 analyze.py
```

That reads the bundled COMEX gold candles in `data/` (`GC=F`, the proxy used for this XAUUSD read). Refresh first with:

```bash
python3 analyze.py --live
```

Spot can differ from futures by a few dollars. Use the zones, and move them by the live futures-spot basis if you execute on XAUUSD itself.

This is educational chart work, not financial advice.
