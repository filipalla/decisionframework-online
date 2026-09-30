"""Fetch daily dollar, Treasury curve and stress series from FRED and write data/macro.json.

Needs repo secret FRED_API_KEY (free at fred.stlouisfed.org). Falls back to the keyless
FRED graph CSV. Every run also writes data/macro-status.json so a failed run can be diagnosed.
"""
import csv
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

START = "2019-01-01"
SERIES = {
    "usd":    "DTWEXBGS",      # Nominal broad U.S. dollar index (Fed), Jan 2006 = 100
    "eurusd": "DEXUSEU",       # U.S. dollars per euro
    "audusd": "DEXUSAL",       # U.S. dollars per Australian dollar
    "t3m":    "DGS3MO",
    "t2":     "DGS2",
    "t5":     "DGS5",
    "t10":    "DGS10",
    "t30":    "DGS30",
    "real10": "DFII10",        # 10-year TIPS yield
    "s2s10":  "T10Y2Y",        # 10-year minus 2-year
    "vix":    "VIXCLS",
    "gvz":    "GVZCLS",        # Cboe gold volatility index
    "hyoas":  "BAMLH0A0HYM2",  # ICE BofA US high yield option-adjusted spread
}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "macro.json")
STATUS = os.path.join(HERE, "..", "data", "macro-status.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36 decisionframework.online")
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
log = []


def get(url, timeout=40, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(4 * (attempt + 1))
    raise last


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fred_api(sid):
    q = urllib.parse.urlencode({"series_id": sid, "api_key": FRED_KEY, "file_type": "json",
                                "observation_start": START})
    j = json.loads(get("https://api.stlouisfed.org/fred/series/observations?" + q))
    return {o["date"]: num(o["value"]) for o in j.get("observations", []) if num(o["value"]) is not None}


def fred_csv(sid):
    text = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={START}", timeout=25, tries=1)
    rows = csv.reader(io.StringIO(text))
    next(rows)
    return {r[0]: num(r[1]) for r in rows if len(r) > 1 and num(r[1]) is not None}


def fetch(name, sid):
    methods = []
    if FRED_KEY:
        methods.append(("fred-api", lambda: fred_api(sid)))
    methods.append(("fred-csv", lambda: fred_csv(sid)))
    for label, fn in methods:
        try:
            data = fn()
            if data:
                log.append(f"{name} ({sid}): {label} ok, {len(data)} points, last {max(data)}")
                return data
            log.append(f"{name} ({sid}): {label} returned no data")
        except Exception as e:
            log.append(f"{name} ({sid}): {label} failed: {type(e).__name__}")
    return {}


def write_status(ok):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "w") as f:
        json.dump({"checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                   "ok": ok, "log": log}, f, indent=1)


def main():
    d = {k: fetch(k, v) for k, v in SERIES.items()}
    got = {k: v for k, v in d.items() if v}
    if "usd" not in got or "t10" not in got:
        log.append("core series missing; data/macro.json left unchanged")
        write_status(False)
        print("\n".join(log))
        return 0
    dates = sorted(set().union(*[set(v) for v in got.values()]))
    series = {k: [(round(d[k][x], 4) if x in d[k] else None) for x in dates] for k in SERIES}
    with open(OUT, "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                   "source": "FRED, Federal Reserve Bank of St. Louis",
                   "ids": SERIES, "dates": dates, "series": series}, f, separators=(",", ":"))
    log.append(f"wrote {len(dates)} dates, last {dates[-1]}")
    write_status(True)
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
