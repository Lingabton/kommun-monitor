"""
Aggregates all output/*/summary.json into site/data.json
so the website and build_site.py can read them.

Deduplicates meetings with the same date+organ (prefers fuller data).

Usage:
    python3 aggregate.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
SITE_DIR = ROOT / "site"
DATA_FILE = SITE_DIR / "data.json"


def aggregate():
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all meetings, keyed by date+organ for dedup
    by_key = {}

    for summary_file in sorted(OUTPUT_DIR.glob("*/summary.json")):
        folder = summary_file.parent.name
        if folder == "unknown_Manuell":
            continue

        data = json.loads(summary_file.read_text("utf-8"))

        organ = data.get("organ") or data.get("meeting_type") or "Okänt"
        date = data.get("meeting_date") or data.get("date") or "unknown"
        decisions = data.get("decisions", [])

        for d in decisions:
            d["organ"] = organ
            d["meeting_date"] = date

        meeting = {
            "organ": organ,
            "date": date,
            "decisions": decisions,
            "decisions_count": len(decisions),
            "source_url": data.get("pdf_path", ""),
            "headline": data.get("summary_headline", ""),
            "motions_of_interest": data.get("motions_of_interest", []),
        }

        # Dedup: keep the version with more decisions
        key = f"{date}_{organ}"
        if key not in by_key or len(decisions) > by_key[key]["decisions_count"]:
            by_key[key] = meeting

    meetings = sorted(by_key.values(), key=lambda m: m["date"], reverse=True)
    total_decisions = sum(m["decisions_count"] for m in meetings)

    site_data = {
        "total_meetings": len(meetings),
        "total_decisions": total_decisions,
        "meetings": meetings,
    }

    DATA_FILE.write_text(json.dumps(site_data, ensure_ascii=False, indent=2), "utf-8")

    print(f"✅ Aggregated {len(meetings)} meetings, {total_decisions} decisions")
    print(f"   → {DATA_FILE}")


if __name__ == "__main__":
    aggregate()
