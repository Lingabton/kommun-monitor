"""
Beslutskollen — Attendance Extractor
=====================================
Extracts attendance data from the first 2 pages of each protocol PDF.
Uses Claude Haiku with a focused prompt — much cheaper than full summarization.

Outputs attendance data per meeting to output/{folder}/attendance.json

Usage:
    python attendance.py                    # Process all protocols
    python attendance.py --max 5            # Process 5 at a time
    python attendance.py --dry-run          # Show what would be processed
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")

try:
    import pdfplumber
except ImportError:
    sys.exit("pip install pdfplumber")

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
PDF_DIR = ROOT / "data" / "pdfs"

ATTENDANCE_PROMPT = """Extrahera närvarolistan från detta protokoll.

Räkna antal NÄRVARANDE ledamöter per parti. Inkludera BÅDE ordinarie ledamöter och tjänstgörande ersättare.

Partiförkortningar: S, M, C, L, KD, V, SD, ÖrP, MP

Räkna också:
- Totalt antal närvarande ledamöter
- Om det finns frånvarande ledamöter som nämns

Svara BARA med JSON:
{
  "total_present": 61,
  "parties": {
    "S": {"present": 20, "names": ["Jan Zetterqvist", "Anders Hagström"]},
    "M": {"present": 10, "names": ["Lucas Holmberg"]},
    "C": {"present": 5, "names": []},
    "L": {"present": 5, "names": []},
    "KD": {"present": 3, "names": []},
    "V": {"present": 5, "names": []},
    "SD": {"present": 5, "names": []},
    "ÖrP": {"present": 4, "names": []},
    "MP": {"present": 2, "names": []}
  },
  "absent_mentioned": ["Frederick Axewill (S)", "Håkan Jacobsson (M)"]
}

REGLER:
- names: lista ALLA närvarande namn (ordinarie + ersättare)
- ÖrP = Örebropartiet (inte OrP)
- Om du inte kan avgöra parti, skippa personen
- absent_mentioned: bara om protokollet explicit nämner frånvarande

--- PROTOKOLL (första sidorna) ---

"""


def extract_first_pages(pdf_path, max_pages=3):
    """Extract text from the first few pages of a PDF."""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n\n".join(parts)


def extract_attendance(text, api_key):
    """Use Claude Haiku to extract attendance from protocol text."""
    client = anthropic.Anthropic(api_key=api_key)

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": ATTENDANCE_PROMPT + text}]
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]

    return json.loads(raw), msg.usage


def find_pdf_for_meeting(folder_name):
    """Find the PDF file for a given output folder."""
    # Try exact match
    for pdf in PDF_DIR.glob("*.pdf"):
        if folder_name.replace("_", " ") in pdf.stem or folder_name in pdf.stem:
            return pdf

    # Try date-based match
    date = folder_name[:10]
    for pdf in PDF_DIR.glob("*.pdf"):
        if date in pdf.stem:
            return pdf

    return None


def main():
    parser = argparse.ArgumentParser(description="Extract attendance from protocols")
    parser.add_argument("--max", type=int, default=999, help="Max protocols to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit("Set ANTHROPIC_API_KEY")

    # Find all meetings that need attendance data
    to_process = []
    for folder in sorted(OUTPUT_DIR.iterdir()):
        if not folder.is_dir() or folder.name == "unknown_Manuell":
            continue
        attendance_file = folder / "attendance.json"
        if attendance_file.exists():
            continue
        summary_file = folder / "summary.json"
        if not summary_file.exists():
            continue
        to_process.append(folder)

    print(f"Meetings needing attendance: {len(to_process)}")
    if not to_process:
        print("All done!")
        return

    to_process = to_process[:args.max]
    print(f"Processing: {len(to_process)}")

    total_cost = 0
    success = 0

    for folder in to_process:
        pdf = find_pdf_for_meeting(folder.name)
        if not pdf:
            logger.warning(f"No PDF found for {folder.name}")
            continue

        if args.dry_run:
            print(f"  Would process: {folder.name} ({pdf.name})")
            continue

        print(f"  {folder.name}...", end=" ", flush=True)

        try:
            text = extract_first_pages(str(pdf), max_pages=3)
            if len(text) < 100:
                print("too short, skipping")
                continue

            attendance, usage = extract_attendance(text, api_key)

            # Save
            (folder / "attendance.json").write_text(
                json.dumps(attendance, ensure_ascii=False, indent=2), "utf-8"
            )

            cost = (usage.input_tokens * 0.25 + usage.output_tokens * 1.25) / 1_000_000
            total_cost += cost
            total_present = attendance.get("total_present", "?")
            parties_str = ", ".join(
                f"{p}:{d['present']}" for p, d in attendance.get("parties", {}).items()
                if d.get("present", 0) > 0
            )
            print(f"{total_present} ledamöter ({parties_str}) ${cost:.4f}")
            success += 1

        except Exception as e:
            print(f"ERROR: {e}")

        import time
        time.sleep(1)

    print(f"\nDone: {success} processed, ${total_cost:.4f} total cost")


if __name__ == "__main__":
    main()
