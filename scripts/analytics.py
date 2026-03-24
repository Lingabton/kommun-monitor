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

    # Load attendance data
    for m in data.get("meetings", []):
        date = m["date"]
        organ = m.get("organ", m.get("meeting_type", ""))
        safe = f"{date}_{organ.replace(' ', '_')}"
        att_file = Path(__file__).parent.parent / "output" / safe / "attendance.json"
        if not att_file.exists():
            # Try old format
            for d in (Path(__file__).parent.parent / "output").iterdir():
                if d.is_dir() and date in d.name and (d / "attendance.json").exists():
                    att_file = d / "attendance.json"
                    break
        if att_file.exists():
            try:
                att = json.loads(att_file.read_text("utf-8"))
                for party, info in att.get("parties", {}).items():
                    if party in parties and info.get("present", 0) > 0:
                        parties[party].setdefault("meetings_attended", 0)
                        parties[party]["meetings_attended"] += 1
                        parties[party].setdefault("total_present_sum", 0)
                        parties[party]["total_present_sum"] += info["present"]
                        parties[party].setdefault("attendance_records", [])
                        parties[party]["attendance_records"].append({
                            "date": date, "organ": organ, "present": info["present"]
                        })
            except Exception:
                pass

    total_meetings_with_attendance = len([
        m for m in data.get("meetings", [])
        if (Path(__file__).parent.parent / "output" / f"{m['date']}_{m.get('organ', m.get('meeting_type', '')).replace(' ', '_')}" / "attendance.json").exists()
        or any((Path(__file__).parent.parent / "output" / d.name / "attendance.json").exists()
               for d in (Path(__file__).parent.parent / "output").iterdir()
               if d.is_dir() and m["date"] in d.name)
    ])

    # Calculate derived metrics
    for abbr, p in parties.items():
        total = p["total_votes"] or 1
        p["for_pct"] = round(p["votes_for"] / total * 100)
        p["against_pct"] = round(p["votes_against"] / total * 100)
        p["abstained_pct"] = round(p["votes_abstained"] / total * 100)
        p["activity_score"] = min(100, int(total * 5 + len(p["motions_filed"]) * 10))

        # Attendance
        attended = p.get("meetings_attended", 0)
        p["attendance_pct"] = round(attended / max(total_meetings_with_attendance, 1) * 100)
        p["avg_present"] = round(p.get("total_present_sum", 0) / max(attended, 1), 1)
        p["total_meetings_with_attendance"] = total_meetings_with_attendance

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


def _party_summary(abbr, p, parties):
    """Generate a template-based summary for a party."""
    name = p["name"]
    pos = p["position"]
    total = p["total_votes"]
    motions = len(p["motions_filed"])
    against_pct = p["against_pct"]
    contested = len(p["contested_votes"])

    lines = []
    if pos == "Majoritet":
        allies = [PARTIES_META[a]["name"] for a in ["S","M","C"] if a != abbr]
        lines.append(f"{name} styr Örebro kommun tillsammans med {' och '.join(allies)}.")
        lines.append(f"Som del av majoriteten röstar de JA i {p['for_pct']}% av frågorna — de flesta förslag har redan deras stöd innan omröstning.")
        if motions == 0:
            lines.append("De driver sina frågor genom budgeten och styrningen, inte genom motioner.")
    else:
        lines.append(f"{name} sitter i opposition i Örebro kommun.")
        if motions > 0:
            # Rank among opposition
            opp_motions = sorted(
                [(a, len(parties[a]["motions_filed"])) for a in parties if parties[a]["position"] == "Opposition" and len(parties[a]["motions_filed"]) > 0],
                key=lambda x: -x[1]
            )
            rank = next((i+1 for i, (a, _) in enumerate(opp_motions) if a == abbr), 0)
            rank_text = {1: "mest", 2: "näst mest", 3: "tredje mest"}.get(rank, f"{rank}:e mest")
            lines.append(f"De har lämnat {motions} motioner — {rank_text} aktiva i oppositionen.")

        if contested > 10:
            lines.append(f"De har röstat emot majoriteten i {contested} beslut.")

    # Top category
    if p["top_categories"]:
        top_cat = p["top_categories"][0][0]
        cat_names = {"bygg":"byggfrågor","infrastruktur":"infrastruktur","skola":"skolfrågor",
                     "budget":"budgetfrågor","miljö":"miljöfrågor","trygghet":"trygghetsfrågor",
                     "kultur":"kulturfrågor","politik":"politiska frågor","regler":"regelfrågor"}
        lines.append(f"{cat_names.get(top_cat, top_cat).capitalize()} är deras starkaste profilområde.")

    return " ".join(lines)


def _context_box(pos):
    """Explain majority vs opposition dynamics."""
    if pos == "Majoritet":
        return ("Vad betyder det att sitta i majoritet?",
                "Majoriteten (S+M+C) styr Örebro kommun. De flesta förslag som kommer till omröstning "
                "har redan deras stöd — därför röstar de JA i nästan alla frågor. Att de sällan lämnar "
                "motioner beror på att de driver sina frågor genom budgeten och styrningen.")
    else:
        return ("Vad betyder det att sitta i opposition?",
                "Oppositionen kan inte styra direkt, men påverkar genom motioner (egna förslag) och "
                "reservationer (formella protester). Att de 'förlorar' omröstningar beror på att "
                "majoriteten S+M+C har fler mandat — det är så minoritetspolitik fungerar i Sverige.")


def generate_party_pages(parties, base_url=""):
    """Generate enriched party profile pages based on design doc."""
    CE = {"bygg":"🏗️","infrastruktur":"🛣️","skola":"🏫","budget":"💰","miljö":"🌿",
          "miljo":"🌿","trygghet":"🛡️","kultur":"🎭","politik":"⚖️","regler":"📜","övrigt":"📋"}

    party_dir = SITE_DIR / "parti"
    party_dir.mkdir(exist_ok=True)

    # ── Overview page ──
    overview_cards = ""
    for abbr in ["S","M","C","L","KD","V","SD","ÖrP","MP"]:
        p = parties.get(abbr)
        if not p or p["total_votes"] == 0:
            continue
        motions_note = f'<div style="margin-top:8px;font-size:12px;color:#94a3b8">{len(p["motions_filed"])} motioner</div>' if p["motions_filed"] else ""
        overview_cards += f'''
<a href="{base_url}/parti/{abbr.lower()}/" class="party-card" style="border-left-color:{p['color']}">
<h3 style="color:{p['color']}">{p['name']}</h3>
<div class="pos">{p['position']} · {p['total_votes']} röstningar</div>
<div class="bar-row"><div class="for" style="width:{p['for_pct']}%"></div><div class="against" style="width:{p['against_pct']}%"></div><div class="abstain" style="width:{p['abstained_pct']}%"></div></div>
<div class="stats"><span style="color:#22c55e">JA {p['for_pct']}%</span><span style="color:#ef4444">NEJ {p['against_pct']}%</span><span>AVSTOD {p['abstained_pct']}%</span></div>
{motions_note}
</a>'''

    overview = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Partier i Örebro kommun — Beslutskollen</title>
<meta name="description" content="Hur röstar partierna i Örebro kommun? Se röstningsstatistik, nyckelfrågor och aktivitet per parti.">
<link rel="canonical" href="{base_url}/parti/">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,600&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Instrument Sans',system-ui,sans-serif;background:#f7f5f2;color:#1a1a1a}}a{{color:#0f1f33;text-decoration:none}}
header{{background:linear-gradient(160deg,#0a1628,#0f1f33 40%,#1e3a5f);color:#fff;padding:32px 24px}}
.wrap{{max-width:800px;margin:0 auto;padding:0 24px}}
.party-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-top:20px;padding-bottom:40px}}
.party-card{{background:#fff;border-radius:12px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.04);transition:box-shadow .2s;border-left:5px solid #ccc}}
.party-card:hover{{box-shadow:0 4px 16px rgba(0,0,0,.08)}}
.party-card h3{{font-size:16px;margin-bottom:4px}} .party-card .pos{{font-size:12px;color:#8a8a8a}}
.bar-row{{display:flex;height:8px;border-radius:4px;overflow:hidden;margin:10px 0 6px;background:#f0ece8}}
.bar-row .for{{background:#1a8754}} .bar-row .against{{background:#c44028}} .bar-row .abstain{{background:#d4d0cc}}
.party-card .stats{{font-size:12px;color:#8a8a8a;display:flex;gap:12px}}
footer{{border-top:1px solid #e8e4df;padding:20px 24px;text-align:center;font-size:11px;color:#8a8a8a}}
</style></head><body>
<header><div class="wrap">
<a href="{base_url}/" style="color:#fff;opacity:.7;font-size:13px">📋 Beslutskollen</a>
<h1 style="font-family:'Fraunces',serif;font-size:26px;font-weight:300;margin-top:8px">Partierna i Örebro kommun</h1>
<p style="font-size:14px;opacity:.6;margin-top:4px">Hur röstar de? Vilka frågor driver de? Baserat på {sum(p["total_votes"] for p in parties.values())} röstningar.</p>
</div></header>
<div class="wrap"><div class="party-grid">{overview_cards}</div></div>
<footer><p>Beslutskollen — AI-sammanfattningar av kommunala beslut. Kan innehålla fel.</p></footer></body></html>'''

    (party_dir / "index.html").write_text(overview, "utf-8")

    # ── Individual party pages ──
    for abbr in ["S","M","C","L","KD","V","SD","ÖrP","MP"]:
        p = parties.get(abbr)
        if not p or p["total_votes"] == 0:
            continue

        tc = "#333" if abbr == "SD" else "#fff"
        summary = _party_summary(abbr, p, parties)
        ctx_title, ctx_text = _context_box(p["position"])

        # ── Voting comparison bars (all parties) ──
        compare_html = ""
        for comp_abbr in ["S","M","C","L","KD","V","SD","ÖrP","MP"]:
            cp = parties.get(comp_abbr)
            if not cp or cp["total_votes"] == 0:
                continue
            is_current = comp_abbr == abbr
            bold = "font-weight:700;" if is_current else ""
            bg = "background:rgba(0,0,0,.03);" if is_current else ""
            compare_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:6px;{bg}">'
                f'<span style="width:28px;font-size:11px;{bold}color:{cp["color"]}">{comp_abbr}</span>'
                f'<div style="flex:1;display:flex;height:6px;border-radius:3px;overflow:hidden;background:#f0ece8">'
                f'<div style="width:{cp["for_pct"]}%;background:#1a8754"></div>'
                f'<div style="width:{cp["against_pct"]}%;background:#c44028"></div>'
                f'<div style="width:{cp["abstained_pct"]}%;background:#d4d0cc"></div></div>'
                f'<span style="width:55px;font-size:11px;color:#8a8a8a;text-align:right">{cp["against_pct"]}% nej</span></div>'
            )

        # ── Alliance bars ──
        alliance_html = ""
        all_agreements = sorted(p["agreement_with"].items(), key=lambda x: -x[1])
        for ally, count in all_agreements:
            if ally not in PARTIES_META:
                continue
            pct = round(count / max(p["total_votes"], 1) * 100)
            alliance_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0">'
                f'<span style="width:28px;font-size:11px;color:{PARTIES_META[ally]["color"]};font-weight:600">{ally}</span>'
                f'<div style="flex:1;height:6px;border-radius:3px;background:#f0ece8">'
                f'<div style="width:{pct}%;background:{PARTIES_META[ally]["color"]};border-radius:3px;height:100%"></div></div>'
                f'<span style="font-size:11px;color:#8a8a8a;width:55px;text-align:right">{pct}%</span></div>'
            )

        # ── Top issues bars ──
        max_cat_count = p["top_categories"][0][1] if p["top_categories"] else 1
        issues_html = ""
        for cat, count in p["top_categories"]:
            emoji = CE.get(cat, "📋")
            pct = round(count / max(max_cat_count, 1) * 100)
            issues_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0">'
                f'<span>{emoji}</span><span style="width:90px;font-size:13px">{cat.title()}</span>'
                f'<div style="flex:1;height:6px;border-radius:3px;background:#f0ece8">'
                f'<div style="width:{pct}%;background:{p["color"]};border-radius:3px;height:100%"></div></div>'
                f'<span style="font-size:12px;color:#8a8a8a;width:20px;text-align:right">{count}</span></div>'
            )

        # ── Motions grouped by category ──
        motions_by_cat = {}
        for mot in p["motions_filed"]:
            # Try to match motion to a category based on keywords
            cat = "övrigt"
            title_lower = mot["title"].lower()
            for c in CE:
                if c in title_lower:
                    cat = c
                    break
            motions_by_cat.setdefault(cat, []).append(mot)

        motions_html = ""
        for cat, mots in sorted(motions_by_cat.items(), key=lambda x: -len(x[1])):
            emoji = CE.get(cat, "📋")
            motions_html += f'<div style="margin-top:12px"><div style="font-size:12px;font-weight:700;color:#8a8a8a;margin-bottom:4px">{emoji} {cat.title()} ({len(mots)})</div>'
            for mot in mots:
                status = mot.get("status", "")
                icon = "✅" if "bifall" in status.lower() or "tillgodose" in status.lower() else "⏳" if "bered" in status.lower() or "bordl" in status.lower() else "❌"
                motions_html += f'<div style="padding:4px 0;font-size:13px;border-bottom:1px solid #f0ece8">{icon} {escape(mot["title"])}<br><span style="color:#8a8a8a;font-size:11px">{mot["date"]} · {status}</span></div>'
            motions_html += '</div>'

        # ── Contested votes (sorted by importance) ──
        contested_html = ""
        sorted_contested = sorted(p["contested_votes"], key=lambda x: x["date"], reverse=True)
        for cv in sorted_contested[:15]:
            contested_html += f'<a href="{base_url}/beslut/{cv["id"]}/" style="display:block;padding:6px 0;border-bottom:1px solid #f0ece8;color:#1a1a1a;font-size:13px"><span style="color:#8a8a8a">{cv["date"]}</span> · {escape(cv["headline"])}</a>'
        if len(sorted_contested) > 15:
            contested_html += f'<div style="font-size:12px;color:#8a8a8a;padding-top:6px">+ {len(sorted_contested) - 15} fler</div>'

        # ── Compare buttons ──
        compare_btns = ""
        for comp_abbr in ["S","M","C","L","KD","V","SD","ÖrP","MP"]:
            if comp_abbr == abbr:
                continue
            cp = parties.get(comp_abbr, {})
            if not cp.get("total_votes"):
                continue
            compare_btns += f'<a href="{base_url}/parti/{comp_abbr.lower()}/" style="display:inline-flex;align-items:center;gap:4px;padding:6px 12px;border-radius:6px;background:{cp.get("color","#999")};color:{"#333" if comp_abbr == "SD" else "#fff"};font-size:12px;font-weight:600">{comp_abbr}</a> '

        # ── Genomslagskraft ──
        granted = len([m for m in p["motions_filed"] if "bifall" in m.get("status","").lower() or "tillgodose" in m.get("status","").lower()])
        total_motions = len(p["motions_filed"])
        genomslag_pct = round(granted / max(total_motions, 1) * 100) if total_motions > 0 else 0

        page = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{p['name']} i Örebro kommun — Beslutskollen</title>
<meta name="description" content="Vad har {p['name']} gjort i Örebro kommun? Röstningsstatistik, motioner och politisk profil baserat på {p['total_votes']} röstningar.">
<link rel="canonical" href="{base_url}/parti/{abbr.lower()}/">
<meta property="og:title" content="{p['name']} — politisk profil Örebro kommun">
<meta property="og:description" content="{summary[:160]}">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,600&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Instrument Sans',system-ui,sans-serif;background:#f7f5f2;color:#1a1a1a;line-height:1.6}}
a{{color:#0f1f33;text-decoration:none}}
header{{background:linear-gradient(160deg,#0a1628,#0f1f33 40%,#1e3a5f);color:#fff;padding:28px 24px}}
.wrap{{max-width:700px;margin:0 auto;padding:0 24px}}
.summary{{font-size:15px;color:#4a4a4a;line-height:1.7;margin:16px 0;padding:16px 20px;background:#fff;border-radius:10px;border-left:4px solid {p['color']};box-shadow:0 1px 4px rgba(0,0,0,.03)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:10px;margin:16px 0}}
.stat{{background:#fff;border-radius:10px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.03)}}
.stat .val{{font-size:22px;font-weight:700}} .stat .lbl{{font-size:11px;color:#8a8a8a;margin-top:2px}}
.section{{background:#fff;border-radius:10px;padding:18px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.03)}}
.section h3{{font-size:11px;font-weight:700;color:#8a8a8a;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.8px}}
.context{{background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:14px 16px;margin-bottom:12px;font-size:13px;color:#92400e;line-height:1.6}}
.context summary{{font-weight:700;cursor:pointer;font-size:12px}}
.bar-big{{height:24px;border-radius:6px;display:flex;overflow:hidden;background:#f0ece8;margin:8px 0}}
.bar-big div{{display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:#fff}}
footer{{border-top:1px solid #e8e4df;padding:20px 24px;text-align:center;font-size:11px;color:#8a8a8a;margin-top:40px}}
@media(max-width:600px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>

<header><div class="wrap">
<div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;font-size:13px">
<a href="{base_url}/" style="color:#fff;opacity:.6">📋 Beslutskollen</a>
<span style="opacity:.3">›</span>
<a href="{base_url}/parti/" style="color:#fff;opacity:.6">Partier</a>
</div>
<div style="display:flex;align-items:center;gap:14px">
<div style="width:52px;height:52px;border-radius:12px;background:{p['color']};display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800;color:{tc}">{abbr}</div>
<div>
<h1 style="font-family:'Fraunces',serif;font-size:26px;font-weight:300">{p['name']}</h1>
<p style="font-size:13px;opacity:.6">{p['position']} · {p['ideology']}</p>
</div>
</div>
</div></header>

<div class="wrap" style="padding-top:16px;padding-bottom:40px">

<!-- 1. Summary -->
<div class="summary">{summary}</div>

<!-- 2. Key stats -->
<div class="stats">
<div class="stat"><div class="val">{p['total_votes']}</div><div class="lbl">Röstningar</div></div>
<div class="stat"><div class="val" style="color:#1a8754">{p['for_pct']}%</div><div class="lbl">Röstade JA</div></div>
<div class="stat"><div class="val" style="color:#c44028">{p['against_pct']}%</div><div class="lbl">Röstade NEJ</div></div>
<div class="stat"><div class="val">{total_motions}</div><div class="lbl">Motioner</div></div>
{f'<div class="stat"><div class="val">{genomslag_pct}%</div><div class="lbl">Genomslag</div></div>' if total_motions > 0 else ''}
<div class="stat"><div class="val">{p.get("attendance_pct", 0)}%</div><div class="lbl">Mötesnärvaro</div></div>
</div>

<div class="bar-big">
<div style="width:{p['for_pct']}%;background:#1a8754">JA {p['for_pct']}%</div>
<div style="width:{p['against_pct']}%;background:#c44028">{'NEJ ' + str(p['against_pct']) + '%' if p['against_pct'] >= 5 else ''}</div>
<div style="width:{p['abstained_pct']}%;background:#d4d0cc;color:#666">{'AVSTOD ' + str(p['abstained_pct']) + '%' if p['abstained_pct'] >= 5 else ''}</div>
</div>

<!-- 3. Context box -->
<details class="context">
<summary>{ctx_title}</summary>
<p style="margin-top:8px">{ctx_text}</p>
</details>

<!-- 4. Voting comparison -->
<div class="section">
<h3>Alla partier — jämförelse</h3>
<p style="font-size:12px;color:#8a8a8a;margin-bottom:8px">Grönt = JA, rött = NEJ. {p['name']} markerat.</p>
{compare_html}
</div>

<!-- 5. Alliances -->
<div class="section">
<h3>Röstar oftast lika som</h3>
<p style="font-size:12px;color:#8a8a8a;margin-bottom:8px">Andel beslut där de röstade på samma sida.</p>
{alliance_html}
</div>

<!-- 6. Attendance -->
{f"""<div class="section">
<h3>Närvaro på möten</h3>
<p style="font-size:12px;color:#8a8a8a;margin-bottom:8px">Närvarande vid {p.get('meetings_attended',0)} av {p.get('total_meetings_with_attendance',0)} sammanträden. Snitt {p.get('avg_present',0)} ledamöter per möte.</p>
<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
<div style="flex:1;height:8px;border-radius:4px;background:#f0ece8">
<div style="width:{p.get('attendance_pct',0)}%;height:100%;border-radius:4px;background:{p['color']}"></div>
</div>
<span style="font-size:13px;font-weight:600">{p.get('attendance_pct',0)}%</span>
</div>
</div>""" if p.get('meetings_attended', 0) > 0 else ''}

<!-- 7. Top issues -->
<div class="section">
<h3>Sakområden</h3>
{issues_html or '<p style="color:#8a8a8a;font-size:13px">Ingen data ännu</p>'}
</div>

<!-- 7. Contested decisions -->
{f"""<div class="section">
<h3>Stridslinjerna — röstade emot majoriteten</h3>
<p style="font-size:12px;color:#8a8a8a;margin-bottom:8px">De frågor {p['name']} tyckte var viktiga nog att ta strid om.</p>
{contested_html}
</div>""" if contested_html else ''}

<!-- 8. Motions -->
{f"""<div class="section">
<h3>Motioner — egna förslag</h3>
<p style="font-size:12px;color:#8a8a8a;margin-bottom:6px">{total_motions} motioner, {granted} bifallna/tillgodosedda ({genomslag_pct}% genomslag).</p>
{motions_html}
</div>""" if total_motions > 0 else ''}

<!-- 9. Compare -->
<div class="section">
<h3>Jämför med annat parti</h3>
<div style="display:flex;flex-wrap:wrap;gap:6px">{compare_btns}</div>
</div>

</div>
<footer><p>Beslutskollen — AI-sammanfattningar av kommunala beslut. Kan innehålla fel — kontrollera alltid originalprotokollet.</p></footer>
</body></html>'''

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
                        "date": m["date"], "meeting_type": m.get("meeting_type", m.get("organ", "")),
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
                "meeting_type": m.get("meeting_type", m.get("organ", "")),
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
