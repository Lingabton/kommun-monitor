"""
Kommun Monitor — Analytics Engine
===================================
Generates:
1. Party profiles from voting data
2. Area/stadsdel pages from location data
3. Budget tracker from financial decisions

Runs after scraper.py — reads from site/data.json, outputs to site/
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from html import escape

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"

PARTIES_META = {
    "S":  {"name":"Socialdemokraterna","short":"S","color":"#e8112d","position":"Majoritet","ideology":"Socialdemokrati"},
    "M":  {"name":"Moderaterna","short":"M","color":"#52bdec","position":"Majoritet","ideology":"Liberalkonservatism"},
    "C":  {"name":"Centerpartiet","short":"C","color":"#009933","position":"Majoritet","ideology":"Centerism, grön liberalism"},
    "L":  {"name":"Liberalerna","short":"L","color":"#006ab3","position":"Opposition","ideology":"Socialliberalism"},
    "KD": {"name":"Kristdemokraterna","short":"KD","color":"#231977","position":"Opposition","ideology":"Kristdemokrati"},
    "V":  {"name":"Vänsterpartiet","short":"V","color":"#da291c","position":"Opposition","ideology":"Demokratisk socialism"},
    "SD": {"name":"Sverigedemokraterna","short":"SD","color":"#dddd00","text_color":"#333","position":"Opposition","ideology":"Socialkonservatism"},
    "ÖrP":{"name":"Örebropartiet","short":"ÖrP","color":"#f47920","position":"Opposition","ideology":"Lokalt parti"},
    "MP": {"name":"Miljöpartiet","short":"MP","color":"#83cf39","position":"Opposition","ideology":"Grön politik"},
}

OREBRO_AREAS = {
    "centrum": {"name": "Centrum", "aliases": ["stortorget", "drottninggatan", "järntorget", "södra strandgatan", "rådhuset", "city"]},
    "söder": {"name": "Söder", "aliases": ["sörbyängen", "sörby", "markbacken", "tybble", "almby"]},
    "öster": {"name": "Öster", "aliases": ["vivalla", "brickebacken", "baronbackarna", "varberga", "oxhagen"]},
    "norr": {"name": "Norr", "aliases": ["adolfsberg", "ånsta", "lillån"]},
    "väster": {"name": "Väster", "aliases": ["marieberg", "norra marieberg", "mosås"]},
    "eyrafältet": {"name": "Eyrafältet", "aliases": ["eyrafältet", "eklundavägen", "eyra"]},
    "garphyttan": {"name": "Garphyttan", "aliases": ["garphyttan", "garphytteklint"]},
    "karlslund": {"name": "Karlslund", "aliases": ["karlslund"]},
    "hjälmaren": {"name": "Hjälmaren", "aliases": ["hjälmaren"]},
    "flygplatsen": {"name": "Flygplatsen", "aliases": ["flygplats", "örebro flygplats", "örebro läns flygplats"]},
}


def load_data():
    p = SITE_DIR / "data.json"
    if not p.exists():
        return {"meetings": []}
    return json.loads(p.read_text("utf-8"))


# ═══════════════════════════════════════════
# 1. PARTY PROFILES
# ═══════════════════════════════════════════

def analyze_parties(data):
    """Analyze all voting data and generate party profiles."""
    parties = {}
    for abbr, meta in PARTIES_META.items():
        parties[abbr] = {
            **meta,
            "votes_for": 0,
            "votes_against": 0,
            "votes_abstained": 0,
            "total_votes": 0,
            "contested_votes": [],    # decisions where they were on minority side
            "key_issues": defaultdict(int),  # category → count
            "motions_filed": [],
            "agreement_with": defaultdict(int),  # other_party → times agreed
            "disagreement_with": defaultdict(int),
            "decisions_involved": [],
        }

    all_decisions = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            all_decisions.append((d, m))
            v = d.get("voting", {})
            if not v:
                continue

            for_parties = set(v.get("for", []))
            against_parties = set(v.get("against", []))
            abstained_parties = set(v.get("abstained", []))
            all_involved = for_parties | against_parties | abstained_parties

            for p in all_involved:
                if p not in parties:
                    continue
                parties[p]["total_votes"] += 1
                parties[p]["decisions_involved"].append({
                    "id": d["id"], "headline": d["headline"],
                    "date": m["date"], "category": d.get("category", ""),
                    "position": "for" if p in for_parties else "against" if p in against_parties else "abstained",
                    "contested": d.get("contested", False),
                })

                if p in for_parties:
                    parties[p]["votes_for"] += 1
                elif p in against_parties:
                    parties[p]["votes_against"] += 1
                    parties[p]["contested_votes"].append({
                        "id": d["id"], "headline": d["headline"], "date": m["date"],
                    })
                else:
                    parties[p]["votes_abstained"] += 1

                if p in against_parties or p in for_parties:
                    parties[p]["key_issues"][d.get("category", "övrigt")] += 1

                # Agreement matrix
                same_side = for_parties if p in for_parties else against_parties if p in against_parties else set()
                other_side = against_parties if p in for_parties else for_parties if p in against_parties else set()
                for other in same_side:
                    if other != p and other in parties:
                        parties[p]["agreement_with"][other] += 1
                for other in other_side:
                    if other != p and other in parties:
                        parties[p]["disagreement_with"][other] += 1

        # Motions
        for mot in m.get("motions_of_interest", []):
            p = mot.get("party", "")
            if p in parties:
                parties[p]["motions_filed"].append({
                    "title": mot["title"], "status": mot.get("status", ""),
                    "date": m["date"],
                })

    # Calculate derived metrics
    for abbr, p in parties.items():
        total = p["total_votes"] or 1
        p["for_pct"] = round(p["votes_for"] / total * 100)
        p["against_pct"] = round(p["votes_against"] / total * 100)
        p["abstained_pct"] = round(p["votes_abstained"] / total * 100)
        p["activity_score"] = min(100, int(total * 5 + len(p["motions_filed"]) * 10))

        # Top categories
        p["top_categories"] = sorted(p["key_issues"].items(), key=lambda x: -x[1])[:5]

        # Best allies / biggest opponents
        p["top_allies"] = sorted(p["agreement_with"].items(), key=lambda x: -x[1])[:3]
        p["top_opponents"] = sorted(p["disagreement_with"].items(), key=lambda x: -x[1])[:3]

        # Convert defaultdicts
        p["key_issues"] = dict(p["key_issues"])
        p["agreement_with"] = dict(p["agreement_with"])
        p["disagreement_with"] = dict(p["disagreement_with"])

    return parties


def generate_party_pages(parties, base_url=""):
    """Generate an HTML page per party + an overview page."""
    cat_emojis = {"bygg":"🏗️","infrastruktur":"🛣️","skola":"🏫","budget":"💰","miljö":"🌿",
                  "trygghet":"🛡️","kultur":"🎭","politik":"⚖️","regler":"📜","övrigt":"📋"}

    party_dir = SITE_DIR / "parti"
    party_dir.mkdir(exist_ok=True)

    # Overview page
    overview = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Partier i Örebro kommun — Kommun Monitor</title>
<meta name="description" content="Hur röstar partierna i Örebro kommun? Se röstningsstatistik, nyckelfrågor och aktivitet per parti.">
<link rel="canonical" href="{base_url}/parti/">
<meta property="og:title" content="Partier i Örebro kommun"><meta property="og:description" content="Röstningsstatistik per parti i Örebro kommunfullmäktige och kommunstyrelsen.">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1e293b}}a{{color:#1e3a5f;text-decoration:none}}
header{{background:linear-gradient(135deg,#0f2439,#1e3a5f 60%,#2d5a87);color:#fff;padding:24px 20px}}
.wrap{{max-width:800px;margin:0 auto;padding:0 20px}}
.party-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-top:20px}}
.party-card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.05);transition:box-shadow .2s;cursor:pointer;border-left:5px solid #ccc}}
.party-card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.1)}}
.party-card h3{{font-size:16px;margin-bottom:4px}} .party-card .pos{{font-size:12px;color:#64748b}}
.bar-row{{display:flex;height:8px;border-radius:4px;overflow:hidden;margin:10px 0 6px;background:#f1f5f9}}
.bar-row .for{{background:#22c55e}} .bar-row .against{{background:#ef4444}} .bar-row .abstain{{background:#d4d4d8}}
.party-card .stats{{font-size:12px;color:#64748b;display:flex;gap:12px}}
footer{{border-top:1px solid #e2e8f0;padding:16px 20px;text-align:center;font-size:11px;color:#94a3b8;margin-top:40px}}
</style></head><body>
<header><div class="wrap">
<a href="{base_url}/" style="color:#fff;opacity:.7;font-size:13px">🏛️ Kommun Monitor</a>
<h1 style="font-family:'DM Serif Display',serif;font-size:24px;font-weight:400;margin-top:8px">Partierna i Örebro kommun</h1>
<p style="font-size:14px;opacity:.7;margin-top:4px">Hur röstar de? Vilka frågor driver de?</p>
</div></header>
<div class="wrap"><div class="party-grid">'''

    for abbr in ["S","M","C","L","KD","V","SD","ÖrP","MP"]:
        p = parties.get(abbr)
        if not p or p["total_votes"] == 0:
            continue
        tc = p.get("text_color", "#fff")
        overview += f'''
<a href="{base_url}/parti/{abbr.lower()}/" class="party-card" style="border-left-color:{p['color']}">
<h3 style="color:{p['color']}">{p['name']}</h3>
<div class="pos">{p['position']} · {p['total_votes']} röstningar</div>
<div class="bar-row"><div class="for" style="width:{p['for_pct']}%"></div><div class="against" style="width:{p['against_pct']}%"></div><div class="abstain" style="width:{p['abstained_pct']}%"></div></div>
<div class="stats"><span style="color:#22c55e">JA {p['for_pct']}%</span><span style="color:#ef4444">NEJ {p['against_pct']}%</span><span>AVSTOD {p['abstained_pct']}%</span></div>
{f"<div style='margin-top:8px;font-size:12px;color:#94a3b8'>{len(p['motions_filed'])} motioner</div>" if p['motions_filed'] else ""}
</a>'''

    overview += '''</div></div>
<footer><p>Kommun Monitor — AI-sammanfattningar av kommunala beslut</p></footer></body></html>'''

    (party_dir / "index.html").write_text(overview, "utf-8")

    # Individual party pages
    for abbr in ["S","M","C","L","KD","V","SD","ÖrP","MP"]:
        p = parties.get(abbr)
        if not p or p["total_votes"] == 0:
            continue

        # Top issues HTML
        issues_html = ""
        for cat, count in p["top_categories"]:
            emoji = cat_emojis.get(cat, "📋")
            issues_html += f'<div style="display:flex;align-items:center;gap:8px;padding:6px 0"><span>{emoji}</span><span style="flex:1">{cat.title()}</span><strong>{count}</strong> röstningar</div>'

        # Allies/opponents
        allies_html = "".join(f'<span style="background:{PARTIES_META.get(a,{}).get("color","#999")};color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600">{a}</span> ' for a, _ in p["top_allies"])
        opponents_html = "".join(f'<span style="background:{PARTIES_META.get(a,{}).get("color","#999")};color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600">{a}</span> ' for a, _ in p["top_opponents"])

        # Contested votes
        contested_html = ""
        for cv in p["contested_votes"][:10]:
            contested_html += f'<a href="{base_url}/beslut/{cv["id"]}/" style="display:block;padding:6px 0;border-bottom:1px solid #f1f5f9;color:#1e293b;font-size:13px"><span style="color:#94a3b8">{cv["date"]}</span> · {escape(cv["headline"])}</a>'

        # Motions
        motions_html = ""
        for mot in p["motions_filed"]:
            motions_html += f'<div style="padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:13px"><strong>{escape(mot["title"])}</strong><br><span style="color:#94a3b8">{mot["date"]} · {mot["status"]}</span></div>'

        page = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{p['name']} i Örebro kommun — Kommun Monitor</title>
<meta name="description" content="Hur röstar {p['name']} i Örebro? Röstningsstatistik, nyckelfrågor och motioner.">
<link rel="canonical" href="{base_url}/parti/{abbr.lower()}/">
<meta property="og:title" content="{p['name']} — röstningsstatistik Örebro kommun">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1e293b;line-height:1.5}}a{{color:#1e3a5f;text-decoration:none}}
header{{background:linear-gradient(135deg,#0f2439,#1e3a5f 60%,#2d5a87);color:#fff;padding:24px 20px}}
.wrap{{max-width:700px;margin:0 auto;padding:0 20px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:20px 0}}
.stat{{background:#fff;border-radius:10px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.stat .val{{font-size:24px;font-weight:700}} .stat .lbl{{font-size:11px;color:#64748b}}
.section{{background:#fff;border-radius:10px;padding:18px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.section h3{{font-size:14px;color:#64748b;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px;font-size:12px}}
.bar-big{{height:24px;border-radius:6px;display:flex;overflow:hidden;background:#f1f5f9;margin:8px 0}}
.bar-big div{{display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:#fff}}
footer{{border-top:1px solid #e2e8f0;padding:16px 20px;text-align:center;font-size:11px;color:#94a3b8;margin-top:40px}}
</style></head><body>
<header><div class="wrap">
<div style="display:flex;gap:12px;align-items:center;margin-bottom:8px">
<a href="{base_url}/" style="color:#fff;opacity:.7;font-size:13px">🏛️ Kommun Monitor</a>
<span style="opacity:.4">›</span>
<a href="{base_url}/parti/" style="color:#fff;opacity:.7;font-size:13px">Partier</a>
</div>
<div style="display:flex;align-items:center;gap:14px">
<div style="width:48px;height:48px;border-radius:10px;background:{p['color']};display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:{'#333' if abbr == 'SD' else '#fff'}">{abbr}</div>
<div>
<h1 style="font-family:'DM Serif Display',serif;font-size:24px;font-weight:400">{p['name']}</h1>
<p style="font-size:13px;opacity:.7">{p['position']} · {p['ideology']}</p>
</div>
</div>
</div></header>

<div class="wrap" style="padding-top:20px;padding-bottom:40px">

<div class="stats">
<div class="stat"><div class="val">{p['total_votes']}</div><div class="lbl">Röstningar</div></div>
<div class="stat"><div class="val" style="color:#22c55e">{p['for_pct']}%</div><div class="lbl">Röstade JA</div></div>
<div class="stat"><div class="val" style="color:#ef4444">{p['against_pct']}%</div><div class="lbl">Röstade NEJ</div></div>
<div class="stat"><div class="val">{len(p['motions_filed'])}</div><div class="lbl">Motioner</div></div>
</div>

<div class="bar-big">
<div class="for" style="width:{p['for_pct']}%;background:#22c55e">JA {p['for_pct']}%</div>
<div style="width:{p['against_pct']}%;background:#ef4444">NEJ {p['against_pct']}%</div>
<div style="width:{p['abstained_pct']}%;background:#d4d4d8;color:#666">AVSTOD {p['abstained_pct']}%</div>
</div>

<div class="section"><h3>Nyckelfrågor</h3>{issues_html or '<p style="color:#94a3b8;font-size:13px">Ingen data ännu</p>'}</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
<div class="section"><h3>Röstar oftast med</h3><div style="display:flex;gap:6px;flex-wrap:wrap">{allies_html or '<span style="color:#94a3b8;font-size:13px">—</span>'}</div></div>
<div class="section"><h3>Röstar oftast mot</h3><div style="display:flex;gap:6px;flex-wrap:wrap">{opponents_html or '<span style="color:#94a3b8;font-size:13px">—</span>'}</div></div>
</div>

{f'<div class="section"><h3>Röstade NEJ i dessa beslut</h3>{contested_html}</div>' if contested_html else ''}
{f'<div class="section"><h3>Motioner</h3>{motions_html}</div>' if motions_html else ''}

</div>
<footer><p>Kommun Monitor — AI-sammanfattningar. Data baserad på publicerade protokoll från orebro.se.</p></footer></body></html>'''

        page_dir = party_dir / abbr.lower()
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(page, "utf-8")

    return len([a for a in parties if parties[a]["total_votes"] > 0])


# ═══════════════════════════════════════════
# 2. AREA PAGES
# ═══════════════════════════════════════════

def analyze_areas(data):
    """Match decisions to geographic areas based on location and tags."""
    areas = {}
    for key, meta in OREBRO_AREAS.items():
        areas[key] = {**meta, "decisions": []}

    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            loc = (d.get("location") or "").lower()
            tags = [t.lower() for t in (d.get("tags") or [])]
            detail = (d.get("detail") or "").lower()
            searchable = f"{loc} {' '.join(tags)} {detail}"

            for area_key, area in OREBRO_AREAS.items():
                if any(alias in searchable for alias in area["aliases"]):
                    areas[area_key]["decisions"].append({
                        "id": d["id"], "headline": d["headline"],
                        "summary": d.get("summary", ""),
                        "date": m["date"], "meeting_type": m["meeting_type"],
                        "category": d.get("category", ""),
                        "contested": d.get("contested", False),
                    })

    return {k: v for k, v in areas.items() if v["decisions"]}


def generate_area_pages(areas, base_url=""):
    """Generate an HTML page per area + overview."""
    cat_emojis = {"bygg":"🏗️","infrastruktur":"🛣️","skola":"🏫","budget":"💰","miljö":"🌿",
                  "trygghet":"🛡️","kultur":"🎭","politik":"⚖️","regler":"📜","övrigt":"📋"}

    area_dir = SITE_DIR / "omrade"
    area_dir.mkdir(exist_ok=True)

    # Overview
    overview = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beslut per område — Örebro — Kommun Monitor</title>
<meta name="description" content="Hitta kommunala beslut som berör ditt område i Örebro. Sörbyängen, Vivalla, Centrum och fler.">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1e293b}}a{{color:#1e3a5f;text-decoration:none}}
header{{background:linear-gradient(135deg,#0f2439,#1e3a5f 60%,#2d5a87);color:#fff;padding:24px 20px}}
.wrap{{max-width:700px;margin:0 auto;padding:0 20px}}
.area-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:20px}}
.area-card{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.05);transition:box-shadow .2s}}
.area-card:hover{{box-shadow:0 4px 12px rgba(0,0,0,.1)}}
footer{{border-top:1px solid #e2e8f0;padding:16px 20px;text-align:center;font-size:11px;color:#94a3b8;margin-top:40px}}
</style></head><body>
<header><div class="wrap">
<a href="{base_url}/" style="color:#fff;opacity:.7;font-size:13px">🏛️ Kommun Monitor</a>
<h1 style="font-family:'DM Serif Display',serif;font-size:24px;font-weight:400;margin-top:8px">Beslut per område</h1>
<p style="font-size:14px;opacity:.7;margin-top:4px">Vad händer i din del av Örebro?</p>
</div></header>
<div class="wrap"><div class="area-grid">'''

    for key in sorted(areas.keys(), key=lambda k: -len(areas[k]["decisions"])):
        a = areas[key]
        overview += f'''<a href="{base_url}/omrade/{key}/" class="area-card">
<div style="font-size:24px;margin-bottom:6px">📍</div>
<h3 style="font-size:16px;margin-bottom:4px">{a['name']}</h3>
<div style="font-size:13px;color:#64748b">{len(a['decisions'])} beslut</div>
</a>'''

    overview += '</div></div><footer><p>Kommun Monitor</p></footer></body></html>'
    (area_dir / "index.html").write_text(overview, "utf-8")

    # Individual area pages
    for key, a in areas.items():
        decisions_html = ""
        for d in sorted(a["decisions"], key=lambda x: x["date"], reverse=True):
            emoji = cat_emojis.get(d["category"], "📋")
            contested = ' <span style="background:#fef2f2;color:#dc2626;font-size:10px;font-weight:700;padding:2px 6px;border-radius:8px">⚡</span>' if d.get("contested") else ""
            decisions_html += f'''<a href="{base_url}/beslut/{d['id']}/" style="display:block;padding:12px 0;border-bottom:1px solid #f1f5f9;color:#1e293b">
<div style="display:flex;align-items:flex-start;gap:8px">
<span>{emoji}</span>
<div><strong style="font-size:14px">{escape(d['headline'])}{contested}</strong>
<div style="font-size:12px;color:#94a3b8;margin-top:2px">{d['meeting_type']} · {d['date']}</div>
<div style="font-size:13px;color:#64748b;margin-top:4px">{escape(d.get('summary',''))}</div>
</div></div></a>'''

        page = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beslut i {a['name']} — Örebro — Kommun Monitor</title>
<meta name="description" content="Alla kommunala beslut som berör {a['name']} i Örebro. Bygg, infrastruktur, skola och mer.">
<link rel="canonical" href="{base_url}/omrade/{key}/">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1e293b;line-height:1.5}}a{{color:#1e3a5f;text-decoration:none}}
header{{background:linear-gradient(135deg,#0f2439,#1e3a5f 60%,#2d5a87);color:#fff;padding:24px 20px}}
.wrap{{max-width:700px;margin:0 auto;padding:0 20px}}
footer{{border-top:1px solid #e2e8f0;padding:16px 20px;text-align:center;font-size:11px;color:#94a3b8;margin-top:40px}}
</style></head><body>
<header><div class="wrap">
<div style="display:flex;gap:12px;align-items:center;margin-bottom:8px">
<a href="{base_url}/" style="color:#fff;opacity:.7;font-size:13px">🏛️ Kommun Monitor</a>
<span style="opacity:.4">›</span>
<a href="{base_url}/omrade/" style="color:#fff;opacity:.7;font-size:13px">Områden</a>
</div>
<h1 style="font-family:'DM Serif Display',serif;font-size:24px;font-weight:400">📍 {a['name']}</h1>
<p style="font-size:14px;opacity:.7;margin-top:4px">{len(a['decisions'])} beslut som berör detta område</p>
</div></header>
<div class="wrap" style="padding:20px 20px 40px">{decisions_html}</div>
<footer><p>Kommun Monitor</p></footer></body></html>'''

        page_dir = area_dir / key
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(page, "utf-8")

    return len(areas)


# ═══════════════════════════════════════════
# 3. BUDGET TRACKER
# ═══════════════════════════════════════════

def analyze_budget(data):
    """Extract financial data from decisions."""
    entries = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            if d.get("category") not in ("budget", "bygg"):
                # Also scan non-budget items for financial mentions
                detail = (d.get("detail") or "") + " " + (d.get("summary") or "")
                if not any(w in detail.lower() for w in ["msek", "mnkr", "miljoner", "miljon", "budget"]):
                    continue

            entries.append({
                "id": d["id"],
                "headline": d["headline"],
                "date": m["date"],
                "category": d.get("category", ""),
                "summary": d.get("summary", ""),
                "detail": d.get("detail", ""),
                "contested": d.get("contested", False),
                "meeting_type": m["meeting_type"],
            })

    return entries


def generate_budget_page(budget_entries, base_url=""):
    """Generate budget tracker page."""
    cat_emojis = {"bygg":"🏗️","budget":"💰","infrastruktur":"🛣️","miljö":"🌿","regler":"📜"}

    entries_html = ""
    for e in sorted(budget_entries, key=lambda x: x["date"], reverse=True):
        emoji = cat_emojis.get(e["category"], "💰")
        contested = ' <span style="background:#fef2f2;color:#dc2626;font-size:10px;font-weight:700;padding:2px 6px;border-radius:8px">⚡</span>' if e.get("contested") else ""
        entries_html += f'''<a href="{base_url}/beslut/{e['id']}/" style="display:block;padding:14px 0;border-bottom:1px solid #f1f5f9;color:#1e293b">
<div style="display:flex;align-items:flex-start;gap:8px">
<span style="font-size:18px">{emoji}</span>
<div><strong style="font-size:14px">{escape(e['headline'])}{contested}</strong>
<div style="font-size:12px;color:#94a3b8;margin-top:2px">{e['meeting_type']} · {e['date']}</div>
<div style="font-size:13px;color:#64748b;margin-top:4px;line-height:1.4">{escape(e.get('summary',''))}</div>
</div></div></a>'''

    page = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Örebro kommuns ekonomi — Budget-tracker — Kommun Monitor</title>
<meta name="description" content="Följ Örebro kommuns ekonomi: budgetbeslut, investeringar, avvikelser och ekonomiska rapporter samlade på ett ställe.">
<link rel="canonical" href="{base_url}/ekonomi/">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'DM Sans',sans-serif;background:#f8fafc;color:#1e293b;line-height:1.5}}a{{color:#1e3a5f;text-decoration:none}}
header{{background:linear-gradient(135deg,#0f2439,#1e3a5f 60%,#2d5a87);color:#fff;padding:24px 20px}}
.wrap{{max-width:700px;margin:0 auto;padding:0 20px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:20px 0}}
.stat{{background:#fff;border-radius:10px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.stat .val{{font-size:22px;font-weight:700}} .stat .lbl{{font-size:11px;color:#64748b}}
footer{{border-top:1px solid #e2e8f0;padding:16px 20px;text-align:center;font-size:11px;color:#94a3b8;margin-top:40px}}
</style></head><body>
<header><div class="wrap">
<div style="display:flex;gap:12px;align-items:center;margin-bottom:8px">
<a href="{base_url}/" style="color:#fff;opacity:.7;font-size:13px">🏛️ Kommun Monitor</a>
</div>
<h1 style="font-family:'DM Serif Display',serif;font-size:24px;font-weight:400">💰 Örebro kommuns ekonomi</h1>
<p style="font-size:14px;opacity:.7;margin-top:4px">Budgetbeslut, investeringar och ekonomiska rapporter</p>
</div></header>
<div class="wrap" style="padding-top:10px;padding-bottom:40px">
<div class="stats">
<div class="stat"><div class="val">{len(budget_entries)}</div><div class="lbl">Ekonomibeslut</div></div>
<div class="stat"><div class="val">{len([e for e in budget_entries if e['contested']])}</div><div class="lbl">Omstridda</div></div>
<div class="stat"><div class="val">{len(set(e['date'][:4] for e in budget_entries))}</div><div class="lbl">År med data</div></div>
</div>
<div style="background:#fff;border-radius:10px;padding:4px 16px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
{entries_html}
</div>
</div>
<footer><p>Kommun Monitor — AI-sammanfattningar av kommunala beslut</p></footer></body></html>'''

    ekon_dir = SITE_DIR / "ekonomi"
    ekon_dir.mkdir(exist_ok=True)
    (ekon_dir / "index.html").write_text(page, "utf-8")
    return len(budget_entries)


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate analytics pages")
    parser.add_argument("--base-url", default="")
    args = parser.parse_args()

    data = load_data()
    total_decisions = sum(len(m["decisions"]) for m in data.get("meetings", []))
    print(f"📊 Loaded {len(data.get('meetings',[]))} meetings, {total_decisions} decisions")

    # Party profiles
    print("\n🏛️ Generating party profiles...")
    parties = analyze_parties(data)
    n = generate_party_pages(parties, args.base_url)
    print(f"   {n} party pages generated → site/parti/")

    # Save party data as JSON too
    (SITE_DIR / "parties.json").write_text(json.dumps(
        {k: {kk: vv for kk, vv in v.items() if kk != "decisions_involved"} for k, v in parties.items()},
        ensure_ascii=False, indent=2), "utf-8")

    # Area pages
    print("\n📍 Generating area pages...")
    areas = analyze_areas(data)
    n = generate_area_pages(areas, args.base_url)
    print(f"   {n} area pages generated → site/omrade/")

    # Budget tracker
    print("\n💰 Generating budget tracker...")
    budget = analyze_budget(data)
    n = generate_budget_page(budget, args.base_url)
    print(f"   {n} budget entries → site/ekonomi/")

    print("\n✅ Analytics complete!")


if __name__ == "__main__":
    main()
