"""
Beslutskollen — API Builder
==============================
Generates a static REST-like JSON API from site/data.json.
Served directly from GitHub Pages at /api/v1/...

Also generates OpenAPI spec and developer documentation.

Endpoints generated:
  /api/v1/meta.json                    — API metadata, stats, last updated
  /api/v1/municipalities.json          — List of available municipalities
  /api/v1/meetings.json                — All meetings (summary)
  /api/v1/meetings/{id}.json           — Single meeting with all decisions
  /api/v1/decisions.json               — All decisions (flat list)
  /api/v1/decisions/{id}.json          — Single decision with full detail
  /api/v1/parties.json                 — Party profiles + vote stats
  /api/v1/parties/{abbr}.json          — Single party detail
  /api/v1/areas.json                   — Area/stadsdel overview
  /api/v1/search.json                  — Full search index (for client-side search)
  /api/v1/feed.json                    — JSON Feed (RFC) for readers/apps
  /api/v1/docs/index.html              — Interactive API documentation

Usage:
  python3 build_api.py
  python3 build_api.py --base-url "https://user.github.io/kommun-monitor"
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from html import escape

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"
API_DIR = SITE_DIR / "api" / "v1"

VERSION = "1.0.0"
API_NAME = "Beslutskollen API"


def load_data():
    return json.loads((SITE_DIR / "data.json").read_text("utf-8"))


def load_parties():
    p = SITE_DIR / "parties.json"
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    return {}


def write_json(path, data):
    """Write JSON with consistent formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), "utf-8")
    return path


def generate_etag(data):
    """Generate ETag from data content."""
    return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:12]


def build_meta(data, base_url):
    """Build API metadata endpoint."""
    meetings = data.get("meetings", [])
    all_decisions = [d for m in meetings for d in m.get("decisions", [])]
    dates = [m["date"] for m in meetings]

    municipalities = set()
    for m in meetings:
        # Extract municipality from meeting type or default
        municipalities.add("orebro")

    meta = {
        "api": API_NAME,
        "version": VERSION,
        "base_url": f"{base_url}/api/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "municipalities": len(municipalities),
            "meetings": len(meetings),
            "decisions": len(all_decisions),
            "contested_decisions": len([d for d in all_decisions if d.get("contested")]),
            "parties_tracked": 9,
            "date_range": {
                "earliest": min(dates) if dates else None,
                "latest": max(dates) if dates else None,
            }
        },
        "endpoints": {
            "meta": "/api/v1/meta.json",
            "municipalities": "/api/v1/municipalities.json",
            "meetings": "/api/v1/meetings.json",
            "meeting_detail": "/api/v1/meetings/{id}.json",
            "decisions": "/api/v1/decisions.json",
            "decision_detail": "/api/v1/decisions/{id}.json",
            "parties": "/api/v1/parties.json",
            "party_detail": "/api/v1/parties/{abbr}.json",
            "areas": "/api/v1/areas.json",
            "search_index": "/api/v1/search.json",
            "json_feed": "/api/v1/feed.json",
            "docs": "/api/v1/docs/",
        },
        "rate_limits": {
            "static_api": "Unlimited (static files, no rate limit)",
            "note": "This is a static JSON API. All data is pre-generated.",
        },
        "license": {
            "data": "Swedish public records (offentlighetsprincipen). Free to use.",
            "api": "CC BY 4.0 — attribute Beslutskollen",
            "note": "AI-generated summaries may contain errors. Always verify against original protocols.",
        }
    }
    write_json(API_DIR / "meta.json", meta)
    return meta


def build_municipalities(data, base_url):
    """Build municipalities endpoint."""
    # For now, just Örebro. Structure supports multi-kommun.
    municipalities = [
        {
            "id": "orebro",
            "name": "Örebro kommun",
            "population": 163_000,
            "county": "Örebro län",
            "website": "https://www.orebro.se",
            "protocols_url": "https://www.orebro.se/kommun--politik/politik--beslut.html",
            "meetings_count": len(data.get("meetings", [])),
            "decisions_count": sum(len(m.get("decisions", [])) for m in data.get("meetings", [])),
            "organs": ["Kommunfullmäktige", "Kommunstyrelsen"],
            "api_url": f"{base_url}/api/v1/meetings.json?municipality=orebro",
        }
    ]
    write_json(API_DIR / "municipalities.json", {
        "count": len(municipalities),
        "municipalities": municipalities,
    })


def build_meetings(data, base_url):
    """Build meetings list + individual meeting endpoints."""
    meetings_summary = []
    for m in data.get("meetings", []):
        summary = {
            "id": m.get("id", f"{m['date']}_{m.get('organ','')}"),
            "date": m["date"],
            "type": m.get("type", m.get("meeting_type", "")),
            "municipality": "orebro",
            "headline": m.get("headline", m.get("summary_headline", "")),
            "decisions_count": len(m.get("decisions", [])),
            "contested_count": len([d for d in m.get("decisions", []) if d.get("contested")]),
            "source_url": m.get("url", m.get("source_url", "")),
            "api_url": f"{base_url}/api/v1/meetings/{m.get('id', f"{m['date']}_{m.get('organ','')}")}.json",
        }
        meetings_summary.append(summary)

        # Individual meeting endpoint
        meeting_detail = {
            **m,
            "municipality": "orebro",
            "_links": {
                "self": f"{base_url}/api/v1/meetings/{m.get('id', f"{m['date']}_{m.get('organ','')}")}.json",
                "decisions": [f"{base_url}/api/v1/decisions/{d['id']}.json" for d in m.get("decisions", [])],
                "web_url": f"{base_url}/#meeting-{m.get('id', f"{m['date']}_{m.get('organ','')}")}",
            }
        }
        write_json(API_DIR / "meetings" / f"{m.get('id', f"{m['date']}_{m.get('organ','')}")}.json", meeting_detail)

    write_json(API_DIR / "meetings.json", {
        "count": len(meetings_summary),
        "meetings": sorted(meetings_summary, key=lambda x: x["date"], reverse=True),
    })


def build_decisions(data, base_url):
    """Build flat decisions list + individual decision endpoints."""
    all_decisions = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            flat = {
                **d,
                "meeting_id": m.get("id", f"{m['date']}_{m.get('organ','')}"),
                "meeting_date": m["date"],
                "meeting_type": m.get("type", m.get("meeting_type", "")),
                "municipality": "orebro",
                "source_url": m.get("url", m.get("source_url", "")),
            }
            all_decisions.append(flat)

            # Compact summary for list
            decision_summary = {
                "id": d["id"],
                "headline": d.get("hl", d.get("headline", "")),
                "summary": d.get("sum", d.get("summary", "")),
                "category": d.get("cat", d.get("category", "")),
                "contested": d.get("contested", False),
                "date": m["date"],
                "meeting_type": m.get("type", m.get("meeting_type", "")),
                "tags": d.get("tags", []),
                "location": d.get("loc", d.get("location")),
                "api_url": f"{base_url}/api/v1/decisions/{d['id']}.json",
                "web_url": f"{base_url}/beslut/{d['id']}/",
            }
            all_decisions[-1]["_summary"] = decision_summary

            # Individual decision endpoint (full detail)
            # Normalize field names for API consistency
            decision_detail = {
                "id": d["id"],
                "headline": d.get("hl", d.get("headline", "")),
                "summary": d.get("sum", d.get("summary", "")),
                "detail": d.get("detail", ""),
                "category": d.get("cat", d.get("category", "")),
                "contested": d.get("contested", False),
                "location": d.get("loc", d.get("location")),
                "paragraph_ref": d.get("ref", d.get("paragraph_ref", "")),
                "tags": d.get("tags", []),
                "voting": None,
                "quote": d.get("quote"),
                "quote_page": d.get("qp", d.get("quote_page")),
                "meeting": {
                    "id": m.get("id", f"{m['date']}_{m.get('organ','')}"),
                    "date": m["date"],
                    "type": m.get("type", m.get("meeting_type", "")),
                    "source_url": m.get("url", m.get("source_url", "")),
                },
                "municipality": "orebro",
                "_links": {
                    "self": f"{base_url}/api/v1/decisions/{d['id']}.json",
                    "meeting": f"{base_url}/api/v1/meetings/{m.get('id', f"{m['date']}_{m.get('organ','')}")}.json",
                    "web_url": f"{base_url}/beslut/{d['id']}/",
                }
            }

            # Normalize voting data
            vote = d.get("vote", d.get("voting"))
            if vote:
                decision_detail["voting"] = {
                    "for": vote.get("f", vote.get("for", [])),
                    "against": vote.get("a", vote.get("against", [])),
                    "abstained": vote.get("ab", vote.get("abstained", [])),
                    "result": vote.get("r", vote.get("result", "")),
                }

            write_json(API_DIR / "decisions" / f"{d['id']}.json", decision_detail)

    # Summary list (without full detail to keep payload small)
    decisions_list = [d["_summary"] for d in all_decisions]
    write_json(API_DIR / "decisions.json", {
        "count": len(decisions_list),
        "decisions": sorted(decisions_list, key=lambda x: x["date"], reverse=True),
    })


def build_parties(base_url):
    """Build party endpoints from parties.json."""
    parties = load_parties()
    if not parties:
        return

    summary = []
    for abbr, p in parties.items():
        if p.get("total_votes", 0) == 0:
            continue
        s = {
            "abbr": abbr,
            "name": p.get("name", ""),
            "color": p.get("color", "#999"),
            "position": p.get("position", ""),
            "ideology": p.get("ideology", ""),
            "total_votes": p.get("total_votes", 0),
            "for_pct": p.get("for_pct", 0),
            "against_pct": p.get("against_pct", 0),
            "abstained_pct": p.get("abstained_pct", 0),
            "motions_count": len(p.get("motions_filed", [])),
            "top_categories": p.get("top_categories", []),
            "top_allies": p.get("top_allies", []),
            "top_opponents": p.get("top_opponents", []),
            "api_url": f"{base_url}/api/v1/parties/{abbr.lower()}.json",
            "web_url": f"{base_url}/parti/{abbr.lower()}/",
        }
        summary.append(s)

        # Full party detail
        write_json(API_DIR / "parties" / f"{abbr.lower()}.json", {
            **p,
            "abbr": abbr,
            "_links": {
                "self": f"{base_url}/api/v1/parties/{abbr.lower()}.json",
                "web_url": f"{base_url}/parti/{abbr.lower()}/",
                "all_parties": f"{base_url}/api/v1/parties.json",
            }
        })

    write_json(API_DIR / "parties.json", {
        "count": len(summary),
        "municipality": "orebro",
        "parties": sorted(summary, key=lambda x: -x["total_votes"]),
    })


def build_search_index(data, base_url):
    """Build search index for client-side full-text search."""
    entries = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            entries.append({
                "id": d["id"],
                "headline": d.get("hl", d.get("headline", "")),
                "summary": d.get("sum", d.get("summary", "")),
                "category": d.get("cat", d.get("category", "")),
                "tags": d.get("tags", []),
                "location": d.get("loc", d.get("location")),
                "date": m["date"],
                "meeting_type": m.get("type", m.get("meeting_type", "")),
                "contested": d.get("contested", False),
                "url": f"{base_url}/api/v1/decisions/{d['id']}.json",
                "web_url": f"{base_url}/beslut/{d['id']}/",
                # Searchable text blob
                "text": " ".join(filter(None, [
                    d.get("hl", d.get("headline", "")),
                    d.get("sum", d.get("summary", "")),
                    d.get("detail", ""),
                    d.get("loc", d.get("location", "")),
                    " ".join(d.get("tags", [])),
                ])).lower(),
            })

    write_json(API_DIR / "search.json", {
        "count": len(entries),
        "updated": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    })


def build_json_feed(data, base_url):
    """Build JSON Feed (https://jsonfeed.org) for readers/apps."""
    items = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            items.append({
                "id": f"{base_url}/beslut/{d['id']}/",
                "url": f"{base_url}/beslut/{d['id']}/",
                "title": d.get("hl", d.get("headline", "")),
                "content_text": d.get("sum", d.get("summary", "")),
                "date_published": f"{m['date']}T12:00:00+01:00",
                "tags": d.get("tags", []),
                "external_url": m.get("url", m.get("source_url", "")),
                "_kommun_monitor": {
                    "category": d.get("cat", d.get("category", "")),
                    "contested": d.get("contested", False),
                    "meeting_type": m.get("type", m.get("meeting_type", "")),
                    "api_url": f"{base_url}/api/v1/decisions/{d['id']}.json",
                }
            })

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Beslutskollen — Örebro",
        "home_page_url": base_url or "https://kommun-monitor.se",
        "feed_url": f"{base_url}/api/v1/feed.json",
        "description": "AI-sammanfattningar av kommunala beslut i Örebro",
        "language": "sv",
        "items": sorted(items, key=lambda x: x["date_published"], reverse=True),
    }
    write_json(API_DIR / "feed.json", feed)


def build_docs(base_url):
    """Generate interactive API documentation page."""
    doc_html = f'''<!DOCTYPE html><html lang="sv"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beslutskollen API — Dokumentation</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Instrument Sans',sans-serif;background:#0c1219;color:#e2e8f0;line-height:1.6}}
a{{color:#60a5fa;text-decoration:none}}
.wrap{{max-width:800px;margin:0 auto;padding:0 24px}}
header{{padding:32px 0;border-bottom:1px solid rgba(255,255,255,0.06)}}
h1{{font-size:28px;font-weight:300;margin-bottom:4px}}
h2{{font-size:18px;font-weight:600;margin:32px 0 12px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.06)}}
h3{{font-size:14px;font-weight:600;color:#94a3b8;margin:20px 0 8px}}
p{{margin:0 0 12px;color:#94a3b8;font-size:14px}}
code{{font-family:'JetBrains Mono',monospace;font-size:13px;background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px}}
pre{{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:16px;overflow-x:auto;margin:12px 0;font-family:'JetBrains Mono',monospace;font-size:13px;line-height:1.5}}
.endpoint{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:16px;margin:10px 0}}
.method{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;background:#22c55e20;color:#22c55e}}
.path{{font-family:'JetBrains Mono',monospace;font-size:14px;margin-left:8px}}
.try-btn{{display:inline-block;padding:6px 14px;background:#3b82f6;color:#fff;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:none;font-family:inherit;margin-top:8px}}
.try-btn:hover{{background:#2563eb}}
.response{{background:#0f1923;border:1px solid rgba(255,255,255,0.06);border-radius:6px;padding:12px;margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:12px;white-space:pre-wrap;display:none;max-height:300px;overflow:auto}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;margin-left:6px}}
.free{{background:#22c55e20;color:#22c55e}}
.premium{{background:#f59e0b20;color:#f59e0b}}
footer{{padding:24px 0;border-top:1px solid rgba(255,255,255,0.06);margin-top:40px;text-align:center;font-size:12px;color:#475569}}
</style></head><body>
<div class="wrap">
<header>
<div style="font-size:12px;color:#475569;margin-bottom:8px">🏛️ KOMMUN MONITOR</div>
<h1>API Documentation</h1>
<p style="font-size:16px;color:#94a3b8">v{VERSION} — Gratis tillgång till strukturerade kommunbeslut</p>
<p>Base URL: <code>{base_url}/api/v1</code></p>
</header>

<h2>Snabbstart</h2>
<p>API:et är statiskt — inga API-nycklar, ingen autentisering, inga rate limits. Hämta JSON direkt:</p>
<pre>
# Alla beslut
curl {base_url}/api/v1/decisions.json

# Ett specifikt beslut
curl {base_url}/api/v1/decisions/kf389.json

# Partistatistik
curl {base_url}/api/v1/parties.json

# JavaScript
const res = await fetch("{base_url}/api/v1/decisions.json");
const data = await res.json();
console.log(`${{data.count}} beslut`);
</pre>

<h2>Endpoints</h2>

<div class="endpoint">
<span class="method">GET</span><span class="path">/meta.json</span><p style="margin-top:6px">API-metadata: version, statistik, tillgängliga endpoints.</p>
<button class="try-btn" onclick="tryIt(this,'{base_url}/api/v1/meta.json')">Testa →</button>
<div class="response"></div>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/municipalities.json</span><p style="margin-top:6px">Lista över kommuner med data tillgänglig.</p>
<button class="try-btn" onclick="tryIt(this,'{base_url}/api/v1/municipalities.json')">Testa →</button>
<div class="response"></div>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/meetings.json</span><p style="margin-top:6px">Alla sammanträden (sammanfattning). Sorterade efter datum (nyast först).</p>
<button class="try-btn" onclick="tryIt(this,'{base_url}/api/v1/meetings.json')">Testa →</button>
<div class="response"></div>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/meetings/{{id}}.json</span><p style="margin-top:6px">Enskilt sammanträde med alla beslut. Exempel: <code>/meetings/2025-12-10_kf.json</code></p>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/decisions.json</span><p style="margin-top:6px">Alla beslut som flat lista (headline, summary, category, date, tags). Utan full detail.</p>
<button class="try-btn" onclick="tryIt(this,'{base_url}/api/v1/decisions.json')">Testa →</button>
<div class="response"></div>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/decisions/{{id}}.json</span><p style="margin-top:6px">Enskilt beslut med full detalj: voting, quotes, tags, protocol reference.</p>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/parties.json</span><p style="margin-top:6px">Partistatistik: röstningsfördelning, allianser, nyckelfrågor.</p>
<button class="try-btn" onclick="tryIt(this,'{base_url}/api/v1/parties.json')">Testa →</button>
<div class="response"></div>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/parties/{{abbr}}.json</span><p style="margin-top:6px">Enskilt parti. Exempel: <code>/parties/v.json</code>, <code>/parties/sd.json</code></p>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/search.json</span><p style="margin-top:6px">Fulltextsökindex för client-side search. Varje entry innehåller normaliserat <code>text</code>-fält.</p>
</div>

<div class="endpoint">
<span class="method">GET</span><span class="path">/feed.json</span><p style="margin-top:6px"><a href="https://jsonfeed.org">JSON Feed</a> (RFC) — för RSS-läsare och appar som stöder JSON Feed.</p>
<button class="try-btn" onclick="tryIt(this,'{base_url}/api/v1/feed.json')">Testa →</button>
<div class="response"></div>
</div>

<h2>Datamodell</h2>

<h3>Decision</h3>
<pre>
{{
  "id": "kf389",
  "headline": "202 socialtjänstbeslut väntar...",
  "summary": "Antalet ej verkställda...",
  "detail": "Fullständig sammanfattning...",
  "category": "politik",         // bygg|skola|budget|politik|regler|miljö|...
  "contested": true,              // true om votering/reservation
  "location": "Eyrafältet",      // null om ej platsspecifikt
  "paragraph_ref": "§ 389",
  "tags": ["socialtjänst", "lss"],
  "voting": {{
    "for": ["S", "M", "C"],
    "against": ["V", "ÖrP", "KD"],
    "abstained": [],
    "result": "V:s tillägg avslogs"
  }},
  "quote": "Citat ur protokollet",
  "quote_page": "s. 10",
  "meeting": {{
    "id": "2025-12-10_kf",
    "date": "2025-12-10",
    "type": "Kommunfullmäktige",
    "source_url": "https://..."
  }}
}}
</pre>

<h3>Party</h3>
<pre>
{{
  "abbr": "V",
  "name": "Vänsterpartiet",
  "color": "#da291c",
  "position": "Opposition",
  "total_votes": 14,
  "for_pct": 43,
  "against_pct": 29,
  "top_allies": [["KD", 6], ["ÖrP", 5]],
  "top_opponents": [["M", 8], ["C", 8]],
  "motions_filed": [...]
}}
</pre>

<h2>Användningsexempel</h2>

<h3>Python</h3>
<pre>
import requests

# Hämta alla omstridda beslut
data = requests.get("{base_url}/api/v1/decisions.json").json()
contested = [d for d in data["decisions"] if d["contested"]]
print(f"{{len(contested)}} omstridda beslut")
for d in contested:
    print(f"  {{d['date']}} — {{d['headline']}}")
</pre>

<h3>JavaScript</h3>
<pre>
// Hämta partistatistik
const res = await fetch("{base_url}/api/v1/parties.json");
const {{ parties }} = await res.json();

// Mest oppositionella parti
const mostOpposed = parties.sort((a,b) => b.against_pct - a.against_pct)[0];
console.log(`${{mostOpposed.name}} röstar NEJ ${{mostOpposed.against_pct}}% av gångerna`);
</pre>

<h3>curl + jq</h3>
<pre>
# Alla beslut om skola
curl -s {base_url}/api/v1/decisions.json | \\
  jq '.decisions[] | select(.category == "skola") | .headline'

# Hur röstade SD?
curl -s {base_url}/api/v1/parties/sd.json | \\
  jq '{{name, for_pct, against_pct, top_allies}}'
</pre>

<h2>Licens & villkor</h2>
<p>Data baserad på svenska offentliga handlingar (offentlighetsprincipen) — fritt att använda.</p>
<p>AI-sammanfattningar publiceras under <strong>CC BY 4.0</strong>. Ange <em>"Beslutskollen"</em> som källa.</p>
<p style="color:#f59e0b">⚠️ Sammanfattningar genereras av AI och kan innehålla fel. Verifiera alltid mot <a href="https://www.orebro.se/kommun--politik/politik--beslut.html">originalprotokollen</a>.</p>

<footer>
<p>Beslutskollen API v{VERSION} — <a href="{base_url}/">Hem</a> · <a href="{base_url}/parti/">Partier</a> · <a href="{base_url}/omrade/">Områden</a></p>
</footer>
</div>

<script>
async function tryIt(btn, url) {{
  const resp = btn.nextElementSibling;
  if (resp.style.display === 'block') {{ resp.style.display = 'none'; btn.textContent = 'Testa →'; return; }}
  btn.textContent = 'Laddar...';
  try {{
    const r = await fetch(url);
    const d = await r.json();
    resp.textContent = JSON.stringify(d, null, 2).slice(0, 3000);
    resp.style.display = 'block';
    btn.textContent = 'Dölj ↑';
  }} catch(e) {{
    resp.textContent = 'Fel: ' + e.message + '\\n(API:et måste serveras — öppna via http, inte file://)';
    resp.style.display = 'block';
    btn.textContent = 'Testa →';
  }}
}}
</script>
</body></html>'''

    docs_dir = API_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(doc_html, "utf-8")


def build_areas(data, base_url):
    """Build areas endpoint from existing area analysis."""
    # Import area analysis
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from analytics import analyze_areas, OREBRO_AREAS
        areas = analyze_areas(data)
        summary = []
        for key, area in areas.items():
            summary.append({
                "id": key,
                "name": area["name"],
                "decisions_count": len(area["decisions"]),
                "api_url": f"{base_url}/api/v1/areas/{key}.json",
                "web_url": f"{base_url}/omrade/{key}/",
                "decisions": area["decisions"],
            })
            write_json(API_DIR / "areas" / f"{key}.json", {
                "id": key,
                "name": area["name"],
                "decisions": area["decisions"],
                "_links": {
                    "self": f"{base_url}/api/v1/areas/{key}.json",
                    "web_url": f"{base_url}/omrade/{key}/",
                }
            })

        write_json(API_DIR / "areas.json", {
            "count": len(summary),
            "areas": sorted(summary, key=lambda x: -x["decisions_count"]),
        })
    except ImportError:
        # Analytics not available, create empty
        write_json(API_DIR / "areas.json", {"count": 0, "areas": []})


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate static JSON API")
    parser.add_argument("--base-url", default="https://lingabton.github.io/kommun-monitor")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"🔧 Building Beslutskollen API v{VERSION}")
    print(f"   Base URL: {base_url or '(relative)'}")
    print(f"   Output: {API_DIR}/")

    data = load_data()
    meetings = data.get("meetings", [])
    decisions = sum(len(m.get("decisions", [])) for m in meetings)
    print(f"   Data: {len(meetings)} meetings, {decisions} decisions")

    API_DIR.mkdir(parents=True, exist_ok=True)

    print("\n📋 Generating endpoints...")

    meta = build_meta(data, base_url)
    print(f"   ✓ meta.json")

    build_municipalities(data, base_url)
    print(f"   ✓ municipalities.json")

    build_meetings(data, base_url)
    print(f"   ✓ meetings.json + {len(meetings)} individual")

    build_decisions(data, base_url)
    print(f"   ✓ decisions.json + {decisions} individual")

    build_parties(base_url)
    parties = load_parties()
    active = len([p for p in parties.values() if p.get("total_votes", 0) > 0])
    print(f"   ✓ parties.json + {active} individual")

    build_areas(data, base_url)
    print(f"   ✓ areas.json")

    build_search_index(data, base_url)
    print(f"   ✓ search.json ({decisions} entries)")

    build_json_feed(data, base_url)
    print(f"   ✓ feed.json (JSON Feed)")

    build_docs(base_url)
    print(f"   ✓ docs/index.html")

    # Count files
    total_files = sum(1 for _ in API_DIR.rglob("*.json")) + 1  # +1 for docs HTML
    total_size = sum(f.stat().st_size for f in API_DIR.rglob("*") if f.is_file())
    print(f"\n✅ API built: {total_files} files, {total_size/1024:.1f} KB total")
    print(f"   Docs: {base_url}/api/v1/docs/")


if __name__ == "__main__":
    main()
