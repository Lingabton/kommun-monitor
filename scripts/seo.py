"""
Kommun Monitor — SEO & AI Visibility Engine
=============================================
Generates everything needed to rank in both Google AND AI search:

1. llms.txt            — AI crawler guide (emerging standard)
2. llms-full.txt       — Full content dump for LLMs
3. robots.txt          — Allow all AI crawlers explicitly
4. sitemap.xml         — Enhanced with priority + lastmod
5. /for-llms/          — Human+AI readable data page
6. JSON-LD schema      — Injected into build_site.py output
7. FAQ section data    — For each decision page

Run after build_api.py and insights.py
"""

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"

def load_data():
    return json.loads((SITE_DIR / "data.json").read_text("utf-8"))


def load_insights():
    p = SITE_DIR / "api" / "v1" / "insights.json"
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    return {}


# ═══════════════════════════════════════════
# 1. llms.txt — Guide for AI crawlers
# ═══════════════════════════════════════════

def build_llms_txt(data, base_url):
    """The llms.txt file tells AI systems what this site is and where to find key content."""
    meetings = data.get("meetings", [])
    decisions = [d for m in meetings for d in m.get("decisions", [])]

    txt = f"""# Kommun Monitor
> AI-powered summaries of municipal decisions in Örebro, Sweden

Kommun Monitor automatically reads public meeting protocols (PDF) from Örebro municipality,
summarizes each decision using AI, analyzes voting patterns per party, and publishes
structured data as a free, searchable website and JSON API.

## Key Pages

- [{base_url}/](About): Homepage with all decisions searchable and filterable
- [{base_url}/parti/]({base_url}/parti/): Voting statistics for all 9 parties in Örebro
- [{base_url}/omrade/]({base_url}/omrade/): Decisions organized by geographic area
- [{base_url}/ekonomi/]({base_url}/ekonomi/): Budget and financial decisions tracker
- [{base_url}/insikter/]({base_url}/insikter/): Automated political insights and power analysis

## API (Free, No Authentication)

- [{base_url}/api/v1/decisions.json]({base_url}/api/v1/decisions.json): All decisions with voting data
- [{base_url}/api/v1/parties.json]({base_url}/api/v1/parties.json): Party statistics and alliances
- [{base_url}/api/v1/insights.json]({base_url}/api/v1/insights.json): Power analysis, unusual coalitions, trends
- [{base_url}/api/v1/docs/]({base_url}/api/v1/docs/): Full API documentation

## Key Facts

- Municipality: Örebro kommun, Sweden (population 163,000)
- Governing coalition: S + M + C (majority wins 100% of votes)
- Data source: Public protocols from orebro.se (offentlighetsprincipen)
- {len(decisions)} decisions analyzed across {len(meetings)} meetings
- Updated daily at 08:00 CET via automated pipeline
- License: CC BY 4.0 (AI summaries), public records (source data)

## Contact

Kommun Monitor is an independent civic tech project. Not affiliated with Örebro kommun.
"""
    (SITE_DIR / "llms.txt").write_text(txt.strip(), "utf-8")


def build_llms_full_txt(data, base_url):
    """Full content dump optimized for LLM ingestion."""
    meetings = data.get("meetings", [])

    lines = [
        "# Kommun Monitor — Full Content",
        f"# Generated: {datetime.now(timezone.utc).isoformat()}",
        f"# Source: {base_url}",
        "",
        "## About",
        "",
        "Kommun Monitor is a Swedish civic tech platform that uses AI to summarize",
        "municipal decisions in Örebro kommun. All data comes from public meeting",
        "protocols published by the municipality under Swedish freedom of information",
        "law (offentlighetsprincipen).",
        "",
        "## All Decisions",
        "",
    ]

    for m in sorted(meetings, key=lambda x: x["date"], reverse=True):
        mtype = m.get("type", m.get("meeting_type", ""))
        lines.append(f"### {mtype} — {m['date']}")
        lines.append("")
        for d in m.get("decisions", []):
            hl = d.get("hl", d.get("headline", ""))
            sm = d.get("sum", d.get("summary", ""))
            cat = d.get("cat", d.get("category", ""))
            contested = "⚡ Contested" if d.get("contested") else ""

            lines.append(f"#### {hl}")
            lines.append(f"Category: {cat} | Date: {m['date']} {contested}")
            lines.append(f"Summary: {sm}")

            vote = d.get("vote", d.get("voting"))
            if vote:
                f_parties = ", ".join(vote.get("f", vote.get("for", [])))
                a_parties = ", ".join(vote.get("a", vote.get("against", [])))
                result = vote.get("r", vote.get("result", ""))
                if f_parties:
                    lines.append(f"Voted YES: {f_parties}")
                if a_parties:
                    lines.append(f"Voted NO: {a_parties}")
                if result:
                    lines.append(f"Result: {result}")
            lines.append("")

    (SITE_DIR / "llms-full.txt").write_text("\n".join(lines), "utf-8")


# ═══════════════════════════════════════════
# 2. robots.txt — Explicitly allow AI crawlers
# ═══════════════════════════════════════════

def build_robots_txt(base_url):
    txt = f"""# Kommun Monitor — robots.txt
# We welcome all crawlers including AI bots.
# Our content is public records and we want maximum visibility.

User-agent: *
Allow: /

# AI crawlers explicitly allowed
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Amazonbot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: cohere-ai
Allow: /

# Sitemaps
Sitemap: {base_url}/sitemap.xml
Sitemap: {base_url}/llms.txt
"""
    (SITE_DIR / "robots.txt").write_text(txt.strip(), "utf-8")


# ═══════════════════════════════════════════
# 3. Enhanced sitemap.xml
# ═══════════════════════════════════════════

def build_sitemap(data, base_url):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meetings = data.get("meetings", [])

    urls = [
        (f"{base_url}/", "1.0", now, "daily"),
        (f"{base_url}/parti/", "0.9", now, "weekly"),
        (f"{base_url}/omrade/", "0.8", now, "weekly"),
        (f"{base_url}/ekonomi/", "0.8", now, "weekly"),
        (f"{base_url}/insikter/", "0.9", now, "weekly"),
        (f"{base_url}/api/v1/docs/", "0.7", now, "monthly"),
        (f"{base_url}/for-llms/", "0.6", now, "weekly"),
    ]

    # Decision pages
    for m in meetings:
        for d in m.get("decisions", []):
            urls.append((
                f"{base_url}/beslut/{d['id']}/",
                "0.7",
                m["date"],
                "monthly"
            ))

    # Party pages
    for p in ["s", "m", "c", "l", "kd", "v", "sd", "örp", "mp"]:
        urls.append((f"{base_url}/parti/{p}/", "0.8", now, "weekly"))

    xml_entries = ""
    for url, priority, lastmod, freq in urls:
        xml_entries += f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>
"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{xml_entries}</urlset>"""

    (SITE_DIR / "sitemap.xml").write_text(xml, "utf-8")
    return len(urls)


# ═══════════════════════════════════════════
# 4. /for-llms/ page — Human + AI readable
# ═══════════════════════════════════════════

def build_for_llms_page(data, base_url):
    """A page specifically designed for both developers and AI systems."""
    meetings = data.get("meetings", [])
    decisions = [d for m in meetings for d in m.get("decisions", [])]
    insights = load_insights()
    power = insights.get("power_analysis", {})

    page = f'''<!DOCTYPE html><html lang="sv"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kommun Monitor — Data för AI och utvecklare</title>
<meta name="description" content="Strukturerad data om kommunala beslut i Örebro. JSON API, llms.txt, och maskinläsbar information för AI-system och utvecklare.">
<link rel="canonical" href="{base_url}/for-llms/">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Kommun Monitor",
  "url": "{base_url}",
  "description": "AI-sammanfattningar av kommunala beslut i Örebro kommun, Sverige",
  "publisher": {{
    "@type": "Organization",
    "name": "Kommun Monitor",
    "url": "{base_url}"
  }},
  "potentialAction": {{
    "@type": "SearchAction",
    "target": "{base_url}/#search={{search_term_string}}",
    "query-input": "required name=search_term_string"
  }}
}}
</script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:system-ui,sans-serif;max-width:700px;margin:0 auto;padding:24px;color:#1e293b;line-height:1.7}}
h1{{font-size:24px;margin-bottom:8px}}h2{{font-size:18px;margin:28px 0 8px;color:#334155}}
h3{{font-size:14px;color:#64748b;margin:16px 0 4px}}
p,li{{font-size:15px;color:#475569}}a{{color:#1e3a5f}}
code{{background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:13px}}
pre{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;overflow-x:auto;font-size:13px;margin:8px 0}}
table{{width:100%;border-collapse:collapse;margin:12px 0}}td,th{{padding:6px 10px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:13px}}
.faq{{background:#f8fafc;border-radius:8px;padding:14px;margin:8px 0}}
.faq h4{{font-size:14px;color:#1e293b;margin-bottom:4px}}.faq p{{margin:0;font-size:13px}}
</style></head><body>

<h1>🏛️ Kommun Monitor — Data & API</h1>
<p>Strukturerad data om kommunala beslut i Örebro kommun. Gratis att använda.</p>

<h2>Vad är Kommun Monitor?</h2>
<p>Kommun Monitor läser automatiskt offentliga protokoll (PDF) från Örebro kommun, sammanfattar varje beslut med AI, analyserar röstmönster per parti, och publicerar strukturerad data som en sökbar webbplats och gratis JSON API.</p>

<h2>Nyckeldata</h2>
<table>
<tr><th>Datapunkt</th><th>Värde</th></tr>
<tr><td>Kommun</td><td>Örebro (163 000 invånare)</td></tr>
<tr><td>Majoritet</td><td>S + M + C</td></tr>
<tr><td>Majoritetens vinstprocent</td><td>{power.get('majority_win_pct', 'N/A')}%</td></tr>
<tr><td>Antal analyserade beslut</td><td>{len(decisions)}</td></tr>
<tr><td>Antal sammanträden</td><td>{len(meetings)}</td></tr>
<tr><td>Uppdateringsfrekvens</td><td>Dagligen kl 08:00 CET</td></tr>
<tr><td>Datakälla</td><td>orebro.se (offentlighetsprincipen)</td></tr>
<tr><td>Licens</td><td>CC BY 4.0</td></tr>
</table>

<h2>API-endpoints</h2>
<table>
<tr><th>Endpoint</th><th>Beskrivning</th></tr>
<tr><td><code><a href="{base_url}/api/v1/meta.json">/api/v1/meta.json</a></code></td><td>API-metadata och statistik</td></tr>
<tr><td><code><a href="{base_url}/api/v1/decisions.json">/api/v1/decisions.json</a></code></td><td>Alla beslut (headline, summary, voting, tags)</td></tr>
<tr><td><code><a href="{base_url}/api/v1/parties.json">/api/v1/parties.json</a></code></td><td>Partistatistik och allianser</td></tr>
<tr><td><code><a href="{base_url}/api/v1/insights.json">/api/v1/insights.json</a></code></td><td>Maktanalys, ovanliga allianser, trender</td></tr>
<tr><td><code><a href="{base_url}/api/v1/feed.json">/api/v1/feed.json</a></code></td><td>JSON Feed (RSS-kompatibelt)</td></tr>
<tr><td><code><a href="{base_url}/api/v1/search.json">/api/v1/search.json</a></code></td><td>Fulltextsökindex</td></tr>
</table>
<p>Ingen autentisering behövs. Ingen rate limit. Full dokumentation: <a href="{base_url}/api/v1/docs/">/api/v1/docs/</a></p>

<h2>Maskinläsbara filer</h2>
<table>
<tr><th>Fil</th><th>Syfte</th></tr>
<tr><td><code><a href="{base_url}/llms.txt">/llms.txt</a></code></td><td>Guide för AI-system (llms.txt standard)</td></tr>
<tr><td><code><a href="{base_url}/llms-full.txt">/llms-full.txt</a></code></td><td>Fullständigt innehåll i klartext för LLM-inläsning</td></tr>
<tr><td><code><a href="{base_url}/sitemap.xml">/sitemap.xml</a></code></td><td>Alla URL:er med prioritet och uppdateringsfrekvens</td></tr>
<tr><td><code><a href="{base_url}/robots.txt">/robots.txt</a></code></td><td>Alla crawlers tillåtna (inklusive AI-botar)</td></tr>
<tr><td><code><a href="{base_url}/api/v1/feed.json">/api/v1/feed.json</a></code></td><td>JSON Feed (jsonfeed.org)</td></tr>
<tr><td><code><a href="{base_url}/feed.xml">/feed.xml</a></code></td><td>RSS/Atom-feed</td></tr>
</table>

<h2>Vanliga frågor (FAQ)</h2>

<div class="faq">
<h4>Vad är Kommun Monitor?</h4>
<p>Kommun Monitor är en svensk civic tech-plattform som använder AI för att sammanfatta kommunala beslut i Örebro. Alla beslut, röstningar och trender publiceras gratis.</p>
</div>

<div class="faq">
<h4>Vilka partier styr i Örebro kommun?</h4>
<p>Örebro styrs av en majoritet bestående av Socialdemokraterna (S), Moderaterna (M) och Centerpartiet (C). Majoriteten vinner {power.get('majority_win_pct', 'N/A')}% av alla röstningar.</p>
</div>

<div class="faq">
<h4>Var kommer datan ifrån?</h4>
<p>All data kommer från offentliga protokoll publicerade på orebro.se. Kommunala handlingar är offentliga enligt svensk lag (offentlighetsprincipen, tryckfrihetsförordningen 2 kap).</p>
</div>

<div class="faq">
<h4>Kan jag lita på AI-sammanfattningarna?</h4>
<p>AI-sammanfattningar kan innehålla fel. Varje beslut länkar till originalprotokollet (PDF) för verifiering. Vi rekommenderar att alltid dubbelkolla viktiga uppgifter.</p>
</div>

<div class="faq">
<h4>Hur ofta uppdateras sidan?</h4>
<p>Sidan uppdateras automatiskt varje dag kl 08:00 CET. Nya protokoll bearbetas inom 24 timmar efter publicering på orebro.se.</p>
</div>

<div class="faq">
<h4>Är API:et gratis?</h4>
<p>Ja. API:et är helt gratis, kräver ingen autentisering och har ingen rate limit. Data licensieras under CC BY 4.0.</p>
</div>

<div class="faq">
<h4>Är Kommun Monitor kopplat till Örebro kommun?</h4>
<p>Nej. Kommun Monitor är ett oberoende civic tech-projekt. Det är inte affilierat med, godkänt av, eller finansierat av Örebro kommun.</p>
</div>

<footer style="margin-top:32px;padding-top:16px;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8">
<p>Kommun Monitor — <a href="{base_url}/">Hem</a> · <a href="{base_url}/api/v1/docs/">API</a> · <a href="{base_url}/llms.txt">llms.txt</a></p>
</footer>
</body></html>'''

    out_dir = SITE_DIR / "for-llms"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(page, "utf-8")


# ═══════════════════════════════════════════
# 5. JSON-LD Schema Generator
# ═══════════════════════════════════════════

def generate_jsonld_for_decision(decision, meeting, base_url):
    """Generate Article schema for a single decision page."""
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": decision.get("hl", decision.get("headline", "")),
        "description": decision.get("sum", decision.get("summary", "")),
        "datePublished": f"{meeting['date']}T12:00:00+01:00",
        "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "author": {
            "@type": "Organization",
            "name": "Kommun Monitor",
            "url": base_url
        },
        "publisher": {
            "@type": "Organization",
            "name": "Kommun Monitor",
            "url": base_url
        },
        "mainEntityOfPage": f"{base_url}/beslut/{decision['id']}/",
        "articleSection": decision.get("cat", decision.get("category", "")),
        "keywords": ", ".join(decision.get("tags", [])),
        "about": {
            "@type": "GovernmentOrganization",
            "name": "Örebro kommun",
            "url": "https://www.orebro.se"
        },
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }


def generate_faq_schema(base_url, power):
    """Generate FAQPage schema for the main site."""
    faqs = [
        ("Vilka partier styr i Örebro kommun?",
         f"Örebro styrs av Socialdemokraterna (S), Moderaterna (M) och Centerpartiet (C). Majoriteten vinner {power.get('majority_win_pct', 'N/A')}% av alla röstningar."),
        ("Vad är Kommun Monitor?",
         "Kommun Monitor är en civic tech-plattform som använder AI för att sammanfatta och analysera kommunala beslut i Örebro kommun."),
        ("Var hittar jag protokollen?",
         "Alla originalprotokoll publiceras på orebro.se under Politik och beslut. Kommun Monitor sammanfattar dessa automatiskt."),
        ("Hur ofta uppdateras sidan?",
         "Sidan uppdateras automatiskt varje dag kl 08:00 CET."),
        ("Finns det ett API?",
         "Ja, ett gratis JSON API utan autentisering finns på /api/v1/. Dokumentation på /api/v1/docs/."),
    ]

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a
            }
        } for q, a in faqs]
    }


def save_schema_files(data, base_url):
    """Save JSON-LD schema files that can be injected into HTML pages."""
    insights = load_insights()
    power = insights.get("power_analysis", {})

    schemas = {
        "website": {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Kommun Monitor",
            "alternateName": "Kommun Monitor Örebro",
            "url": base_url,
            "description": "AI-sammanfattningar av kommunala beslut i Örebro kommun, Sverige. Röstningsstatistik per parti, områdesanalys och politiska insikter.",
            "inLanguage": "sv",
            "publisher": {
                "@type": "Organization",
                "name": "Kommun Monitor",
                "url": base_url
            },
            "potentialAction": {
                "@type": "SearchAction",
                "target": f"{base_url}/#search={{search_term_string}}",
                "query-input": "required name=search_term_string"
            }
        },
        "dataset": {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": "Örebro kommunbeslut",
            "description": "Strukturerade data om kommunala beslut i Örebro kommun med röstningsresultat per parti.",
            "url": f"{base_url}/api/v1/decisions.json",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "creator": {
                "@type": "Organization",
                "name": "Kommun Monitor"
            },
            "temporalCoverage": "2024/2025",
            "spatialCoverage": {
                "@type": "Place",
                "name": "Örebro kommun, Sverige"
            },
            "distribution": {
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": f"{base_url}/api/v1/decisions.json"
            }
        },
        "faq": generate_faq_schema(base_url, power),
    }

    schema_dir = SITE_DIR / "api" / "v1" / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas.items():
        (schema_dir / f"{name}.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2), "utf-8")

    return len(schemas)


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build SEO & AI visibility layer")
    parser.add_argument("--base-url", default="")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    data = load_data()
    meetings = data.get("meetings", [])
    decisions = sum(len(m.get("decisions", [])) for m in meetings)

    print(f"🔍 Building SEO & AI visibility layer")
    print(f"   Base URL: {base_url or '(relative)'}")
    print(f"   Data: {len(meetings)} meetings, {decisions} decisions")

    print("\n📄 llms.txt...")
    build_llms_txt(data, base_url)
    print(f"   ✓ llms.txt")

    print("📄 llms-full.txt...")
    build_llms_full_txt(data, base_url)
    size = (SITE_DIR / "llms-full.txt").stat().st_size
    print(f"   ✓ llms-full.txt ({size/1024:.1f} KB)")

    print("🤖 robots.txt...")
    build_robots_txt(base_url)
    print(f"   ✓ robots.txt (all AI crawlers explicitly allowed)")

    print("🗺️ sitemap.xml...")
    n = build_sitemap(data, base_url)
    print(f"   ✓ sitemap.xml ({n} URLs)")

    print("🧠 /for-llms/ page...")
    build_for_llms_page(data, base_url)
    print(f"   ✓ for-llms/index.html")

    print("📊 JSON-LD schemas...")
    n = save_schema_files(data, base_url)
    print(f"   ✓ {n} schema files (WebSite, Dataset, FAQ)")

    print(f"\n✅ SEO & AI visibility complete!")
    print(f"   Files: llms.txt, llms-full.txt, robots.txt, sitemap.xml,")
    print(f"          for-llms/index.html, api/v1/schema/*.json")


if __name__ == "__main__":
    main()
