"""Daily NYMEX/ICE closes for the futures crack spreads, between two EIA releases.

Front-month contracts (the nearest one not yet at expiry) for:
  HO  NY Harbor ULSD (NYMEX, $/gal)      RB  RBOB gasoline (NYMEX, $/gal)
  CL  WTI crude (NYMEX, $/bbl)           BRN Brent crude (ICE Europe, $/bbl)
Cracks in $/bbl: diesel = HO*42 - Brent, gasoline = RB*42 - WTI, 3-2-1 = (2*RB*42 + HO*42 - 3*WTI) / 3.

Source: TradingView market data (public scanner endpoint, unofficial). The job runs each weekday at 20:50 UTC,
after the NYMEX and ICE settlements and before Globex reopens for the next session.
Writes data/futures-cracks.json and data/futures-status.json. BACKFILL=n also stores the n-1 previous closes.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "futures-cracks.json")
STATUS = os.path.join(HERE, "..", "data", "futures-status.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
CODES = "FGHJKMNQUVXZ"
ROOTS = {"ho": "NYMEX:HO", "rb": "NYMEX:RB", "cl": "NYMEX:CL", "brn": "ICEEUR:BRN"}
log = []


def scan(tickers, cols):
    body = json.dumps({"symbols": {"tickers": tickers}, "columns": cols}).encode()
    req = urllib.request.Request("https://scanner.tradingview.com/futures/scan", data=body, headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return {x["s"]: x["d"] for x in json.loads(r.read())["data"]}


def candidates(root, today):
    out = []
    for i in range(0, 5):
        m = (today.month - 1 + i) % 12
        y = today.year + (today.month - 1 + i) // 12
        out.append(f"{root}{CODES[m]}{y}")
    return out


def session_date(now):
    d = now.date()
    if now.weekday() >= 5 or now.hour < 19:
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
    back = max(1, int(os.environ.get("BACKFILL") or 1))
    try:
        store = json.load(open(OUT))
    except (OSError, ValueError):
        store = {"rows": []}
    sess = session_date(now)
    ymd = int(sess.strftime("%Y%m%d"))

    # pick the front contract per product: nearest expiration after the session date
    front = {}
    try:
        info = scan([t for r in ROOTS.values() for t in candidates(r, sess)], ["name", "expiration", "description"])
        for k, root in ROOTS.items():
            live = sorted((v[1], s, v[2]) for s, v in info.items() if s.startswith(root) and v[1] and v[1] > ymd)
            front[k] = live[0]
            log.append(f"{k}: front {live[0][1]} ({live[0][2]}), expires {live[0][0]}")
    except Exception as e:
        log.append(f"contract lookup failed: {type(e).__name__} {str(e)[:200]}")
        return finish(store, ok=False)

    cols = ["name", "update_time"] + ["close"] + [f"close[{i}]" for i in range(1, back)]
    try:
        q = scan([front[k][1] for k in ROOTS], cols)
    except Exception as e:
        log.append(f"prices failed: {type(e).__name__} {str(e)[:200]}")
        return finish(store, ok=False)

    # stale check: if the newest quote is older than 20 hours, the session did not trade (holiday)
    upd = max((q[front[k][1]][1] or 0) for k in ROOTS)
    if back == 1 and now.timestamp() - upd > 20 * 3600:
        log.append("no fresh quote (market holiday?); nothing added")
        return finish(store, ok=True)

    have = {r["d"] for r in store["rows"]}
    d = sess
    for i in range(back):
        vals = {k: q[front[k][1]][2 + i] for k in ROOTS}
        ds = d.isoformat()
        if all(v is not None for v in vals.values()) and ds not in have:
            ho, rb, cl, brn = (float(vals[k]) for k in ("ho", "rb", "cl", "brn"))
            store["rows"].append({
                "d": ds, "ho": ho, "rb": rb, "cl": cl, "brn": brn,
                "diesel": round(ho * 42 - brn, 2), "gasoline": round(rb * 42 - cl, 2),
                "c321": round((2 * rb * 42 + ho * 42 - 3 * cl) / 3, 2),
                "contracts": {k: front[k][1].split(":")[1] for k in ROOTS}})
            log.append(f"{ds}: diesel {ho * 42 - brn:.2f}, gasoline {rb * 42 - cl:.2f}")
        d = prev_weekday(d)
    store["rows"].sort(key=lambda r: r["d"])

    # mark rolls: a product whose contract differs from the previous row
    prev = None
    for r in store["rows"]:
        r["roll"] = [k for k in ROOTS if prev and prev["contracts"][k] != r["contracts"][k]]
        prev = r
    return finish(store, ok=True)


def finish(store, ok):
    store.update({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                  "unit": "USD per barrel", "source": "NYMEX and ICE daily closes via TradingView"})
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
