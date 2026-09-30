"""One-off study: US dollar around midterm elections. Writes data/midterm-study.json.
Series: DTWEXM (major-currency dollar index, 1973-2019) and DTWEXBGS (broad index, 2006-)."""
import json, os, urllib.parse, urllib.request
from datetime import date, timedelta

KEY = os.environ.get("FRED_API_KEY", "").strip()
MIDTERMS = ["1974-11-05", "1978-11-07", "1982-11-02", "1986-11-04", "1990-11-06", "1994-11-08",
            "1998-11-03", "2002-11-05", "2006-11-07", "2010-11-02", "2014-11-04", "2018-11-06", "2022-11-08"]


def series(sid):
    q = urllib.parse.urlencode({"series_id": sid, "api_key": KEY, "file_type": "json", "observation_start": "1973-01-01"})
    with urllib.request.urlopen("https://api.stlouisfed.org/fred/series/observations?" + q, timeout=60) as r:
        j = json.load(r)
    return {o["date"]: float(o["value"]) for o in j["observations"] if o["value"] not in (".", "")}


def at(s, d, before=True):
    d0 = date.fromisoformat(d)
    for i in range(10):
        k = (d0 - timedelta(i) if before else d0 + timedelta(i)).isoformat()
        if k in s:
            return s[k]
    return None


def main():
    out = {"note": "percent change of the dollar index; positive = stronger dollar", "rows": []}
    try:
        m = series("DTWEXM")
    except Exception as e:
        m = {}; out["err_m"] = str(e)
    try:
        b = series("DTWEXBGS")
    except Exception as e:
        b = {}; out["err_b"] = str(e)
    for e in MIDTERMS:
        s, name = (m, "DTWEXM") if at(m, e) else (b, "DTWEXBGS")
        ed = date.fromisoformat(e)
        def pt(days):
            return at(s, (ed + timedelta(days)).isoformat(), before=days <= 0)
        v0 = pt(0)
        row = {"election": e, "index": name}
        for lab, d in [("3m_before", -91), ("1m_before", -30), ("4w_from_late_sep", None)]:
            if d is None:
                x = at(s, f"{e[:4]}-09-30")
            else:
                x = pt(d)
            row[lab] = round((v0 / x - 1) * 100, 2) if (x and v0) else None
        for lab, d in [("1m_after", 30), ("3m_after", 91), ("6m_after", 182)]:
            x = pt(d)
            row[lab] = round((x / v0 - 1) * 100, 2) if (x and v0) else None
        if name == "DTWEXM" and b and at(b, e):
            row["broad_sep30_to_election"] = round((at(b, e) / at(b, f"{e[:4]}-09-30") - 1) * 100, 2)
        out["rows"].append(row)
    os.makedirs("data", exist_ok=True)
    json.dump(out, open("data/midterm-study.json", "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
