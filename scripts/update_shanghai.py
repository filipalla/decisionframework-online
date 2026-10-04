"""Record the Shanghai gold and silver premium from the MetalCharts API.

Needs repo secret METALCHARTS_API_KEY. Each run appends one snapshot per metal to
data/shanghai-premium.json and writes data/shanghai-status.json (HTTP status and message,
never the key) so a failed run can be diagnosed. Shanghai premium data by MetalCharts
(https://metalcharts.org).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "shanghai-premium.json")
STATUS = os.path.join(HERE, "..", "data", "shanghai-status.json")
URL = "https://api.metalcharts.org/v1/shanghai/?symbols=XAU,XAG"
KEY = os.environ.get("METALCHARTS_API_KEY", "").strip()
FIELDS = ["price", "priceCNY", "exchangeRate", "premiumPercent", "premiumPercentExVat",
          "priceExVat", "vatInclusive", "timestamp", "exchange", "marketType", "source"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def status(ok, http, msg, extra=None):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    d = {"checked": now(), "ok": ok, "http": http, "message": msg[:500]}
    if extra:
        d.update(extra)
    with open(STATUS, "w") as f:
        json.dump(d, f, indent=1)
    print(json.dumps(d, indent=1))


def main():
    if not KEY:
        status(False, None, "METALCHARTS_API_KEY secret is not set")
        return 0
    req = urllib.request.Request(URL, headers={"Authorization": "Bearer " + KEY, "Accept": "application/json",
                                               "User-Agent": "decisionframework.online shanghai-premium"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body, http, attribution = r.read().decode("utf-8"), r.status, r.headers.get("X-Attribution", "")
    except urllib.error.HTTPError as e:
        status(False, e.code, e.read().decode("utf-8", "replace"))
        return 0
    except Exception as e:
        status(False, None, type(e).__name__ + ": " + str(e))
        return 0
    try:
        j = json.loads(body)
    except ValueError:
        status(False, http, "Response was not JSON: " + body[:300])
        return 0
    data = j.get("data") or {}
    if not j.get("success") or not data:
        status(False, http, "No data in response: " + body[:300])
        return 0

    try:
        with open(OUT) as f:
            store = json.load(f)
    except (OSError, ValueError):
        store = {"source": "MetalCharts API, /v1/shanghai/", "credit": "Shanghai premium data by MetalCharts (https://metalcharts.org)",
                 "note": "One snapshot per run. premiumUsd = price - price / (1 + premiumPercent/100), USD per troy ounce.",
                 "rows": []}
    added = 0
    for sym, d in data.items():
        if not isinstance(d, dict) or d.get("price") is None:
            continue
        row = {"run": now(), "symbol": sym}
        for k in FIELDS:
            if k in d:
                row[k] = d[k]
        p, pct = d.get("price"), d.get("premiumPercentExVat", d.get("premiumPercent"))
        if p is not None and pct is not None:
            row["premiumUsd"] = round(p - p / (1 + pct / 100.0), 2)
        key = (sym, row.get("timestamp"))
        if any((r.get("symbol"), r.get("timestamp")) == key for r in store["rows"]):
            continue  # same quote as an earlier run (market closed): skip
        store["rows"].append(row)
        added += 1
    store["updated"] = now()
    with open(OUT, "w") as f:
        json.dump(store, f, indent=1)
    status(True, http, "ok", {"added": added, "symbols": list(data.keys()), "cacheAge": j.get("cacheAge"),
                              "isStale": j.get("isStale"), "attribution": attribution})
    return 0


if __name__ == "__main__":
    sys.exit(main())
