# XAUUSD Technical Analysis — SMC, ICT, and Moving Averages

Analyze the GOLD (XAUUSD) chart with smart-money structure, ICT dealing ranges, and moving averages. The aim is a high-probability trade, or an explicit decision to stay flat when the location is wrong.

## Current read

**28 October 2026, 18:03 Asia/Dhaka. Trade the spot chart. Spot mid 4,045. Stay flat until a spot level breaks.**

Structure is taken from December COMEX gold, which is about **$13 above spot** today. Every order below is the spot price; the futures twin is in [ANALYSIS.md](ANALYSIS.md).

- Half-size spot sell at **4,065–4,073** only after a 15-minute close back under 4,055 (stop 4,081, target 4,029), or after a 15-minute close under **4,017**.
- Main spot sell at **4,119–4,148** if the midnight spike reaches it and rejects. A 1-hour close above **4,159** cancels it.
- Main spot buy only after a sweep under **3,976** that closes back above **3,987**.

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
