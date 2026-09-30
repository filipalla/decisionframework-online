"""Fetch daily spot prices from FRED (EIA data) and write crack spreads to data/cracks.json.

Series (all daily spot, public, no API key needed):
  DDFUELNYH    NY Harbor ultra-low-sulfur No.2 diesel, $/gal
  DGASNYH      NY Harbor conventional gasoline (regular), $/gal
  DCOILWTICO   WTI Cushing crude, $/bbl
  DCOILBRENTEU Brent Europe crude, $/bbl
"""
import csv
import io
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

START = "2019-01-01"
SERIES = ["DDFUELNYH", "DGASNYH", "DCOILWTICO", "DCOILBRENTEU"]
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "cracks.json")


def fetch(sid):
    req = urllib.request.Request(URL.format(sid=sid, start=START),
                                 headers={"User-Agent": "decisionframework-crack-updater"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8")
            break
        except Exception as e:  # retry transient errors
            if attempt == 2:
                raise
            print(f"retry {sid}: {e}", file=sys.stderr)
            time.sleep(5)
    rows = csv.reader(io.StringIO(text))
    next(rows)  # header (DATE or observation_date)
    out = {}
    for row in rows:
        if len(row) < 2:
            continue
        d, v = row[0], row[1].strip()
        if v in ("", "."):
            continue
        try:
            out[d] = float(v)
        except ValueError:
            continue
    return out


def main():
    data = {sid: fetch(sid) for sid in SERIES}
    ulsd, gas, wti, brent = (data[s] for s in SERIES)

    dates = sorted(set(ulsd) & set(gas) & set(wti) & set(brent))
    rows = []
    for d in dates:
        u, g, w, b = ulsd[d] * 42, gas[d] * 42, wti[d], brent[d]
        rows.append({
            "d": d,
            "diesel_brent": round(u - b, 2),
            "diesel_wti": round(u - w, 2),
            "gasoline_wti": round(g - w, 2),
            "c321": round((2 * g + u - 3 * w) / 3, 2),
            "brent": round(b, 2),
            "wti": round(w, 2),
        })

    if not rows:
        print("no overlapping data, keeping old file", file=sys.stderr)
        sys.exit(1)

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "FRED / U.S. EIA daily spot prices (NY Harbor ULSD, NY Harbor gasoline, WTI, Brent)",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"wrote {len(rows)} rows, last {rows[-1]['d']}")


if __name__ == "__main__":
    main()
