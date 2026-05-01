"""
Beslutskollen — Static Site Generator
=======================================
Reads site/data.json and generates:
- Individual HTML pages per decision (SEO, OG tags, canonical URLs)
- sitemap.xml for Google
- RSS feed (feed.xml)
- robots.txt
- 404.html

Run after scraper.py to rebuild the site:
    python3 build_site.py
    python3 build_site.py --base-url https://kommunmonitor.se
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from html import escape

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"
DECISIONS_DIR = SITE_DIR / "beslut"

MONTHS_SV = ["januari","februari","mars","april","maj","juni","juli","augusti","september","oktober","november","december"]
CATS = {
    "bygg":("Bygg","🏗️","#d97706"),"infrastruktur":("Infrastruktur","🛣️","#4f46e5"),
    "skola":("Skola","🏫","#059669"),"budget":("Budget","💰","#2563eb"),
    "miljö":("Miljö","🌿","#16a34a"),"miljo":("Miljö","🌿","#16a34a"),
    "trygghet":("Trygghet","🛡️","#dc2626"),"kultur":("Kultur","🎭","#9333ea"),
    "politik":("Politik","⚖️","#475569"),"regler":("Regler","📜","#b45309"),
    "övrigt":("Övrigt","📋","#94a3b8"),"ovrigt":("Övrigt","📋","#94a3b8"),
}
PC = {"S":"#e8112d","M":"#52bdec","C":"#009933","L":"#006ab3","KD":"#231977",
      "V":"#da291c","SD":"#b8960c","ÖrP":"#f47920","MP":"#83cf39"}
PN = {"S":"Socialdemokraterna","M":"Moderaterna","C":"Centerpartiet","L":"Liberalerna",
      "KD":"Kristdemokraterna","V":"Vänsterpartiet","SD":"Sverigedemokraterna",
      "ÖrP":"Örebropartiet","MP":"Miljöpartiet"}


def fmt_date(ds):
    d = datetime.strptime(ds, "%Y-%m-%d")
    return f"{d.day} {MONTHS_SV[d.month-1]} {d.year}"

def slug(text):
    """Create URL-safe slug from Swedish text."""
    s = text.lower()
    for a,b in [("å","a"),("ä","a"),("ö","o"),("é","e"),("ü","u"),(" ","-")]:
        s = s.replace(a,b)
    s = re.sub(r'[^a-z0-9-]', '', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:80]


def voting_html(v):
    if not v: return ""
    groups = ""
    for label, color, parties in [("JA","#16a34a",v.get("for",[])),("NEJ","#dc2626",v.get("against",[])),("AVSTOD","#94a3b8",v.get("abstained",[]))]:
        if parties:
            badges = " ".join(
                f'<span style="background:{PC.get(p,"#999")};color:#fff;'
                f'font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px;'
                f'" title="{PN.get(p,p)}">{p}</span>'
                for p in parties
            )
            groups += f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px"><span style="color:{color};font-weight:700;font-size:12px;min-width:50px">{label}:</span>{badges}</div>'
    return f'<div style="margin:16px 0"><div style="font-size:12px;font-weight:700;color:#64748b;margin-bottom:8px;letter-spacing:0.4px">RÖSTNING: {escape(v.get("result",""))}</div>{groups}</div>'


GLOSSARY = {
    "motion": "Ett förslag från en eller flera ledamöter. Behandlas av kommunen och leder till ett beslut.",
    "interpellation": "En fråga från en ledamot till en ansvarig politiker, som besvaras i fullmäktige.",
    "votering": "Formell omröstning där varje ledamot registrerar sin röst — används vid oenighet.",
    "bifall": "Förslaget godkändes — beslutet gick igenom.",
    "avslag": "Förslaget avslogs — det röstades ner.",
    "bordläggning": "Beslutet skjuts upp till ett senare möte.",
    "avstod": "Partiet deltog inte aktivt i omröstningen — ofta som markering utan att rösta emot.",
    "reservation": "Formell protest mot ett beslut. Betyder att partiet vill markera sitt motstånd.",
    "KF": "Kommunfullmäktige — kommunens högsta beslutande organ, med folkvalda ledamöter.",
    "KS": "Kommunstyrelsen — leder kommunens arbete och förbereder ärenden åt fullmäktige.",
}

OREBRO_PROTOKOLL_URL = "https://www.orebro.se/kommun--politik/politik--beslut.html"


def decision_page_html(decision, meeting, base_url, all_data):
    d = decision
    m = meeting
    cat_name, cat_emoji, cat_color = CATS.get(d.get("category",""), ("Övrigt","📋","#94a3b8"))
    title = f"{d['headline']} — Beslutskollen"
    desc = d.get("summary", "")[:160]
    canonical = f"{base_url}/beslut/{d['id']}/"
    proto_url = OREBRO_PROTOKOLL_URL

    detail_html = ""
    for para in (d.get("detail","") or d.get("summary","")).split("\n\n"):
        detail_html += f"<p>{escape(para)}</p>\n"

    vote_html = voting_html(d.get("voting"))

    quote_html = ""
    if d.get("quote"):
        quote_html = f'''<blockquote style="margin:20px 0;padding:14px 18px;background:#faf9f7;border-left:3px solid #d4d0cc;border-radius:0 8px 8px 0;font-style:italic;color:#5a5550;line-height:1.7;font-size:15px">
"{escape(d['quote'])}"
<div style="font-style:normal;font-size:12px;color:#8a8a8a;margin-top:6px">Källa: <a href="{OREBRO_PROTOKOLL_URL}" target="_blank" rel="noopener" style="color:#8a8a8a">Originalprotokoll</a>{f", {d['quote_page']}" if d.get('quote_page') else ""}</div>
</blockquote>'''

    # Related decisions
    related_html = ""
    if d.get("tags"):
        related = []
        for om in all_data.get("meetings", []):
            for od in om.get("decisions", []):
                if od["id"] != d["id"] and od.get("tags") and any(t in d["tags"] for t in od["tags"]):
                    related.append((od, om))
        if related:
            items = ""
            for rd, rm in related[:5]:
                items += f'<a href="{base_url}/beslut/{rd["id"]}/" style="display:block;padding:8px 0;border-bottom:1px solid #e0f2fe;color:#0c4a6e;text-decoration:none;font-size:14px"><span style="color:#7dd3fc">{fmt_date(rm["date"])}</span> · {rm.get("meeting_type", rm.get("organ", ""))} · {escape(rd["headline"])}</a>'
            related_html = f'<div style="margin:20px 0;padding:14px 18px;background:#f0f9ff;border-radius:8px;border:1px solid #bae6fd"><div style="font-size:12px;font-weight:700;color:#0369a1;margin-bottom:8px">🔗 RELATERADE BESLUT</div>{items}</div>'

    badges_html = ""
    if d.get("contested"):
        badges_html += '<span style="background:#fef2f2;color:#dc2626;font-size:11px;font-weight:700;padding:3px 10px;border-radius:10px;margin-right:6px">⚡ Omstritt</span>'
    v = d.get("voting",{})
    if v.get("result") == "Enhälligt":
        badges_html += '<span style="background:#f0fdf4;color:#16a34a;font-size:11px;font-weight:700;padding:3px 10px;border-radius:10px;margin-right:6px">✓ Enhälligt</span>'
    if v.get("result","").lower().find("votering") >= 0:
        badges_html += '<span style="background:#fef3c7;color:#d97706;font-size:11px;font-weight:700;padding:3px 10px;border-radius:10px">🗳️ Votering</span>'

    organ = m.get('meeting_type', m.get('organ', ''))
    organ_short = organ.replace('Kommunfullmäktige', 'KF').replace('Kommunstyrelsen', 'KS')

    return f'''<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{escape(d['headline'])}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="article">
<meta property="og:locale" content="sv_SE">
<meta property="og:site_name" content="Beslutskollen">
<meta property="article:published_time" content="{m['date']}T00:00:00+01:00">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{escape(d['headline'])}">
<meta name="twitter:description" content="{escape(desc)}">
<link rel="alternate" type="application/rss+xml" title="Beslutskollen RSS" href="{base_url}/feed.xml">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Beslutskollen", "item": "{base_url}/"}},
    {{"@type": "ListItem", "position": 2, "name": "{organ}", "item": "{base_url}/#beslut"}},
    {{"@type": "ListItem", "position": 3, "name": "{escape(d['headline'][:60])}"}}
  ]
}}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,600&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Instrument Sans',system-ui,sans-serif;background:#f7f5f2;color:#1a1a1a;line-height:1.6}}
a{{color:#0f1f33;text-decoration:none}} ::selection{{background:#0f1f33;color:#fff}}
.wrap{{max-width:700px;margin:0 auto;padding:0 24px}}
header{{background:linear-gradient(160deg,#0a1628,#0f1f33 40%,#1e3a5f);color:#fff;padding:20px 24px}}
header a{{color:#fff;text-decoration:none;font-size:13px;opacity:.7}}
header a:hover{{opacity:1}}
article p{{font-size:16px;line-height:1.8;color:#4a4a4a;margin-bottom:14px}}
.tooltip{{position:relative;border-bottom:1px dotted #8a8a8a;cursor:help}}
.tooltip:hover::after{{content:attr(data-tip);position:absolute;bottom:100%;left:0;background:#0f1f33;color:#fff;padding:6px 10px;border-radius:6px;font-size:12px;white-space:normal;width:240px;z-index:10;line-height:1.4;font-weight:400}}
</style>
</head>
<body>
<header>
<div class="wrap">
<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:13px">
<a href="{base_url}/" style="opacity:.6">📋 Beslutskollen</a>
<span style="opacity:.3">›</span>
<a href="{base_url}/#beslut" style="opacity:.6">Beslut</a>
<span style="opacity:.3">›</span>
<span style="opacity:.8">{organ_short} {fmt_date(m['date'])}</span>
</div>
<h1 style="font-family:'Fraunces',serif;font-size:clamp(22px,3vw,28px);font-weight:400;line-height:1.3">{escape(d['headline'])}</h1>
</div>
</header>

<main class="wrap" style="padding-top:20px;padding-bottom:60px">
<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap">
<span style="background:{cat_color};color:#fff;font-size:12px;font-weight:600;padding:3px 10px;border-radius:6px">{cat_emoji} {cat_name}</span>
<span style="font-size:13px;color:#8a8a8a">{organ} · {fmt_date(m['date'])}</span>
{f'<span style="font-size:13px;color:#8a8a8a">· {d["paragraph_ref"]}</span>' if d.get("paragraph_ref") else ""}
{f'<span style="font-size:13px;color:#8a8a8a">· 📍 {escape(d["location"])}</span>' if d.get("location") else ""}
</div>

<div style="margin-bottom:16px">{badges_html}</div>

<p style="font-size:16px;color:#4a4a4a;line-height:1.7;margin-bottom:24px;font-weight:500">{escape(d.get('summary',''))}</p>

<article style="border-top:1px solid #e8e4df;padding-top:20px">
{detail_html}
</article>

{vote_html}
{quote_html}
{related_html}

<div style="margin-top:24px;display:flex;flex-wrap:wrap;gap:8px;padding-top:16px;border-top:1px solid #e8e4df">
<a href="{proto_url}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:5px;padding:8px 16px;border-radius:8px;background:#0f1f33;color:#fff;font-size:13px;font-weight:500;text-decoration:none">📄 Hitta originalprotokollet{f" ({d['paragraph_ref']})" if d.get('paragraph_ref') else ""}</a>
<button onclick="share()" style="display:inline-flex;align-items:center;gap:5px;padding:8px 16px;border-radius:8px;border:1px solid #e8e4df;background:#fff;font-size:13px;cursor:pointer;font-family:inherit;color:#8a8a8a">🔗 Dela detta beslut</button>
</div>
</main>

<footer style="border-top:1px solid #e8e4df;padding:20px 24px;text-align:center;font-size:11px;color:#8a8a8a">
<p>Beslutskollen sammanfattar offentliga protokoll med AI. Kan innehålla fel — kontrollera alltid <a href="{OREBRO_PROTOKOLL_URL}" target="_blank" rel="noopener" style="text-decoration:underline;color:#8a8a8a">originalprotokollet</a>.</p>
<p style="margin-top:4px"><a href="{base_url}/" style="color:#8a8a8a">Startsida</a> · <a href="{base_url}/feed.xml" style="color:#8a8a8a">RSS</a> · <a href="{base_url}/parti/" style="color:#8a8a8a">Partier</a> · <a href="{base_url}/insikter/" style="color:#8a8a8a">Insikter</a></p>
</footer>

<script>
async function share(){{
  const url="{canonical}";
  const title="{escape(d['headline']).replace('"','&quot;')}";
  if(navigator.share)try{{await navigator.share({{title,url}})}}catch{{}}
  else{{navigator.clipboard.writeText(url);event.target.textContent="✓ Länk kopierad!";setTimeout(()=>event.target.textContent="🔗 Dela detta beslut",2000)}}
}}
</script>
<script data-goatcounter="https://beslutskollen.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body>
</html>'''


def generate_sitemap(decisions_with_meetings, base_url):
    urls = [f'<url><loc>{base_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>']
    # Section pages
    for section in ["insikter/", "ekonomi/", "parti/", "omrade/", "press/"]:
        urls.append(f'<url><loc>{base_url}/{section}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    # Individual decision pages
    for d, m in decisions_with_meetings:
        urls.append(f'<url><loc>{base_url}/beslut/{d["id"]}/</loc><lastmod>{m["date"]}</lastmod><priority>0.8</priority></url>')
    # Individual party pages
    for party in PC:
        slug_p = party.lower().replace("ö","o")
        urls.append(f'<url><loc>{base_url}/parti/{slug_p}/</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"".join(urls)}
</urlset>'''


def generate_rss(decisions_with_meetings, base_url):
    items = ""
    for d, m in decisions_with_meetings[:30]:
        cat_name = CATS.get(d.get("category",""),("Övrigt",))[0]
        items += f'''<item>
<title>{escape(d["headline"])}</title>
<link>{base_url}/beslut/{d["id"]}/</link>
<guid>{base_url}/beslut/{d["id"]}/</guid>
<pubDate>{datetime.strptime(m["date"],"%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 +0100")}</pubDate>
<description>{escape(d.get("summary",""))}</description>
<category>{cat_name}</category>
<source url="{m.get("source_url","")}">Örebro kommun</source>
</item>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>Beslutskollen — Örebro</title>
<link>{base_url}/</link>
<description>AI-sammanfattningar av beslut från Örebro kommun</description>
<language>sv</language>
<atom:link href="{base_url}/feed.xml" rel="self" type="application/rss+xml"/>
<lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0100")}</lastBuildDate>
{items}
</channel>
</rss>'''


def generate_robots(base_url):
    return f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""


def generate_404(base_url):
    return f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sidan hittades inte — Beslutskollen</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400&family=Instrument+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>body{{font-family:'Instrument Sans',system-ui,sans-serif;background:#f7f5f2;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;color:#8a8a8a}}</style>
</head><body><div><div style="font-size:64px;margin-bottom:16px">📋</div><h1 style="font-family:'Fraunces',serif;font-size:24px;color:#1a1a1a;margin-bottom:8px;font-weight:300">Sidan hittades inte</h1>
<p>Beslutet du letar efter kanske har flyttats eller tagits bort.</p>
<a href="{base_url}/" style="display:inline-block;margin-top:16px;padding:10px 24px;background:#0f1f33;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">← Alla beslut</a></div></body></html>'''


def main():
    parser = argparse.ArgumentParser(description="Build static site")
    parser.add_argument("--base-url", default="https://lingabton.github.io/kommun-monitor", help="Base URL for the site")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    # Load data
    data_path = SITE_DIR / "data.json"
    if not data_path.exists():
        print("❌ No site/data.json found. Run scraper.py first.")
        return

    data = json.loads(data_path.read_text("utf-8"))
    print(f"📊 {data.get('total_meetings',0)} meetings, {data.get('total_decisions',0)} decisions")

    # Collect all decisions with their meeting context
    all_decisions = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            all_decisions.append((d, m))

    # Sort by date descending
    all_decisions.sort(key=lambda x: x[1]["date"], reverse=True)

    # Generate individual decision pages
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    for d, m in all_decisions:
        page_dir = DECISIONS_DIR / d["id"]
        page_dir.mkdir(parents=True, exist_ok=True)
        html = decision_page_html(d, m, base, data)
        (page_dir / "index.html").write_text(html, encoding="utf-8")

    print(f"📄 {len(all_decisions)} decision pages generated")

    # Sitemap
    (SITE_DIR / "sitemap.xml").write_text(generate_sitemap(all_decisions, base), "utf-8")
    print("🗺️  sitemap.xml")

    # RSS
    (SITE_DIR / "feed.xml").write_text(generate_rss(all_decisions, base), "utf-8")
    print("📡 feed.xml")

    # Robots
    (SITE_DIR / "robots.txt").write_text(generate_robots(base), "utf-8")
    print("🤖 robots.txt")

    # 404
    (SITE_DIR / "404.html").write_text(generate_404(base), "utf-8")
    print("🚫 404.html")

    print(f"\n✅ Site built! {len(all_decisions)} pages in site/beslut/")


if __name__ == "__main__":
    main()
