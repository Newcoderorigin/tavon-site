#!/usr/bin/env python3
"""
Affiliate Trend Site — single-file MVP
- Trends → keywords
- Keywords → affiliate search pages
- Static site generator (index + keyword pages)
- Social CSV for promos

Optional libs:
- pytrends (pip install pytrends) for real Google Trends keywords
Everything else: stdlib only.

Usage:
  python affiliate_trend_site.py --site-dir site --amazon-tag yourtag-20 --niches "home gym,desk setup,pet hair remover"
  # with Google Trends (if pytrends installed):
  python affiliate_trend_site.py --site-dir site --amazon-tag yourtag-20 --trends "US" --trend-count 12

Then host ./site on Netlify/Vercel/S3 or run:
  python -m http.server --directory site 8080
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import random
import re
import sys
import urllib.parse

# ------------------------- CONFIG -------------------------
SITE_TITLE = "TrendFinder • Deals & Ideas"
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
THEME_CSS = """
:root{--bg:#0b1020;--card:#121735;--text:#e9ecff;--muted:#9aa3c7;--accent:#7c9bff;--accent2:#17e3a6;}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#0a0f22, #101738);
color:var(--text);font:16px/1.6 system-ui,Segoe UI,Roboto,Inter,Arial}
a{color:var(--accent);text-decoration:none}a:hover{opacity:.9}
.container{max-width:1024px;margin:0 auto;padding:24px}
.grid{display:grid;gap:16px}
.cards{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:16px;
padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.25);backdrop-filter: blur(6px)}
.badge{display:inline-block;background:rgba(255,255,255,.09);padding:4px 10px;border-radius:999px;color:var(--muted);font-size:12px}
h1,h2,h3{margin:8px 0 12px} .muted{color:var(--muted)} .btn{display:inline-block;background:var(--accent);
color:#0b1020;padding:10px 14px;border-radius:10px;font-weight:600} .btn.alt{background:var(--accent2)}
.hero{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.search{display:flex;gap:8px}
.input{flex:1;padding:10px 12px;border-radius:10px;border:1px solid rgba(255,255,255,.15);background:#0f1530;color:var(--text)}
.footer{margin-top:32px;color:var(--muted);font-size:14px}
.kwd a{display:inline-block;margin:6px 8px 0 0;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08)}
.small{font-size:13px}
"""

# ------------------------- CORE -------------------------
def slugify(s:str)->str:
    s = re.sub(r"[^a-zA-Z0-9]+","-", s.strip().lower()).strip("-")
    return s or "item"

def amazon_search_url(keyword:str, tag:str)->str:
    # Amazon search with affiliate tag (public, compliant)
    return f"https://www.amazon.com/s?{urllib.parse.urlencode({'k': keyword, 'tag': tag})}"

def ebay_search_url(keyword:str, campid:str="", customid:str="")->str:
    # eBay Partner Network basic search link (optional params)
    base = f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(keyword)}"
    qs = []
    if campid: qs.append(("_trkparms", f"aid={campid}"))
    if customid: qs.append(("_trksid", customid))
    if qs:
        return base + "&" + urllib.parse.urlencode(qs)
    return base

def pinterest_search_link(keyword:str)->str:
    # Public search page (no scraping, just link out for inspiration)
    return f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(keyword)}"

def get_trending_keywords(country:str="US", count:int=12, seed:list[str]|None=None)->list[str]:
    # Try pytrends for real trends; fallback to provided seeds or defaults
    try:
        from pytrends.request import TrendReq
        pytrend = TrendReq(hl="en-US", tz=360)
        # Use Daily Trends (may vary by region)
        daily = pytrend.trending_searches(pn=country)
        kws = [str(x[0]) if isinstance(x, (list,tuple)) else str(x) for x in daily.values.tolist()]
        kws = [k for k in kws if k and len(k) < 40][:max(3, count)]
        if kws: return kws
    except Exception:
        pass
    fallback = seed or [
        "desk setup", "home gym", "pet hair remover", "portable blender",
        "mini projector", "rgb lights", "travel organizer", "phone tripod",
        "ice roller", "car vacuum", "wireless lav mic", "cat water fountain"
    ]
    random.shuffle(fallback)
    return fallback[:count]

def ensure_dir(path:str): os.makedirs(path, exist_ok=True)

# ------------------------- TEMPLATES -------------------------
def page_layout(title:str, body_html:str, subtitle:str="")->str:
    title_safe = html.escape(title)
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title_safe}</title><style>{THEME_CSS}</style></head><body>
<div class="container">
  <div class="hero"><div>
    <div class="badge">TrendFinder</div>
    <h1>{title_safe}</h1>
    <p class="muted">{html.escape(subtitle)}</p>
  </div>
  <form class="search" action="search.html" method="get">
    <input class="input" name="q" placeholder="Search ideas or products..."/>
    <button class="btn">Find</button>
  </form></div>
  {body_html}
  <div class="footer">
    <p>{html.escape(DISCLOSURE)}</p>
    <p class="small">© {dt.datetime.utcnow().year} TrendFinder • Built with an AI growth stack.</p>
  </div>
</div></body></html>"""

def index_body(keywords:list[str])->str:
    chips = "".join([f'<span class="kwd"><a href="{slugify(k)}.html">{html.escape(k)}</a></span>' for k in keywords])
    return f"""
<section class="card">
  <h2>Fresh Trends</h2>
  <p class="muted">Tap a topic to explore products & inspo.</p>
  <div>{chips}</div>
</section>
"""

def keyword_body(kw:str, amazon_tag:str, ebay_campid:str, ebay_customid:str)->str:
    amz = amazon_search_url(kw, amazon_tag) if amazon_tag else None
    eby = ebay_search_url(kw, ebay_campid, ebay_customid) if (ebay_campid or ebay_customid) else ebay_search_url(kw)
    pin = pinterest_search_link(kw)
    cards = []
    if amz: cards.append(f"""
    <div class="card"><h3>Amazon • {html.escape(kw)}</h3>
      <p class="muted">Browse and buy — affiliate tag applied.</p>
      <a class="btn" href="{amz}" rel="nofollow sponsored">Shop on Amazon</a>
      <p class="small muted">Opens Amazon search with “{html.escape(kw)}”.</p></div>""")
    cards.append(f"""
    <div class="card"><h3>eBay • {html.escape(kw)}</h3>
      <p class="muted">Find deals or refurbished picks.</p>
      <a class="btn alt" href="{eby}" rel="nofollow sponsored">Browse on eBay</a></div>""")
    cards.append(f"""
    <div class="card"><h3>Pinterest Inspiration</h3>
      <p class="muted">See what looks good right now.</p>
      <a class="btn" href="{pin}" target="_blank" rel="noopener">Open Pinterest</a></div>""")
    grid = '<section class="grid cards">' + "\n".join(cards) + "</section>"
    back = '<p><a href="index.html">← Back to trends</a></p>'
    return back + grid

def search_page()->str:
    # Minimal client-side search across generated keywords (anchors)
    js = """
<script>
const params = new URLSearchParams(location.search); const q=(params.get('q')||'').toLowerCase();
const list = JSON.parse(localStorage.getItem('tf_keywords')||'[]');
const results = list.filter(k=>k.toLowerCase().includes(q));
document.getElementById('q').textContent = q || '—';
document.getElementById('res').innerHTML = results.map(k=>`<a href="${k.replace(/[^a-z0-9]+/gi,'-').replace(/^-|-$/g,'')}.html">${k}</a>`).join(' ');
</script>
"""
    body = """
<section class="card">
  <h2>Search</h2>
  <p>Results for: <strong id="q">...</strong></p>
  <div id="res" class="kwd"></div>
</section>
"""
    return page_layout("Search • TrendFinder", body) + js

# ------------------------- SOCIAL CSV -------------------------
def write_social_csv(path:str, keywords:list[str], site_base:str):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text","link","image"])
        for kw in keywords:
            slug = slugify(kw)+".html"
            text = f"{kw.title()} finds you didn’t know you needed ✨ #deals #trending #amazonfinds"
            w.writerow([text, urllib.parse.urljoin(site_base, slug), ""])

# ------------------------- BUILD -------------------------
def build_site(out_dir:str, keywords:list[str], amazon_tag:str, ebay_campid:str, ebay_customid:str):
    ensure_dir(out_dir)
    # index
    with open(os.path.join(out_dir,"index.html"),"w",encoding="utf-8") as f:
        f.write(page_layout(SITE_TITLE, index_body(keywords), "Live ideas from today’s internet."))
    # keywords
    for kw in keywords:
        with open(os.path.join(out_dir, slugify(kw)+".html"),"w",encoding="utf-8") as f:
            f.write(page_layout(f"{kw} • TrendFinder",
                                keyword_body(kw, amazon_tag, ebay_campid, ebay_customid),
                                "Shop links include affiliate parameters where available."))
    # search
    with open(os.path.join(out_dir,"search.html"),"w",encoding="utf-8") as f:
        f.write(search_page())
    # small boot script to cache keywords for client search
    boot = f"""<script>localStorage.setItem('tf_keywords', {json.dumps(keywords)});</script>"""
    with open(os.path.join(out_dir,"boot.js"),"w",encoding="utf-8") as f:
        f.write(boot)

# ------------------------- MAIN -------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Affiliate Trend Site (one-file builder)")
    ap.add_argument("--site-dir", default="site", help="output folder for static site")
    ap.add_argument("--amazon-tag", default="", help="your Amazon Associates tag (e.g., mytag-20)")
    ap.add_argument("--ebay-campid", default="", help="eBay Partner Network campaign id (optional)")
    ap.add_argument("--ebay-customid", default="", help="eBay custom id (optional)")
    ap.add_argument("--niches", default="", help="comma-separated seed keywords (fallback)")
    ap.add_argument("--trends", default="", help="two-letter country for Google Trends (e.g., US, GB). Requires pytrends.")
    ap.add_argument("--trend-count", type=int, default=12)
    ap.add_argument("--site-base", default="http://localhost:8080/", help="absolute site base URL for social CSV")
    ap.add_argument("--social-csv", default="social_posts.csv")
    args = ap.parse_args(argv)

    seeds = [s.strip() for s in args.niches.split(",") if s.strip()] if args.niches else None
    kws = get_trending_keywords(args.trends or "US", count=args.trend_count, seed=seeds)
    build_site(args.site_dir, kws, args.amazon_tag, args.ebay_campid, args.ebay_customid)
    write_social_csv(args.social_csv, kws, args.site_base)

    print(f"✔ Built site in {args.site_dir} with {len(kws)} keywords.")
    print(f"✔ Social CSV: {args.social_csv}")
    if not args.amazon_tag:
        print("! Note: No Amazon tag supplied. Add --amazon-tag yourtag-20 for commissions.")
    print("Host the 'site' folder (Netlify/Vercel/S3) or run:  python -m http.server --directory site 8080")

if __name__ == "__main__":
    sys.exit(main())
