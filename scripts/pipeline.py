"""
Kommun Monitor — Automated Pipeline
=====================================
Orchestrates the full flow:
    1. Discover new protocols (RSS + Google)
    2. Download PDFs
    3. Summarize with Claude AI
    4. Build static site
    5. (Optional) Git commit + push

This is what runs in GitHub Actions on the daily cron.

Usage:
    python pipeline.py                    # Full auto run
    python pipeline.py --discover-only    # Just check for new protocols
    python pipeline.py --process URL      # Process a specific PDF URL
    python pipeline.py --retry            # Retry protocols missing PDFs
    python pipeline.py --dry-run          # Show what would happen
    python pipeline.py --backfill 2025    # Backfill historical protocols
"""

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Import our modules
from discovery import (
    discover_new_protocols,
    retry_pending,
    backfill_from_google,
    get_pending_protocols,
    load_state as load_discovery_state,
    MONITORED_ORGANS,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = ROOT / "output"
SITE_DIR = ROOT / "site"
LOG_DIR = ROOT / "logs"

HEADERS = {
    "User-Agent": "KommunMonitor/2.0 (https://github.com/lingabton/kommun-monitor)"
}

# Processing state — tracks which PDFs have been processed
PROCESS_STATE_FILE = DATA_DIR / "process_state.json"


def parse_organ_date_from_url(url: str) -> tuple[str, str]:
    """
    Extract organ name and date from a protocol PDF URL.
    Example: '.../2025-11-11%20Kommunstyrelsen.pdf' → ('Kommunstyrelsen', '2025-11-11')
    """
    from urllib.parse import unquote
    filename = unquote(url.split("/")[-1]).replace(".pdf", "")
    # Match pattern: "2025-11-11 Kommunstyrelsen" or "2025-11-11  Kommunstyrelsen § 207-209"
    match = re.match(r"(\d{4}-\d{2}-\d{2})\s+(.+?)(?:\s*§.*)?$", filename)
    if match:
        return match.group(2).strip(), match.group(1)
    return "Okänt", "unknown"


# ─────────────────────────────────────────────
# PDF DOWNLOAD
# ─────────────────────────────────────────────

def download_pdf(url: str, organ: str, meeting_date: str) -> Path | None:
    """
    Download a protocol PDF to the local pdfs directory.
    Returns the local file path or None on failure.
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Clean filename
    safe_organ = organ.replace(" ", "_").replace("/", "-")
    filename = f"{meeting_date}_{safe_organ}.pdf"
    filepath = PDF_DIR / filename

    if filepath.exists():
        logger.info(f"PDF already downloaded: {filename}")
        return filepath

    try:
        logger.info(f"Downloading: {url}")
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        r.raise_for_status()

        # Verify it's actually a PDF
        content_type = r.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not r.content[:5] == b"%PDF-":
            logger.error(f"Not a PDF: {url} (content-type: {content_type})")
            return None

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = filepath.stat().st_size / 1024
        logger.info(f"Downloaded: {filename} ({size_kb:.0f} KB)")
        return filepath

    except requests.RequestException as e:
        logger.error(f"Download failed: {url} — {e}")
        return None


# ─────────────────────────────────────────────
# PROCESSING STATE
# ─────────────────────────────────────────────

def load_process_state() -> dict:
    """Load processing state."""
    if PROCESS_STATE_FILE.exists():
        return json.loads(PROCESS_STATE_FILE.read_text("utf-8"))
    return {"processed": {}, "last_run": None}


def save_process_state(state: dict):
    """Save processing state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now().isoformat()
    PROCESS_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), "utf-8"
    )


def is_processed(pdf_url: str, state: dict) -> bool:
    """Check if a PDF has already been processed."""
    if not pdf_url:
        return True
    url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
    return url_hash in state["processed"]


def mark_processed(pdf_url: str, state: dict, result: dict):
    """Mark a PDF as processed."""
    url_hash = hashlib.md5(pdf_url.encode()).hexdigest()
    state["processed"][url_hash] = {
        "url": pdf_url,
        "processed_at": datetime.now().isoformat(),
        "organ": result.get("organ", ""),
        "meeting_date": result.get("meeting_date", ""),
        "decisions_count": result.get("decisions_count", 0),
        "status": result.get("status", "ok"),
    }


# ─────────────────────────────────────────────
# SUMMARIZATION (calls existing summarizer)
# ─────────────────────────────────────────────

def process_protocol(
    pdf_path: Path,
    organ: str,
    meeting_date: str,
    dry_run: bool = False,
) -> dict | None:
    """
    Process a single protocol PDF through the AI summarizer.

    This imports and uses the existing summarizer module.
    Returns the summary result dict or None on failure.
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would process: {organ} {meeting_date} ({pdf_path})")
        return {"status": "dry_run", "organ": organ, "meeting_date": meeting_date}

    try:
        # Import here to avoid import errors if summarizer isn't available
        from summarizer import extract_text_from_pdf, summarize_protocol

        # Extract text
        logger.info(f"Extracting text from {pdf_path.name}...")
        text = extract_text_from_pdf(str(pdf_path))
        if not text or len(text) < 100:
            logger.warning(f"Too little text extracted from {pdf_path.name}: {len(text or '')} chars")
            return {"status": "empty", "organ": organ, "meeting_date": meeting_date, "decisions_count": 0}

        # Summarize with AI
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY not set")
            return {"status": "error", "organ": organ, "meeting_date": meeting_date, "error": "No API key"}

        model = os.environ.get("KOMMUN_MODEL", "haiku")
        logger.info(f"Summarizing {organ} {meeting_date} ({len(text)} chars) with {model}...")
        result = summarize_protocol(text, api_key, model=model)

        if result:
            result["organ"] = organ
            result["meeting_date"] = meeting_date
            result["pdf_path"] = str(pdf_path)
            result["status"] = "ok"
            result["decisions_count"] = len(result.get("decisions", []))
            logger.info(f"Summarized: {result['decisions_count']} decisions")

            # Save output
            save_output(result, organ, meeting_date)

        return result

    except ImportError:
        logger.error(
            "summarizer module not found. Make sure summarizer.py / kommun_monitor.py "
            "is in the scripts directory."
        )
        return None
    except Exception as e:
        logger.error(f"Processing failed for {organ} {meeting_date}: {e}")
        return {"status": "error", "organ": organ, "meeting_date": meeting_date, "error": str(e)}


def save_output(result: dict, organ: str, meeting_date: str):
    """Save processing output to the output directory."""
    safe_organ = organ.replace(" ", "_")
    out_dir = OUTPUT_DIR / f"{meeting_date}_{safe_organ}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save full result
    output_file = out_dir / "summary.json"
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    logger.info(f"Saved output to {output_file}")


# ─────────────────────────────────────────────
# SITE BUILD
# ─────────────────────────────────────────────

def build_site():
    """Run the static site builder."""
    build_script = ROOT / "scripts" / "build_site.py"
    if not build_script.exists():
        logger.warning("build_site.py not found. Skipping site build.")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Site built successfully")
            return True
        else:
            logger.error(f"Site build failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Site build error: {e}")
        return False


def git_commit_and_push(message: str = None):
    """Commit and push changes (for GitHub Actions)."""
    if not message:
        message = f"Auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    try:
        subprocess.run(["git", "add", "-A"], cwd=str(ROOT), check=True)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if not result.stdout.strip():
            logger.info("No changes to commit.")
            return

        subprocess.run(["git", "commit", "-m", message], cwd=str(ROOT), check=True)
        subprocess.run(["git", "push"], cwd=str(ROOT), check=True)
        logger.info(f"Committed and pushed: {message}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Git error: {e}")


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(
    dry_run: bool = False,
    skip_build: bool = False,
    skip_git: bool = False,
    max_process: int = 5,
) -> dict:
    """
    Run the full pipeline:
    1. Discover new protocols from RSS
    2. Download PDFs
    3. Process through AI
    4. Build site
    5. Git commit + push

    Returns a summary dict.
    """
    summary = {
        "started": datetime.now().isoformat(),
        "discovered": 0,
        "downloaded": 0,
        "processed": 0,
        "errors": 0,
        "decisions_total": 0,
    }

    # Step 1: Discover
    logger.info("=" * 60)
    logger.info("STEP 1: Discovering new protocols...")
    logger.info("=" * 60)

    protocols = discover_new_protocols()
    summary["discovered"] = len(protocols)

    if not protocols:
        logger.info("No new protocols. Checking for pending retries...")
        retry_found = retry_pending(max_retries=3)
        if retry_found:
            logger.info(f"Retry found {len(retry_found)} PDFs")
            # Convert to protocol format for processing
            protocols = [
                {
                    "organ_display": p["organ"],
                    "meeting_date": p["meeting_date"],
                    "pdf_url": p["pdf_url"],
                    "priority": 1,
                }
                for p in retry_found
            ]

    # Filter to only protocols with PDF URLs
    with_pdf = [p for p in protocols if p.get("pdf_url")]
    if not with_pdf:
        logger.info("No protocols with PDF URLs to process.")
        summary["finished"] = datetime.now().isoformat()
        return summary

    # Sort by priority (1 = highest)
    with_pdf.sort(key=lambda p: p.get("priority", 99))

    # Limit processing per run
    to_process = with_pdf[:max_process]
    logger.info(f"Will process {len(to_process)} of {len(with_pdf)} protocols with PDFs")

    # Step 2 + 3: Download and Process
    process_state = load_process_state()
    processed_results = []

    for p in to_process:
        if is_processed(p["pdf_url"], process_state):
            logger.info(f"Already processed: {p['organ_display']} {p['meeting_date']}")
            continue

        logger.info("=" * 60)
        logger.info(f"STEP 2+3: {p['organ_display']} {p['meeting_date']}")
        logger.info("=" * 60)

        # Download
        pdf_path = download_pdf(p["pdf_url"], p["organ_display"], p["meeting_date"])
        if not pdf_path:
            summary["errors"] += 1
            continue
        summary["downloaded"] += 1

        # Process
        result = process_protocol(
            pdf_path, p["organ_display"], p["meeting_date"], dry_run=dry_run
        )
        if result:
            mark_processed(p["pdf_url"], process_state, result)
            if result.get("status") == "ok":
                summary["processed"] += 1
                summary["decisions_total"] += result.get("decisions_count", 0)
                processed_results.append(result)
            elif result.get("status") == "error":
                summary["errors"] += 1

        # Rate limit between AI calls
        time.sleep(2)

    save_process_state(process_state)

    # Step 4: Build site
    if not skip_build and processed_results and not dry_run:
        logger.info("=" * 60)
        logger.info("STEP 4: Building site...")
        logger.info("=" * 60)
        build_site()

    # Step 5: Git commit
    if not skip_git and processed_results and not dry_run:
        if os.environ.get("GITHUB_ACTIONS"):
            logger.info("=" * 60)
            logger.info("STEP 5: Git commit + push...")
            logger.info("=" * 60)
            decisions = summary["decisions_total"]
            msg = (
                f"🏛️ {summary['processed']} new protocol(s), "
                f"{decisions} decision(s) — "
                f"{datetime.now().strftime('%Y-%m-%d')}"
            )
            git_commit_and_push(msg)

    summary["finished"] = datetime.now().isoformat()

    # Print summary
    print("\n" + "=" * 60)
    print("📊 PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  🔍 Discovered: {summary['discovered']} new protocol(s)")
    print(f"  📥 Downloaded: {summary['downloaded']} PDF(s)")
    print(f"  🤖 Processed:  {summary['processed']} protocol(s)")
    print(f"  📋 Decisions:  {summary['decisions_total']} total")
    print(f"  ❌ Errors:     {summary['errors']}")
    print("=" * 60)

    return summary


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kommun Monitor — Pipeline")
    parser.add_argument("--discover-only", action="store_true",
                        help="Only discover, don't process")
    parser.add_argument("--process", metavar="URL",
                        help="Process a specific PDF URL")
    parser.add_argument("--process-known", action="store_true",
                        help="Process all protocols from data/known_protocols.json")
    parser.add_argument("--retry", action="store_true",
                        help="Retry protocols missing PDFs")
    parser.add_argument("--backfill", type=int, metavar="YEAR",
                        help="Backfill historical protocols for a year")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't actually process, just show what would happen")
    parser.add_argument("--skip-build", action="store_true",
                        help="Skip site build step")
    parser.add_argument("--skip-git", action="store_true",
                        help="Skip git commit/push step")
    parser.add_argument("--max", type=int, default=5,
                        help="Max protocols to process per run (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        ],
    )

    if args.discover_only:
        from discovery import main as discovery_main
        discovery_main()
        return

    if args.retry:
        print("🔄 Retrying pending protocols...")
        from discovery import retry_pending
        found = retry_pending()
        for p in found:
            print(f"  ✅ {p['organ']} {p['meeting_date']} → {p['pdf_url']}")
        if not found:
            print("  No new PDFs found.")
        return

    if args.backfill:
        print(f"📚 Backfilling {args.backfill}...")
        results = backfill_from_google(year=args.backfill, max_searches=10)
        for r in results:
            print(f"  📄 {r['organ_display']} {r['meeting_date']}")
        return

    if args.process:
        # Process a single URL — extract organ + date from filename
        organ, meeting_date = parse_organ_date_from_url(args.process)
        process_state = load_process_state()
        pdf_path = download_pdf(args.process, organ, meeting_date)
        if pdf_path:
            result = process_protocol(pdf_path, organ, meeting_date, dry_run=args.dry_run)
            if result:
                mark_processed(args.process, process_state, result)
                save_process_state(process_state)
        return

    if args.process_known:
        # Process all protocols from known_protocols.json
        known_file = DATA_DIR / "known_protocols.json"
        if not known_file.exists():
            print("❌ data/known_protocols.json not found")
            return
        known = json.loads(known_file.read_text("utf-8"))
        process_state = load_process_state()
        count = 0
        limit = args.max
        for p in known["protocols"]:
            if count >= limit:
                print(f"\n  ⏸️  Batch limit reached ({limit}). Run again to continue.")
                break
            url = p["pdf_url"]
            if is_processed(url, process_state):
                continue
            print(f"\n  📄 Processing: {p['organ']} {p['date']} ({p.get('pages','?')} pages)...")
            pdf_path = download_pdf(url, p["organ"], p["date"])
            if pdf_path:
                result = process_protocol(pdf_path, p["organ"], p["date"], dry_run=args.dry_run)
                if result:
                    mark_processed(url, process_state, result)
                    save_process_state(process_state)
                    count += 1
            time.sleep(2)
        print(f"\n  ✅ Done: {count} protocols processed")
        return

    # Default: run full pipeline
    run_pipeline(
        dry_run=args.dry_run,
        skip_build=args.skip_build,
        skip_git=args.skip_git,
        max_process=args.max,
    )


if __name__ == "__main__":
    main()
