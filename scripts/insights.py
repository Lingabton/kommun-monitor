"""
Kommun Monitor — Insights Engine
===================================
Automatically generates political insights from voting data.

Produces:
1. Power Analysis — majority dominance, democratic health metrics
2. Unusual Coalitions — when parties that normally disagree vote together
3. Decision Timelines — linked decisions over time (Eyrafältet saga etc)
4. Opposition Effectiveness — do motions lead to change?
5. Trend Analysis — are decisions getting more contested?
6. Attention Score — which decisions deserve most public attention?

Run after analytics.py, outputs to site/api/v1/insights.json
and generates site/insikter/index.html
"""

import json
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime
from itertools import combinations

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site"

PARTIES_META = {
    "S": {"name":"Socialdemokraterna","block":"majority"},
    "M": {"name":"Moderaterna","block":"majority"},
    "C": {"name":"Centerpartiet","block":"majority"},
    "L": {"name":"Liberalerna","block":"opposition"},
    "KD": {"name":"Kristdemokraterna","block":"opposition"},
    "V": {"name":"Vänsterpartiet","block":"opposition"},
    "SD": {"name":"Sverigedemokraterna","block":"opposition"},
    "ÖrP": {"name":"Örebropartiet","block":"opposition"},
    "MP": {"name":"Miljöpartiet","block":"opposition"},
}
MAJORITY = {"S","M","C"}
OPPOSITION = {"L","KD","V","SD","ÖrP","MP"}
PC = {"S":"#e8112d","M":"#52bdec","C":"#009933","L":"#006ab3","KD":"#231977",
      "V":"#da291c","SD":"#eab308","ÖrP":"#f47920","MP":"#83cf39"}


def load_data():
    return json.loads((SITE_DIR / "data.json").read_text("utf-8"))


def get_all_decisions(data):
    """Flatten all decisions with meeting context."""
    out = []
    for m in data.get("meetings", []):
        for d in m.get("decisions", []):
            out.append({
                **d,
                "meeting_id": m["id"],
                "date": m["date"],
                "meeting_type": m.get("type", m.get("meeting_type", "")),
            })
    return out


# ═══════════════════════════════════════════
# 1. POWER ANALYSIS
# ═══════════════════════════════════════════

def analyze_power(decisions):
    """How dominant is the majority? How often does opposition lose?"""
    total_voted = 0
    majority_wins = 0
    unanimous = 0
    opposition_united_but_lost = 0
    votering_count = 0

    for d in decisions:
        v = d.get("vote", d.get("voting"))
        if not v:
            continue
        total_voted += 1

        f = set(v.get("f", v.get("for", [])))
        a = set(v.get("a", v.get("against", [])))
        r = v.get("r", v.get("result", ""))

        if not a:
            unanimous += 1
            majority_wins += 1
            continue

        # Did majority win?
        maj_voted_for = bool(MAJORITY & f)
        maj_voted_against = bool(MAJORITY & a)
        if maj_voted_for and not maj_voted_against:
            majority_wins += 1

        # Was opposition united against?
        opp_against = OPPOSITION & a
        opp_for = OPPOSITION & f
        if len(opp_against) >= 4 and len(opp_for) <= 1:
            opposition_united_but_lost += 1

        if "votering" in r.lower():
            votering_count += 1

    pct = round(majority_wins / max(total_voted, 1) * 100)
    unan_pct = round(unanimous / max(total_voted, 1) * 100)

    return {
        "total_voted_decisions": total_voted,
        "majority_wins": majority_wins,
        "majority_win_pct": pct,
        "unanimous_decisions": unanimous,
        "unanimous_pct": unan_pct,
        "opposition_united_but_lost": opposition_united_but_lost,
        "formal_votes": votering_count,
        "majority_parties": list(MAJORITY),
        "interpretation": _interpret_power(pct, unan_pct, opposition_united_but_lost, votering_count, total_voted),
    }


def _interpret_power(pct, unan_pct, opp_lost, vot, total):
    lines = []
    if pct >= 95:
        lines.append(f"Majoriteten (S, M, C) vinner {pct}% av alla röstningar — i praktiken total kontroll.")
    elif pct >= 80:
        lines.append(f"Majoriteten vinner {pct}% av röstningarna — stark dominans men oppositionen har visst inflytande.")

    if unan_pct >= 40:
        lines.append(f"{unan_pct}% av besluten är enhälliga — det mesta är opolitiskt.")
    elif unan_pct < 15:
        lines.append(f"Bara {unan_pct}% är enhälliga — politiken i Örebro är ovanligt polariserad.")

    if opp_lost >= 3:
        lines.append(f"Vid {opp_lost} av {total} tillfällen var oppositionen samlad emot — men förlorade ändå varje gång.")

    if vot >= 3:
        lines.append(f"{vot} formella voteringer visar att konfliktnivån är hög.")

    return " ".join(lines)


# ═══════════════════════════════════════════
# 2. UNUSUAL COALITIONS
# ═══════════════════════════════════════════

def find_unusual_coalitions(decisions):
    """Find decisions where parties that normally disagree voted together."""
    # Define "unusual" pairs — parties from different ideological camps
    unusual_pairs = [
        ("V", "SD"),   # far left + far right
        ("V", "KD"),   # left + christian dem
        ("SD", "MP"),  # right populist + green
        ("V", "L"),    # socialist + liberal
        ("SD", "V"),   # duplicate for clarity
        ("ÖrP", "V"),  # local party + left
    ]

    results = []
    for d in decisions:
        v = d.get("vote", d.get("voting"))
        if not v:
            continue
        f = set(v.get("f", v.get("for", [])))
        a = set(v.get("a", v.get("against", [])))

        for side, label in [(f, "JA"), (a, "NEJ")]:
            for p1, p2 in unusual_pairs:
                if p1 in side and p2 in side:
                    results.append({
                        "decision_id": d["id"],
                        "headline": d.get("hl", d.get("headline", "")),
                        "date": d["date"],
                        "coalition": sorted([p1, p2]),
                        "side": label,
                        "all_on_side": sorted(side),
                        "surprise_level": "high" if {p1,p2} == {"V","SD"} else "medium",
                        "narrative": f"{p1} och {p2} röstade båda {label} — ovanligt då de normalt står långt ifrån varandra.",
                    })

    # Deduplicate (same decision can match multiple pairs)
    seen = set()
    unique = []
    for r in results:
        key = (r["decision_id"], tuple(r["coalition"]))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return sorted(unique, key=lambda x: (0 if x["surprise_level"]=="high" else 1, x["date"]), reverse=False)


# ═══════════════════════════════════════════
# 3. DECISION TIMELINES
# ═══════════════════════════════════════════

def find_timelines(decisions):
    """Group related decisions into timelines based on shared tags."""
    # Build tag → decision index
    tag_map = defaultdict(list)
    for d in decisions:
        for tag in d.get("tags", []):
            tag_map[tag.lower()].append(d)

    timelines = []
    seen_groups = set()

    for tag, decs in tag_map.items():
        if len(decs) < 2:
            continue
        # Create a unique key for this group
        ids = tuple(sorted(d["id"] for d in decs))
        if ids in seen_groups:
            continue
        seen_groups.add(ids)

        sorted_decs = sorted(decs, key=lambda x: x["date"])
        span_days = (datetime.strptime(sorted_decs[-1]["date"], "%Y-%m-%d") -
                     datetime.strptime(sorted_decs[0]["date"], "%Y-%m-%d")).days

        if span_days < 30:
            continue  # Same meeting, not interesting

        timelines.append({
            "tag": tag,
            "decisions_count": len(decs),
            "span_days": span_days,
            "first_date": sorted_decs[0]["date"],
            "last_date": sorted_decs[-1]["date"],
            "decisions": [{
                "id": d["id"],
                "headline": d.get("hl", d.get("headline", "")),
                "date": d["date"],
                "summary": d.get("sum", d.get("summary", "")),
            } for d in sorted_decs],
            "narrative": _narrate_timeline(tag, sorted_decs, span_days),
        })

    return sorted(timelines, key=lambda x: -x["span_days"])


def _narrate_timeline(tag, decs, span_days):
    months = span_days // 30
    return f"'{tag}' har dykt upp i {len(decs)} beslut under {months} månader ({decs[0]['date']} → {decs[-1]['date']})."


# ═══════════════════════════════════════════
# 4. OPPOSITION EFFECTIVENESS
# ═══════════════════════════════════════════

def analyze_opposition(decisions, data):
    """How effective is the opposition? Do motions lead to change?"""
    motions = []
    for m in data.get("meetings", []):
        for mot in m.get("motions_of_interest", m.get("motions", [])):
            motions.append({
                "title": mot.get("t", mot.get("title", "")),
                "party": mot.get("p", mot.get("party", "")),
                "status": mot.get("s", mot.get("status", "")),
                "date": m["date"],
            })

    party_motions = defaultdict(list)
    for mot in motions:
        party_motions[mot["party"]].append(mot)

    # Count reservations (voting against) per party
    party_reservations = defaultdict(int)
    for d in decisions:
        v = d.get("vote", d.get("voting"))
        if not v:
            continue
        for p in v.get("a", v.get("against", [])):
            party_reservations[p] += 1

    # Calculate opposition effectiveness per party
    results = []
    for party in OPPOSITION:
        mots = party_motions.get(party, [])
        reserv = party_reservations.get(party, 0)
        bifallen = len([m for m in mots if "bifall" in m["status"].lower()])

        results.append({
            "party": party,
            "name": PARTIES_META.get(party, {}).get("name", party),
            "motions_filed": len(mots),
            "motions_granted": bifallen,
            "reservations": reserv,
            "effectiveness_score": round((bifallen / max(len(mots), 1)) * 100),
            "motions": mots,
            "interpretation": _interpret_opposition(party, len(mots), bifallen, reserv),
        })

    return sorted(results, key=lambda x: -x["motions_filed"])


def _interpret_opposition(party, filed, granted, reserv):
    if filed == 0 and reserv == 0:
        return f"{party} har varken lagt motioner eller reserverat sig — låg aktivitet."
    if filed > 0 and granted == 0:
        return f"{party} har lagt {filed} motioner men ingen har bifallits. {reserv} reservationer totalt."
    if granted > 0:
        return f"{party} har fått {granted} av {filed} motioner bifallna — ovanligt framgångsrik opposition."
    return f"{party} har reserverat sig {reserv} gånger."


# ═══════════════════════════════════════════
# 5. TREND ANALYSIS
# ═══════════════════════════════════════════

def analyze_trends(decisions):
    """Are decisions getting more contested over time?"""
    by_month = defaultdict(lambda: {"total": 0, "contested": 0, "unanimous": 0, "voteringer": 0})

    for d in decisions:
        month = d["date"][:7]  # YYYY-MM
        by_month[month]["total"] += 1
        if d.get("contested"):
            by_month[month]["contested"] += 1
        v = d.get("vote", d.get("voting"))
        if v:
            r = v.get("r", v.get("result", ""))
            if "enhälligt" in r.lower():
                by_month[month]["unanimous"] += 1
            if "votering" in r.lower():
                by_month[month]["voteringer"] += 1

    trend_data = []
    for month in sorted(by_month.keys()):
        m = by_month[month]
        trend_data.append({
            "month": month,
            **m,
            "contested_pct": round(m["contested"] / max(m["total"], 1) * 100),
        })

    return {
        "months": trend_data,
        "overall_contested_pct": round(
            sum(m["contested"] for m in by_month.values()) /
            max(sum(m["total"] for m in by_month.values()), 1) * 100
        ),
    }


# ═══════════════════════════════════════════
# 6. ATTENTION SCORE
# ═══════════════════════════════════════════

def score_decisions(decisions):
    """Score each decision by how much public attention it deserves."""
    scored = []
    for d in decisions:
        score = 0
        reasons = []

        # Contested = base attention
        if d.get("contested"):
            score += 20
            reasons.append("Omstritt")

        v = d.get("vote", d.get("voting"))
        if v:
            r = v.get("r", v.get("result", ""))
            a = v.get("a", v.get("against", []))
            f = v.get("f", v.get("for", []))

            # Formal vote
            if "votering" in r.lower():
                score += 25
                reasons.append("Gick till votering")

            # Large opposition
            if len(a) >= 4:
                score += 15
                reasons.append(f"{len(a)} partier emot")

            # Unusual coalition
            against_set = set(a)
            if "V" in against_set and "SD" in against_set:
                score += 20
                reasons.append("V och SD på samma sida")
            elif "V" in against_set and "KD" in against_set:
                score += 10
                reasons.append("Bred ideologisk opposition")

            # Close to unanimous opposition
            for_set = set(f)
            if for_set.issubset(MAJORITY) and len(against_set) >= 5:
                score += 15
                reasons.append("Bara majoriteten för — resten emot")

        # Budget/money topics
        cat = d.get("cat", d.get("category", ""))
        detail = d.get("detail", "")
        if cat == "budget" or any(w in detail.lower() for w in ["msek", "mnkr", "miljoner"]):
            score += 10
            reasons.append("Handlar om pengar")

        # Location-specific (affects real people in real places)
        if d.get("loc", d.get("location")):
            score += 5
            reasons.append("Berör specifikt område")

        scored.append({
            "id": d["id"],
            "headline": d.get("hl", d.get("headline", "")),
            "date": d["date"],
            "score": min(score, 100),
            "reasons": reasons,
            "category": cat,
        })

    return sorted(scored, key=lambda x: -x["score"])


# ═══════════════════════════════════════════
# GENERATE INSIGHTS PAGE
# ═══════════════════════════════════════════

def generate_insights_page(insights, base_url=""):
    """Generate the insights HTML page."""
    power = insights["power_analysis"]
    coalitions = insights["unusual_coalitions"]
    timelines = insights["timelines"]
    opposition = insights["opposition_effectiveness"]
    trends = insights["trends"]
    top_decisions = insights["attention_ranking"][:5]

    # Build HTML sections
    top_html = ""
    for i, d in enumerate(top_decisions):
        bar_w = d["score"]
        top_html += f'''<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
<div style="width:36px;height:36px;border-radius:8px;background:{'#ef4444' if d['score']>=60 else '#f59e0b' if d['score']>=30 else '#3b82f6'};display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:#fff;flex-shrink:0">{d['score']}</div>
<div style="flex:1;min-width:0"><div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{d['headline']}</div>
<div style="font-size:11px;color:#64748b;margin-top:2px">{', '.join(d['reasons'][:3])}</div></div>
<div style="font-size:11px;color:#475569">{d['date']}</div></div>'''

    coal_html = ""
    for c in coalitions[:5]:
        parties = " + ".join(c["coalition"])
        coal_html += f'''<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:13px">
<div style="display:flex;align-items:center;gap:6px"><span style="background:{'#ef444420' if c['surprise_level']=='high' else '#f59e0b20'};color:{'#ef4444' if c['surprise_level']=='high' else '#f59e0b'};padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700">{parties}</span>
<span style="color:#94a3b8">röstade {c['side']}</span></div>
<div style="color:#cbd5e1;margin-top:3px">{c['headline']}</div></div>'''

    timeline_html = ""
    for t in timelines[:3]:
        dots = ""
        for d in t["decisions"]:
            dots += f'<div style="padding:6px 0 6px 16px;border-left:2px solid rgba(255,255,255,0.1);font-size:12px"><span style="color:#64748b">{d["date"]}</span> — {d["headline"]}</div>'
        timeline_html += f'''<div style="margin-bottom:16px">
<div style="font-size:13px;font-weight:600;color:#60a5fa;margin-bottom:6px">🔗 {t['tag']} ({t['decisions_count']} beslut, {t['span_days']} dagar)</div>
{dots}</div>'''

    opp_html = ""
    for o in opposition:
        if o["motions_filed"] == 0 and o["reservations"] == 0:
            continue
        opp_html += f'''<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
<span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:5px;background:{PC.get(o['party'],'#666')};color:{'#1a1a00' if o['party']=='SD' else '#fff'};font-size:11px;font-weight:800">{o['party']}</span>
<div style="flex:1;font-size:13px"><strong>{o['name']}</strong></div>
<div style="font-size:12px;color:#94a3b8">{o['motions_filed']} motioner · {o['reservations']} reservationer</div></div>'''

    # Pre-build trend chart bars (avoid nested f-strings)
    trend_bars = ""
    trend_labels = ""
    for m in trends["months"]:
        color = "#ef4444" if m["contested_pct"] >= 70 else "#f59e0b" if m["contested_pct"] >= 40 else "#3b82f6"
        h = max(m["contested_pct"], 5)
        trend_bars += f'<div title="{m["month"]}: {m["contested"]}/{m["total"]}" style="flex:1;background:{color};border-radius:3px 3px 0 0;height:{h}%;min-height:4px;opacity:0.8"></div>'
        trend_labels += f'<span>{m["month"][5:]}</span>'

    page = f'''<!DOCTYPE html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Politiska insikter — Örebro kommun — Kommun Monitor</title>
<meta name="description" content="Djupanalys av Örebro kommunpolitik. Maktbalans, ovanliga allianser, oppositionens effektivitet och trender.">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,600;1,9..144,400&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Instrument Sans',sans-serif;background:#0c1219;color:#e2e8f0;line-height:1.6}}
a{{color:#60a5fa;text-decoration:none}}
.wrap{{max-width:800px;margin:0 auto;padding:0 24px}}
header{{padding:32px 0 24px;border-bottom:1px solid rgba(255,255,255,0.06)}}
.card{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px;margin-bottom:16px}}
.card h2{{font-family:'Fraunces',serif;font-size:20px;font-weight:400;margin:0 0 4px}}
.card .sub{{font-size:13px;color:#64748b;margin-bottom:14px}}
.stat-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:16px}}
.stat{{background:rgba(255,255,255,0.04);border-radius:8px;padding:12px;text-align:center}}
.stat .v{{font-size:28px;font-weight:700;font-family:'Fraunces',serif}} .stat .l{{font-size:11px;color:#64748b;margin-top:2px}}
.interp{{font-size:14px;color:#94a3b8;line-height:1.7;padding:12px 16px;background:rgba(255,255,255,0.02);border-radius:8px;border-left:3px solid #3b82f6}}
footer{{padding:20px 0;border-top:1px solid rgba(255,255,255,0.06);margin-top:32px;text-align:center;font-size:12px;color:#475569}}
</style></head><body>
<div class="wrap">
<header>
<div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;font-size:13px">
<a href="{base_url}/" style="color:#64748b">🏛️ Kommun Monitor</a>
<span style="color:#333">›</span>
<span>Insikter</span>
</div>
<h1 style="font-family:'Fraunces',serif;font-size:30px;font-weight:300">Politiska insikter</h1>
<p style="font-size:14px;color:#64748b;margin-top:4px">Automatiskt genererad djupanalys av {power['total_voted_decisions']} beslut i Örebro kommun</p>
</header>

<div style="padding-top:20px">

<!-- POWER ANALYSIS -->
<div class="card">
<h2>⚖️ Maktbalans</h2>
<div class="sub">Hur dominerar S+M+C i Örebro?</div>
<div class="stat-row">
<div class="stat"><div class="v" style="color:#22c55e">{power['majority_win_pct']}%</div><div class="l">Majoritetens vinster</div></div>
<div class="stat"><div class="v">{power['unanimous_pct']}%</div><div class="l">Enhälliga beslut</div></div>
<div class="stat"><div class="v" style="color:#ef4444">{power['opposition_united_but_lost']}</div><div class="l">Samlad opposition förlorade</div></div>
<div class="stat"><div class="v" style="color:#f59e0b">{power['formal_votes']}</div><div class="l">Formella voteringer</div></div>
</div>
<div class="interp">{power['interpretation']}</div>
</div>

<!-- ATTENTION RANKING -->
<div class="card">
<h2>🔥 Mest uppmärksamhetsvärda besluten</h2>
<div class="sub">Automatiskt rankat efter konfliktnivå, ovanliga allianser och ekonomisk påverkan</div>
{top_html}
</div>

<!-- UNUSUAL COALITIONS -->
<div class="card">
<h2>🤝 Ovanliga allianser</h2>
<div class="sub">Partier som normalt står långt ifrån varandra men röstade på samma sida</div>
{coal_html if coal_html else '<div style="font-size:13px;color:#475569">Ingen data ännu</div>'}
</div>

<!-- TIMELINES -->
<div class="card">
<h2>📅 Beslut som hänger ihop</h2>
<div class="sub">Samma fråga dyker upp i flera beslut under lång tid</div>
{timeline_html if timeline_html else '<div style="font-size:13px;color:#475569">Ingen data ännu</div>'}
</div>

<!-- OPPOSITION -->
<div class="card">
<h2>📣 Oppositionens aktivitet</h2>
<div class="sub">Vilka partier driver frågor och reserverar sig?</div>
{opp_html}
</div>

<!-- TRENDS -->
<div class="card">
<h2>📈 Trender</h2>
<div class="sub">{trends['overall_contested_pct']}% av alla beslut är omstridda</div>
<div style="display:flex;gap:4px;align-items:flex-end;height:60px;margin-top:8px">
{trend_bars}
</div>
<div style="display:flex;justify-content:space-between;font-size:10px;color:#475569;margin-top:4px">
{trend_labels}
</div>
</div>

</div>
<footer><p>Kommun Monitor — AI-genererad analys av offentliga protokoll</p></footer>
</div></body></html>'''

    out_dir = SITE_DIR / "insikter"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(page, "utf-8")


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate political insights")
    parser.add_argument("--base-url", default="https://lingabton.github.io/kommun-monitor")
    args = parser.parse_args()

    data = load_data()
    decisions = get_all_decisions(data)
    print(f"🧠 Analyzing {len(decisions)} decisions...")

    insights = {}

    print("\n⚖️ Power analysis...")
    insights["power_analysis"] = analyze_power(decisions)
    pa = insights["power_analysis"]
    print(f"   Majority wins: {pa['majority_win_pct']}% | Unanimous: {pa['unanimous_pct']}% | Opposition lost united: {pa['opposition_united_but_lost']}")

    print("\n🤝 Unusual coalitions...")
    insights["unusual_coalitions"] = find_unusual_coalitions(decisions)
    print(f"   Found {len(insights['unusual_coalitions'])} unusual coalition votes")

    print("\n📅 Decision timelines...")
    insights["timelines"] = find_timelines(decisions)
    print(f"   Found {len(insights['timelines'])} multi-decision timelines")

    print("\n📣 Opposition effectiveness...")
    insights["opposition_effectiveness"] = analyze_opposition(decisions, data)
    for o in insights["opposition_effectiveness"]:
        if o["motions_filed"] > 0:
            print(f"   {o['party']:3s}: {o['motions_filed']} motioner, {o['reservations']} reservationer")

    print("\n📈 Trend analysis...")
    insights["trends"] = analyze_trends(decisions)
    print(f"   Overall contested: {insights['trends']['overall_contested_pct']}%")

    print("\n🔥 Attention ranking...")
    insights["attention_ranking"] = score_decisions(decisions)
    for d in insights["attention_ranking"][:3]:
        print(f"   [{d['score']:3d}] {d['headline'][:60]}")

    # Save as API endpoint
    api_dir = SITE_DIR / "api" / "v1"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "insights.json").write_text(
        json.dumps(insights, ensure_ascii=False, indent=2, default=str), "utf-8")
    print(f"\n   → api/v1/insights.json")

    # Generate HTML page
    generate_insights_page(insights, args.base_url)
    print(f"   → insikter/index.html")

    print("\n✅ Insights complete!")


if __name__ == "__main__":
    main()
