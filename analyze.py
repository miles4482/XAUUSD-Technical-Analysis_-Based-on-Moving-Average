#!/usr/bin/env python3
"""SMC, ICT, and moving-average scan for GOLD.

The bundled candles are COMEX gold futures (GC=F), the liquid proxy for
spot XAUUSD. Levels are zones: spot can print a few dollars away from the
futures price. This is a structure tool, not an order-placement system and
not financial advice.

    python3 analyze.py           # read data/gc_*.json
    python3 analyze.py --live    # refresh GC=F from Yahoo Finance, then scan
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
INTERVALS = {
    "daily": ("1d", "1y", DATA / "gc_daily.json"),
    "hourly": ("1h", "1mo", DATA / "gc_hourly.json"),
    "weekly": ("1wk", "5y", DATA / "gc_weekly.json"),
}


def fetch(interval: str, range_: str) -> dict:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        f"?interval={interval}&range={range_}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def load_rows(payload: dict, drop_partial_hour: bool = False) -> list[dict]:
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    rows = []
    for i, ts in enumerate(result["timestamp"]):
        o, h, l, c = (quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i])
        if None in (o, h, l, c):
            continue
        dt = datetime.fromtimestamp(ts, timezone.utc)
        if drop_partial_hour and dt.minute != 0:
            continue
        rows.append(
            {
                "dt": dt,
                "o": float(o),
                "h": float(h),
                "l": float(l),
                "c": float(c),
                "v": float(quote["volume"][i] or 0),
            }
        )
    return rows


def ema(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < length:
        return out
    k = 2 / (length + 1)
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    for i in range(length, len(values)):
        seed = values[i] * k + seed * (1 - k)
        out[i] = seed
    return out


def rsi(values: list[float], length: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= length:
        return out
    gains, losses = [], []
    for i in range(1, length + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length
    out[length] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(length + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (length - 1) + max(change, 0.0)) / length
        avg_loss = (avg_loss * (length - 1) + max(-change, 0.0)) / length
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def atr(rows: list[dict], length: int = 14) -> list[float | None]:
    true_ranges = []
    for i, row in enumerate(rows):
        if i == 0:
            true_ranges.append(row["h"] - row["l"])
        else:
            prev = rows[i - 1]["c"]
            true_ranges.append(
                max(row["h"] - row["l"], abs(row["h"] - prev), abs(row["l"] - prev))
            )
    out: list[float | None] = [None] * len(rows)
    if len(true_ranges) < length:
        return out
    seed = sum(true_ranges[:length]) / length
    out[length - 1] = seed
    for i in range(length, len(true_ranges)):
        seed = (seed * (length - 1) + true_ranges[i]) / length
        out[i] = seed
    return out


def swings(rows: list[dict], wing: int = 2) -> tuple[list[int], list[int]]:
    highs, lows = [], []
    for i in range(wing, len(rows) - wing):
        high, low = rows[i]["h"], rows[i]["l"]
        if all(high > rows[j]["h"] for j in range(i - wing, i)) and all(
            high >= rows[j]["h"] for j in range(i + 1, i + wing + 1)
        ):
            highs.append(i)
        if all(low < rows[j]["l"] for j in range(i - wing, i)) and all(
            low <= rows[j]["l"] for j in range(i + 1, i + wing + 1)
        ):
            lows.append(i)
    return highs, lows


def open_fvgs(rows: list[dict], min_size: float) -> list[dict]:
    gaps = []
    for i in range(2, len(rows)):
        if rows[i]["l"] > rows[i - 2]["h"]:
            size = rows[i]["l"] - rows[i - 2]["h"]
            if size >= min_size:
                gaps.append(
                    {
                        "i": i,
                        "side": "bull",
                        "bot": rows[i - 2]["h"],
                        "top": rows[i]["l"],
                        "dt": rows[i]["dt"],
                        "size": size,
                    }
                )
        elif rows[i]["h"] < rows[i - 2]["l"]:
            size = rows[i - 2]["l"] - rows[i]["h"]
            if size >= min_size:
                gaps.append(
                    {
                        "i": i,
                        "side": "bear",
                        "bot": rows[i]["h"],
                        "top": rows[i - 2]["l"],
                        "dt": rows[i]["dt"],
                        "size": size,
                    }
                )
    alive = []
    for gap in gaps:
        filled = False
        touched = False
        for row in rows[gap["i"] + 1 :]:
            if gap["side"] == "bull" and row["l"] <= gap["top"]:
                touched = True
                if row["l"] <= gap["bot"]:
                    filled = True
                    break
            if gap["side"] == "bear" and row["h"] >= gap["bot"]:
                touched = True
                if row["h"] >= gap["top"]:
                    filled = True
                    break
        if not filled:
            gap["touched"] = touched
            gap["ce"] = (gap["bot"] + gap["top"]) / 2
            alive.append(gap)
    return alive


def resample_h4(hourly: list[dict]) -> list[dict]:
    buckets: dict[datetime, dict] = {}
    for row in hourly:
        key = row["dt"].replace(minute=0, second=0, microsecond=0)
        key = key.replace(hour=(key.hour // 4) * 4)
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {**row, "dt": key}
        else:
            bucket["h"] = max(bucket["h"], row["h"])
            bucket["l"] = min(bucket["l"], row["l"])
            bucket["c"] = row["c"]
            bucket["v"] += row["v"]
    return [buckets[k] for k in sorted(buckets)]


def money(value: float) -> str:
    return f"{value:,.2f}"


def bearish_context(daily: list[dict]) -> dict:
    """Active bearish dealing range: last swing high before the latest swing low."""
    highs, lows = swings(daily, 2)
    if len(highs) < 2 or len(lows) < 2:
        raise SystemExit("Not enough daily swings to map a dealing range.")
    low_i = lows[-1]
    prior_highs = [i for i in highs if i < low_i]
    if not prior_highs:
        raise SystemExit("No swing high sits before the latest swing low.")
    high_i = prior_highs[-1]
    prev_low = next(i for i in reversed(lows) if i < low_i)
    prev_high = prior_highs[-2] if len(prior_highs) > 1 else prior_highs[-1]
    hi, lo = daily[high_i]["h"], daily[low_i]["l"]
    rng = hi - lo
    # Displacement candle: first daily bar after the swing high that breaks
    # the previous swing low, which is the break of structure.
    break_i = None
    for i in range(high_i + 1, len(daily)):
        if daily[i]["l"] < daily[prev_low]["l"]:
            break_i = i
            break
    ob = None
    if break_i is not None:
        for k in range(break_i - 1, high_i, -1):
            if daily[k]["c"] > daily[k]["o"]:
                ob = daily[k]
                break
    return {
        "high_i": high_i,
        "low_i": low_i,
        "hi": hi,
        "lo": lo,
        "rng": rng,
        "eq": (hi + lo) / 2,
        "ote_lo": lo + 0.62 * rng,
        "ote_mid": lo + 0.705 * rng,
        "ote_hi": lo + 0.79 * rng,
        "fib382": lo + 0.382 * rng,
        "lower_high": daily[high_i]["h"] < daily[prev_high]["h"],
        "lower_low": daily[low_i]["l"] < daily[prev_low]["l"],
        "prev_high": daily[prev_high]["h"],
        "prev_low": daily[prev_low]["l"],
        "ob": ob,
        "break_dt": daily[break_i]["dt"] if break_i is not None else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="XAUUSD SMC / ICT / MA scan")
    parser.add_argument("--live", action="store_true", help="refresh GC=F candles first")
    args = parser.parse_args()

    if args.live:
        DATA.mkdir(exist_ok=True)
        for name, (interval, range_, path) in INTERVALS.items():
            payload = fetch(interval, range_)
            path.write_text(json.dumps(payload))
            print(f"saved {name} -> {path.name}")

    daily = load_rows(json.loads(INTERVALS["daily"][2].read_text()))
    hourly = load_rows(json.loads(INTERVALS["hourly"][2].read_text()), drop_partial_hour=True)
    weekly = load_rows(json.loads(INTERVALS["weekly"][2].read_text()))
    h4 = resample_h4(hourly)

    last = daily[-1]
    price = last["c"]
    d_close = [r["c"] for r in daily]
    h_close = [r["c"] for r in h4]
    w_close = [r["c"] for r in weekly]
    d_ema = {n: ema(d_close, n)[-1] for n in (20, 50, 100, 200)}
    h_ema = {n: ema(h_close, n)[-1] for n in (20, 50, 100)}
    w_ema = {n: ema(w_close, n)[-1] for n in (20, 50)}
    d_rsi = rsi(d_close)[-1]
    h_rsi = rsi(h_close)[-1]
    ctx = bearish_context(daily)
    location = (price - ctx["lo"]) / ctx["rng"]

    print("XAUUSD via GC=F  |  SMC + ICT + moving averages")
    print(f"As of {last['dt'].strftime('%Y-%m-%d %H:%M')} UTC   last {money(price)}")
    print(f"Session bar  H {money(last['h'])}  L {money(last['l'])}")
    print()
    print("Moving averages (daily close vs EMA)")
    for n in (20, 50, 100, 200):
        value = d_ema[n]
        side = "below" if price < value else "above"
        print(f"  EMA{n:<3} {money(value)}   price {side}")
    stacked = d_ema[20] < d_ema[50] < d_ema[100] < d_ema[200]
    print(f"  Stack EMA20 < EMA50 < EMA100 < EMA200: {'yes' if stacked else 'no'}")
    print(f"  Daily RSI(14) {d_rsi:.1f}")
    print(f"  4H EMA20 {money(h_ema[20])}  EMA50 {money(h_ema[50])}  EMA100 {money(h_ema[100])}  RSI {h_rsi:.1f}")
    print(f"  Weekly EMA20 {money(w_ema[20])}  EMA50 {money(w_ema[50])}")
    print()
    print("Daily structure")
    print(
        f"  Swing high {ctx['high_i'] and daily[ctx['high_i']]['dt'].date()} "
        f"{money(ctx['hi'])}   prior high {money(ctx['prev_high'])} "
        f"({'LH' if ctx['lower_high'] else 'HH'})"
    )
    print(
        f"  Swing low  {daily[ctx['low_i']]['dt'].date()} {money(ctx['lo'])}   "
        f"prior low {money(ctx['prev_low'])} ({'LL' if ctx['lower_low'] else 'HL'})"
    )
    if ctx["break_dt"]:
        print(f"  Break of the prior swing low: {ctx['break_dt'].date()}")
    if ctx["ob"]:
        ob = ctx["ob"]
        print(
            f"  Bearish order block {ob['dt'].date()}  body {money(min(ob['o'], ob['c']))}"
            f"–{money(max(ob['o'], ob['c']))}  wick high {money(ob['h'])}"
        )
    print()
    print("Dealing range of the active leg (sell premium, not discount)")
    print(f"  {money(ctx['lo'])} → {money(ctx['hi'])}")
    print(f"  Equilibrium {money(ctx['eq'])}")
    print(f"  0.382 retrace {money(ctx['fib382'])}")
    print(
        f"  OTE 0.62–0.79 {money(ctx['ote_lo'])} – {money(ctx['ote_hi'])}"
        f"   midpoint 0.705 {money(ctx['ote_mid'])}"
    )
    print(f"  Price location {location * 100:.1f}% of the range (0 = low, 100 = high)")
    print()
    print("Open imbalances near price")
    for label, rows, minimum in (("Daily", daily, 12), ("4H", h4, 6)):
        for gap in open_fvgs(rows, minimum):
            if abs(((gap["bot"] + gap["top"]) / 2) - price) > 200:
                continue
            state = "touched" if gap["touched"] else "untouched"
            print(
                f"  {label} {gap['dt'].date()} {gap['side']} FVG "
                f"{money(gap['bot'])}–{money(gap['top'])}  CE {money(gap['ce'])}  {state}"
            )
    print()
    bearish = stacked and price < d_ema[20] and ctx["lower_high"] and ctx["lower_low"]
    in_ote = ctx["ote_lo"] <= price <= ctx["ote_hi"]
    print("Stance")
    if not bearish:
        print("  Daily filter is not a clean bearish stack. Stand aside until it is.")
    elif in_ote:
        print("  Price is inside the OTE premium. A short is eligible only after a")
        print("  15-minute or 1-hour bearish displacement and a fresh fair value gap.")
        print(f"  Invalidation: a 1-hour close above {money(ctx['ote_hi'])}.")
    elif price < ctx["eq"]:
        print("  NO market short and no dip buy.")
        print("  Daily bias is bearish, but price is still in discount, under equilibrium.")
        print(
            f"  High-probability short zone: {money(ctx['ote_lo'])} – {money(min(ctx['ote_hi'], ctx['ob']['h'] if ctx['ob'] else ctx['ote_hi']))}."
        )
        print("  Wait for price to trade there, then sell a bearish reaction.")
        print(f"  Invalidation of that idea: a 1-hour close above {money(ctx['ote_hi'])}.")
        print(f"  Liquidity targets below: {money(ctx['lo'])}, then the June weekly low cluster.")
    else:
        print("  Price is above equilibrium but not yet in OTE. Let it reach the zone.")


if __name__ == "__main__":
    main()
