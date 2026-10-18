"""Build feed.xml (RSS 2.0, full content) of all DecisionFramework insights.

Run from the site root with a local server on :8765 serving the site.
Charts (inline SVG / CSS bar blocks) are rendered to PNG under images/feed/.
Tables are flattened to paragraphs (Substack has no tables).
"""
import os, re, json, html
from datetime import datetime
from email.utils import format_datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SITE = "https://decisionframework.online"
LOCAL = "http://localhost:8765"

ARTICLES = [
    "article.html", "brics-global-finance-gold.html", "sovereign-debt-loop.html",
    "confidence-tokenized.html", "the-confidence-indicator.html",
    "the-confidence-no-one-priced.html", "the-third-confidence.html",
    "china-took-the-leverage-out.html", "commodity-etf-guide.html",
    "could-europe-take-your-gold.html", "silver-oil-rates-leverage.html",
    "gold-three-prices.html", "oil-curve-expiry-week.html",
    "france-switzerland-gap.html", "hormuz-dark-flows.html",
    "inflation-day-30-september-2026.html", "thirty-year-yields-gold.html",
    "brief-2026-10-11.html", "belgium-france-shadows.html",
    "sixteen-dealers-six-questions.html",
]
FALLBACK_DATES = {
    "inflation-day-30-september-2026.html": "2026-09-30",
    "brief-2026-10-11.html": "2026-10-11",
}
CHART_SEL = "main svg, main .bars"


def top_level(els, contains):
    out = []
    for e in els:
        if not any(o is not e and contains(o, e) for o in els):
            out.append(e)
    return out


def meta(soup, f):
    title = None
    date = None
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(s.string)
        except Exception:
            continue
        title = title or d.get("headline")
        date = date or d.get("datePublished")
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else soup.title.get_text().split("|")[0].strip()
    date = date or FALLBACK_DATES.get(f)
    desc = soup.find("meta", attrs={"name": "description"})
    sub = soup.select_one("header .subtitle")
    return title, date, (desc["content"] if desc else ""), (sub.get_text(" ", strip=True) if sub else "")


def absolutize(tag):
    for a in tag.find_all("a", href=True):
        h = a["href"]
        if h.startswith("/"):
            a["href"] = SITE + h
        elif not re.match(r"^(https?:|mailto:|#)", h):
            a["href"] = SITE + "/" + h
    for im in tag.find_all("img", src=True):
        s = im["src"]
        if s.startswith("/"):
            im["src"] = SITE + s
        elif not s.startswith("http"):
            im["src"] = SITE + "/" + s


def flatten_tables(soup, main):
    for t in main.find_all("table"):
        heads = [th.get_text(" ", strip=True) for th in t.select("thead th")]
        rows = t.select("tbody tr") or t.find_all("tr")[1 if heads else 0:]
        frag = soup.new_tag("div")
        for r in rows:
            cells = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
            if not cells:
                continue
            p = soup.new_tag("p")
            b = soup.new_tag("strong")
            b.string = cells[0]
            p.append(b)
            parts = []
            for i, c in enumerate(cells[1:], 1):
                label = heads[i] if i < len(heads) and heads[i] else ""
                parts.append(f"{label}: {c}" if label else c)
            if parts:
                p.append(" — " + "; ".join(parts))
            frag.append(p)
        t.replace_with(frag)


def clean_main(soup, main):
    for sel in [".df-signup", ".df-desk", "#df-comments", "script", "style", "form"]:
        for e in main.select(sel):
            e.decompose()
    for a in main.select("a.button"):
        p = a.find_parent("p")
        if p and "Back to Insights" in p.get_text():
            p.decompose()
    # stats tiles -> paragraphs
    for st in main.select(".stats"):
        frag = soup.new_tag("div")
        for s in st.select(".stat"):
            k = s.select_one(".k"); v = s.select_one(".v"); n = s.select_one(".n")
            p = soup.new_tag("p")
            b = soup.new_tag("strong")
            b.string = f"{k.get_text(' ', strip=True) if k else ''}: {v.get_text(' ', strip=True) if v else ''}"
            p.append(b)
            if n:
                p.append(" — " + n.get_text(" ", strip=True))
            frag.append(p)
        st.replace_with(frag)
    for c in main.select(".chain, .quote"):
        bq = soup.new_tag("blockquote")
        bq.append(c.get_text(" ", strip=True))
        c.replace_with(bq)
    flatten_tables(soup, main)
    # drop inline style / class noise
    for e in main.find_all(True):
        for attr in ("style", "class", "id", "data-page"):
            e.attrs.pop(attr, None)


def main():
    os.makedirs("images/feed", exist_ok=True)
    items = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        for f in ARTICLES:
            slug = f[:-5]
            soup = BeautifulSoup(open(f, encoding="utf-8").read(), "html.parser")
            title, date, desc, sub = meta(soup, f)
            main_el = soup.find("main")
            # render charts
            pg.goto(f"{LOCAL}/{f}")
            pg.wait_for_timeout(400)
            handles = pg.query_selector_all(CHART_SEL)
            keep = pg.evaluate(
                """(sel) => { const els=[...document.querySelectorAll(sel)];
                   return els.map(e => !els.some(o => o!==e && o.contains(e))); }""",
                CHART_SEL)
            handles = [h for h, k in zip(handles, keep) if k]
            bs_charts = top_level(main_el.select(CHART_SEL),
                                  lambda o, e: e in o.descendants)
            if len(handles) != len(bs_charts):
                raise SystemExit(f"{f}: chart count mismatch {len(handles)} vs {len(bs_charts)}")
            for i, (h, el) in enumerate(zip(handles, bs_charts), 1):
                out = f"images/feed/{slug}-{i}.png"
                h.scroll_into_view_if_needed()
                h.screenshot(path=out)
                label = el.get("aria-label") or (el.find("title").get_text() if el.find("title") else title)
                img = soup.new_tag("img", src=f"/{out}", alt=label)
                el.replace_with(img)
            # header image (if the page has one outside main)
            hero = None
            for im in soup.find_all("img"):
                if im.find_parent("main") is None:
                    hero = im
                    break
            clean_main(soup, main_el)
            if hero is not None:
                h2 = soup.new_tag("img", src=hero["src"], alt=hero.get("alt", ""))
                main_el.insert(0, h2)
            if sub:
                sp = soup.new_tag("p")
                em = soup.new_tag("em"); em.string = sub
                sp.append(em)
                main_el.insert(1 if hero is not None else 0, sp)
            orig = soup.new_tag("p")
            em = soup.new_tag("em")
            em.append("Originally published at ")
            a = soup.new_tag("a", href=f"{SITE}/{f}"); a.string = "decisionframework.online"
            em.append(a); em.append(". Read The Gold Investor free in your language: ")
            a2 = soup.new_tag("a", href=f"{SITE}/free-preview.html"); a2.string = "free preview"
            em.append(a2); em.append(".")
            orig.append(em)
            main_el.append(orig)
            absolutize(main_el)
            body = "".join(str(c) for c in main_el.contents).strip()
            items.append((date, title, f, desc, body))
            print(date, f, "charts:", len(bs_charts))
        b.close()

    items.sort(key=lambda x: x[0])
    rss = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:atom="http://www.w3.org/2005/Atom">',
           "<channel>",
           "<title>DecisionFramework — Insights</title>",
           f"<link>{SITE}/insights-and-partners.html#insights</link>",
           f'<atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>',
           "<description>Market analysis on gold, silver, oil, currencies and the bond markets behind them, by Stonecold.</description>",
           "<language>en</language>"]
    for date, title, f, desc, body in reversed(items):  # newest first, as feeds expect
        dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=8)
        from datetime import timezone, timedelta
        dt = dt.replace(tzinfo=timezone(timedelta(hours=2)))
        rss += ["<item>",
                f"<title>{html.escape(title)}</title>",
                f"<link>{SITE}/{f}</link>",
                f'<guid isPermaLink="true">{SITE}/{f}</guid>',
                f"<pubDate>{format_datetime(dt)}</pubDate>",
                "<dc:creator>Stonecold</dc:creator>",
                f"<description>{html.escape(desc)}</description>",
                "<content:encoded><![CDATA[" + body.replace("]]>", "]]]]><![CDATA[>") + "]]></content:encoded>",
                "</item>"]
    rss += ["</channel>", "</rss>"]
    open("feed.xml", "w", encoding="utf-8").write("\n".join(rss) + "\n")
    print("items:", len(items))


if __name__ == "__main__":
    main()
