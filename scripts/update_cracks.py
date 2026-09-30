"""Fetch daily spot prices (U.S. EIA data) and write crack spreads to data/cracks.json.

Series:
  NY Harbor ultra-low-sulfur No.2 diesel, $/gal   FRED DDFUELNYH  | EIA EER_EPD2DXL0_PF4_Y35NY_DPG
  NY Harbor conventional gasoline (regular), $/gal FRED DGASNYH    | EIA EER_EPMRU_PF4_Y35NY_DPG
  WTI Cushing crude, $/bbl                        FRED DCOILWTICO | EIA RWTC
  Brent Europe crude, $/bbl                       FRED DCOILBRENTEU | EIA RBRTE

Sources are tried in order; the first that works for a series is used:
  1. FRED API        (needs repo secret FRED_API_KEY, free at fred.stlouisfed.org)
  2. EIA API v2      (needs repo secret EIA_API_KEY, free at eia.gov/opendata)
  3. FRED graph CSV  (no key)
Every run also writes data/cracks-status.json so a failed run can be diagnosed.
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
    "ulsd":  {"fred": "DDFUELNYH",    "eia": "EER_EPD2DXL0_PF4_Y35NY_DPG"},
    "gas":   {"fred": "DGASNYH",      "eia": "EER_EPMRU_PF4_Y35NY_DPG"},
    "wti":   {"fred": "DCOILWTICO",   "eia": "RWTC"},
    "brent": {"fred": "DCOILBRENTEU", "eia": "RBRTE"},
}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "cracks.json")
STATUS = os.path.join(HERE, "..", "data", "cracks-status.json")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36 decisionframework.online")
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
EIA_KEY = os.environ.get("EIA_API_KEY", "").strip()
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


def eia_api(sid):
    q = urllib.parse.urlencode({"api_key": EIA_KEY, "frequency": "daily", "data[0]": "value",
                                "facets[series][]": sid, "start": START, "length": 5000,
                                "sort[0][column]": "period", "sort[0][direction]": "asc"})
    j = json.loads(get("https://api.eia.gov/v2/petroleum/pri/spt/data/?" + q))
    return {r["period"]: num(r["value"]) for r in j["response"]["data"] if num(r["value"]) is not None}


def fred_csv(sid):
    text = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={START}", timeout=25, tries=1)
    rows = csv.reader(io.StringIO(text))
    next(rows)
    return {r[0]: num(r[1]) for r in rows if len(r) > 1 and num(r[1]) is not None}


def fetch(name, ids):
    methods = []
    if FRED_KEY:
        methods.append(("fred-api", lambda: fred_api(ids["fred"])))
    if EIA_KEY:
        methods.append(("eia-api", lambda: eia_api(ids["eia"])))
    methods.append(("fred-csv", lambda: fred_csv(ids["fred"])))
    for label, fn in methods:
        try:
            data = fn()
            if data:
                log.append(f"{name}: {label} ok, {len(data)} points, last {max(data)}")
                return data
            log.append(f"{name}: {label} returned no data")
        except Exception as e:
            log.append(f"{name}: {label} failed: {type(e).__name__}: {e}")
    return {}


def write_status(ok):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "w") as f:
        json.dump({"checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                   "ok": ok, "log": log}, f, indent=1)


def main():
    d = {k: fetch(k, v) for k, v in SERIES.items()}
    dates = sorted(set(d["ulsd"]) & set(d["gas"]) & set(d["wti"]) & set(d["brent"]))
    if not dates:
        log.append("no overlapping dates; data/cracks.json left unchanged")
        write_status(False)
        print("\n".join(log))
        return 0  # keep the workflow green so the status file gets committed

    rows = []
    for day in dates:
        u, g, w, b = d["ulsd"][day] * 42, d["gas"][day] * 42, d["wti"][day], d["brent"][day]
        rows.append({"d": day,
                     "diesel_brent": round(u - b, 2), "diesel_wti": round(u - w, 2),
                     "gasoline_wti": round(g - w, 2), "c321": round((2 * g + u - 3 * w) / 3, 2),
                     "brent": round(b, 2), "wti": round(w, 2)})
    with open(OUT, "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                   "source": "U.S. EIA daily spot prices (NY Harbor ULSD, NY Harbor gasoline, WTI, Brent)",
                   "rows": rows}, f, separators=(",", ":"))
    log.append(f"wrote {len(rows)} rows, last {rows[-1]['d']}")
    write_status(True)
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
