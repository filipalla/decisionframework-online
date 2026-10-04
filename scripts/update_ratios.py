"""Daily closes for the metal ratios: gold/silver, miners/gold (GDX/GLD) and juniors/majors (GDXJ/GDX).

Source: TradingView market data (public scanner endpoint, unofficial): TVC gold and silver spot, AMEX GDX, GLD, GDXJ.
Runs each weekday at 21:30 UTC, after the US equity close in both summer and winter time.
Writes data/ratios.json and data/ratios-status.json. BACKFILL=n also stores the n-1 previous closes (the scanner keeps 3).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "ratios.json")
STATUS = os.path.join(HERE, "..", "data", "ratios-status.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SYMBOLS = {"gold": ("cfd", "TVC:GOLD"), "silver": ("cfd", "TVC:SILVER"),
           "gdx": ("america", "AMEX:GDX"), "gld": ("america", "AMEX:GLD"), "gdxj": ("america", "AMEX:GDXJ")}
log = []


def scan(market, tickers, cols):
    body = json.dumps({"symbols": {"tickers": tickers}, "columns": cols}).encode()
    req = urllib.request.Request(f"https://scanner.tradingview.com/{market}/scan", data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return {x["s"]: x["d"] for x in json.loads(r.read())["data"]}


def session_date(now):
    d = now.date()
    if now.weekday() >= 5 or now.hour < 20:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def prev_weekday(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def main():
    now = datetime.now(timezone.utc)
    back = max(1, min(3, int(os.environ.get("BACKFILL") or 1)))
    try:
        store = json.load(open(OUT))
    except (OSError, ValueError):
        store = {"rows": []}
    cols = ["name", "update_time", "close"] + [f"close[{i}]" for i in range(1, back)]
    q = {}
    try:
        for market in ("cfd", "america"):
            q.update(scan(market, [s for m, s in SYMBOLS.values() if m == market], cols))
    except Exception as e:
        log.append(f"prices failed: {type(e).__name__} {str(e)[:200]}")
        return finish(store, False)
    missing = [k for k, (m, s) in SYMBOLS.items() if s not in q]
    if missing:
        log.append(f"missing symbols: {missing}")
        return finish(store, False)
    upd = max(q[SYMBOLS[k][1]][1] or 0 for k in ("gdx", "gld", "gdxj"))
    if back == 1 and now.timestamp() - upd > 20 * 3600:
        log.append("no fresh US close (market holiday?); nothing added")
        return finish(store, True)

    have = {r["d"] for r in store["rows"]}
    d = session_date(now)
    for i in range(back):
        v = {k: q[SYMBOLS[k][1]][2 + i] for k in SYMBOLS}
        if all(x is not None for x in v.values()) and d.isoformat() not in have:
            row = {"d": d.isoformat(), **{k: round(float(x), 4) for k, x in v.items()}}
            row["gs"] = round(row["gold"] / row["silver"], 2)
            row["mg"] = round(row["gdx"] / row["gld"], 4)
            row["jm"] = round(row["gdxj"] / row["gdx"], 4)
            store["rows"].append(row)
            log.append(f"{row['d']}: gold/silver {row['gs']}, GDX/GLD {row['mg']}, GDXJ/GDX {row['jm']}")
        d = prev_weekday(d)
    store["rows"].sort(key=lambda r: r["d"])
    return finish(store, True)


def finish(store, ok):
    store.update({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                  "source": "TradingView market data: TVC gold and silver spot; AMEX GDX, GLD, GDXJ daily closes"})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if store.get("rows"):
        with open(OUT, "w") as f:
            json.dump(store, f, separators=(",", ":"))
    with open(STATUS, "w") as f:
        json.dump({"checked": store["updated"], "ok": ok, "log": log}, f, indent=1)
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
