"""Shanghai gold premium: SGE benchmark price versus the Western price, in USD per troy ounce.

History (back to 2016): SGE Shanghai Gold Benchmark PM (14:15 Beijing) against the LBMA gold
price AM (10:30 London), or, when LBMA blocks the request, the XAU/USD daily open (Stooq) or the
COMEX front-month daily open (Yahoo), on the same date, converted at the Fed's CNY/USD rate (FRED DEXCHUS,
last available value). Live reading (each weekday run after 06:15 UTC): today's SGE PM benchmark
against MetalCharts live gold spot and USD/CNY at the moment of the run.

Only derived values are stored (SGE USD price and the premium), not raw LBMA prices.
Secrets: FRED_API_KEY (exchange rate history), METALCHARTS_API_KEY (live spot and FX, free tier).
Writes data/shanghai-premium.json and data/shanghai-status.json (sources and HTTP results, never keys).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "shanghai-premium.json")
STATUS = os.path.join(HERE, "..", "data", "shanghai-status.json")
OZ = 31.1034768
FRED = os.environ.get("FRED_API_KEY", "").strip()
MC = os.environ.get("METALCHARTS_API_KEY", "").strip()
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
log = []


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get(url, data=None, headers=None, timeout=40, tries=3):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    h.update(headers or {})
    body = urllib.parse.urlencode(data).encode() if data else None
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def sge():
    txt = get("https://www.sge.com.cn/graph/DayilyJzj", data={"start": "2016-01-01", "end": "2099-12-31"},
              headers={"Referer": "https://www.sge.com.cn/sjzx/jzj", "X-Requested-With": "XMLHttpRequest"})
    j = json.loads(txt)
    out = {}
    for key in ("zp", "wp"):
        for ts, v in j.get(key, []):
            d = (datetime.fromtimestamp(ts / 1000, timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")
            out.setdefault(d, {})["am" if key == "zp" else "pm"] = v
    return out


def lbma_am():
    j = json.loads(get("https://prices.lbma.org.uk/json/gold_am.json",
                       headers={"Referer": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices"}))
    out = {}
    for row in j:
        d, v = row.get("d"), row.get("v") or []
        if d and v and v[0]:
            out[d] = float(v[0])
    return out


def stooq_open():
    """XAU/USD spot daily bars from Stooq; the day's open (about 22:00-00:00 UTC) is the bar edge nearest
    the SGE PM benchmark at 06:15 UTC, roughly six to eight hours earlier."""
    txt = get("https://stooq.com/q/d/l/?s=xauusd&i=d", headers={"Accept": "text/csv"})
    out = {}
    lines = txt.strip().splitlines()
    if not lines or not lines[0].lower().startswith("date"):
        raise ValueError("unexpected Stooq response: " + txt[:80])
    for ln in lines[1:]:
        c = ln.split(",")
        try:
            out[c[0]] = float(c[1])
        except (IndexError, ValueError):
            pass
    return out


def yahoo_open():
    """COMEX gold front-month (GC=F) daily open from Yahoo Finance chart data, as a fallback."""
    last = None
    for host in ("query2", "query1", "query2"):
        try:
            j = json.loads(get(f"https://{host}.finance.yahoo.com/v8/finance/chart/GC%3DF?range=10y&interval=1d",
                               headers={"Accept": "application/json"}, tries=2))
            break
        except Exception as e:
            last = e
            time.sleep(20)
    else:
        raise last
    r = j["chart"]["result"][0]
    opens = r["indicators"]["quote"][0]["open"]
    out = {}
    for ts, v in zip(r["timestamp"], opens):
        if v:
            out[datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")] = float(v)
    return out


def fred_cny():
    q = urllib.parse.urlencode({"series_id": "DEXCHUS", "api_key": FRED, "file_type": "json",
                                "observation_start": "2016-01-01"})
    j = json.loads(get("https://api.stlouisfed.org/fred/series/observations?" + q))
    out = {}
    for o in j.get("observations", []):
        try:
            out[o["date"]] = float(o["value"])
        except ValueError:
            pass
    return out


def mc(path):
    return json.loads(get("https://api.metalcharts.org" + path, headers={"Authorization": "Bearer " + MC}))


def step(name, fn):
    try:
        r = fn()
        log.append(f"{name}: ok, {len(r) if hasattr(r, '__len__') else 1} items")
        return r
    except Exception as e:
        msg = str(e)
        if hasattr(e, "read"):
            try:
                msg += " " + e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
        log.append(f"{name}: failed: {type(e).__name__} {msg[:250]}")
        return None


def ffill(series, d):
    if not series:
        return None
    for i in range(8):
        k = (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y-%m-%d")
        if k in series:
            return series[k]
    return None


def main():
    try:
        with open(OUT) as f:
            store = json.load(f)
    except (OSError, ValueError):
        store = {}
    store.setdefault("live", [])
    s = step("SGE benchmark (sge.com.cn)", sge)
    # History is a one-off backfill kept in the file (see "method"); free Western gold prices refuse
    # GitHub's servers, so this job only adds the live reading.
    # live reading, only on a weekday run after the SGE PM benchmark (06:15 UTC)
    t = datetime.now(timezone.utc)
    if s and MC and t.weekday() < 5 and t.hour >= 6:
        today = (t + timedelta(hours=8)).strftime("%Y-%m-%d")
        pm = (s.get(today) or {}).get("pm")
        if pm is None:
            log.append(f"live: no SGE PM benchmark for {today} (holiday or not yet published)")
        else:
            px = step("MetalCharts prices", lambda: mc("/v1/prices/?symbols=XAU"))
            cur = step("MetalCharts currency", lambda: mc("/v1/currency/"))
            try:
                spot = float(px["data"]["XAU"]["price"])
                rates = cur.get("data") or cur.get("rates") or {}
                rates = rates.get("rates", rates)
                cny = float(rates["CNY"])
                usd = pm * OZ / cny
                if not any(r.get("date") == today for r in store["live"]):
                    store["live"].append({"date": today, "run": now(), "sge": round(usd, 2), "spot": round(spot, 2),
                                          "fx": cny, "prem": round(usd - spot, 2), "pct": round((usd / spot - 1) * 100, 3)})
                log.append(f"live: {today} premium {usd - spot:.2f} USD/oz")
            except Exception as e:
                log.append(f"live: could not read MetalCharts response ({type(e).__name__}: {str(e)[:120]}); "
                           f"prices keys {list((px or {}).keys())[:5]}, currency keys {list((cur or {}).keys())[:5]}")

    store.update({"updated": now(), "unit": "USD per troy ounce",
                  "credit": "Live gold spot and USD/CNY by MetalCharts (https://metalcharts.org)"})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if store.get("daily") or store.get("live"):
        with open(OUT, "w") as f:
            json.dump(store, f, separators=(",", ":"))
    with open(STATUS, "w") as f:
        json.dump({"checked": now(), "log": log}, f, indent=1)
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
