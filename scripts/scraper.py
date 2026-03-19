"""
Kommun Monitor — Scraper
Monitors orebro.se for new protokoll PDFs, downloads and processes them.
"""

import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

from summarizer import extract_text_from_pdf, summarize_protocol, generate_social_posts

BASE_URL = "https://www.orebro.se"
SCRAPE_PAGES = [
    {"name": "Kommunfullmäktige", "url": f"{BASE_URL}/kommun--politik/politik--beslut/kommunfullmaktige.html"},
    {"name": "Kommunstyrelsen", "url": f"{BASE_URL}/kommun--politik/politik--beslut/kommunstyrelsen.html"},
]

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = ROOT / "output"
SITE_DIR = ROOT / "site"
STATE_FILE = DATA_DIR / "state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(ROOT / "logs" / "scraper.log", encoding="utf-8")])


def setup():
    for d in [DATA_DIR, PDF_DIR, OUTPUT_DIR, SITE_DIR, ROOT / "logs"]:
        d.mkdir(parents=True, exist_ok=True)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text("utf-8"))
    return {"processed": {}, "last_check": None}


def save_state(state):
    state["last_check"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")


def fetch_page(url):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "KommunMonitor/1.0"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        logging.error(f"Fetch failed {url}: {e}")
        return None


def find_protocol_pdfs(html, page_url, source):
    soup = BeautifulSoup(html, "html.parser")
    results, seen = [], set()
    for a in soup.find_all("a", href=True):
        href, text = a["href"], a.get_text(strip=True)
        if "/download/" not in href or not href.lower().endswith(".pdf"):
            continue
        if any(s in text.lower() for s in ["ärendelista", "arbetsordning", "reglemente", "offentlighet"]):
            continue
        url = urljoin(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", unquote(url))
        date = dm.group(1) if dm else None
        body = source
        for b in ["Kommunfullmäktige", "Kommunstyrelsen"]:
            if b.lower() in unquote(url).lower():
                body = b
                break
        pid = f"{date or 'unknown'}_{hashlib.md5(url.encode()).hexdigest()[:10]}"
        results.append({"id": pid, "url": url, "text": text, "source": source, "body": body, "date": date})
    return results


def discover_all():
    all_p = []
    for page in SCRAPE_PAGES:
        logging.info(f"Scanning {page['name']}...")
        html = fetch_page(page["url"])
        if html:
            found = find_protocol_pdfs(html, page["url"], page["name"])
            logging.info(f"  {len(found)} PDFs found")
            all_p.extend(found)
    seen = set()
    return [p for p in all_p if not (p["url"] in seen or seen.add(p["url"]))]


def download_pdf(url, pid):
    path = PDF_DIR / f"{pid}.pdf"
    if path.exists():
        return path
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "KommunMonitor/1.0"})
        r.raise_for_status()
        path.write_bytes(r.content)
        logging.info(f"  Downloaded {path.name} ({len(r.content)//1024}KB)")
        return path
    except Exception as e:
        logging.error(f"  Download failed: {e}")
        return None


def process_one(protocol, api_key, model="haiku", quality_check=False):
    pid = protocol["id"]
    logging.info(f"Processing {pid}...")

    pdf = download_pdf(protocol["url"], pid)
    if not pdf:
        return None

    text = extract_text_from_pdf(str(pdf))
    if len(text) < 200:
        logging.warning(f"  Too short ({len(text)} chars)")
        return None

    logging.info(f"  {len(text)} chars extracted, running pipeline...")
    try:
        from prompts import run_pipeline
        results = run_pipeline(text, api_key, quality_check=quality_check)
        summary = results["summary"]
    except Exception as e:
        logging.error(f"  Pipeline failed: {e}")
        # Fallback to basic summarization
        try:
            summary = summarize_protocol(text, api_key, model)
            results = {"summary": summary, "tokens": {"input": 0, "output": 0}, "cost_usd": 0}
        except Exception as e2:
            logging.error(f"  Fallback also failed: {e2}")
            return None

    # Save per-protocol output
    out = OUTPUT_DIR / pid
    out.mkdir(exist_ok=True)
    website_data = {
        "id": f"{summary['date']}_{summary['meeting_type'][:2].lower()}",
        "meeting_type": summary["meeting_type"],
        "date": summary["date"],
        "source_url": protocol["url"],
        "summary_headline": summary["summary_headline"],
        "decisions": summary["decisions"],
        "motions_of_interest": summary.get("motions_of_interest", []),
    }
    (out / "website_data.json").write_text(json.dumps(website_data, ensure_ascii=False, indent=2), "utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")

    # Save social posts (from pipeline or generate separately)
    if "social_posts" in results:
        (out / "social_posts.json").write_text(json.dumps(results["social_posts"], ensure_ascii=False, indent=2), "utf-8")
    else:
        try:
            posts = generate_social_posts(summary["decisions"], api_key, model)
            (out / "social_posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), "utf-8")
        except Exception as e:
            logging.warning(f"  Social posts failed: {e}")

    # Save newsletter subjects
    if "newsletter_subjects" in results:
        (out / "newsletter_subjects.json").write_text(json.dumps(results["newsletter_subjects"], ensure_ascii=False, indent=2), "utf-8")

    # Save quality check
    if "quality_check" in results:
        (out / "quality_check.json").write_text(json.dumps(results["quality_check"], ensure_ascii=False, indent=2), "utf-8")

    # Save cost data
    cost_data = {"tokens": results.get("tokens", {}), "cost_usd": results.get("cost_usd", 0)}
    (out / "cost.json").write_text(json.dumps(cost_data, ensure_ascii=False, indent=2), "utf-8")

    logging.info(f"  ✅ {len(summary.get('decisions',[]))} decisions, ${results.get('cost_usd',0):.4f}")
    return summary


def build_site_data(api_key=None):
    """Combine all protocol outputs into a single site data file. Optionally run connection detection."""
    all_meetings = []
    total_cost = 0
    for d in sorted(OUTPUT_DIR.iterdir()):
        wf = d / "website_data.json"
        if wf.exists():
            all_meetings.append(json.loads(wf.read_text("utf-8")))
        cf = d / "cost.json"
        if cf.exists():
            total_cost += json.loads(cf.read_text("utf-8")).get("cost_usd", 0)

    all_meetings.sort(key=lambda m: m["date"], reverse=True)

    # Run connection detection if we have enough decisions and an API key
    connections = []
    if api_key and len(all_meetings) >= 2:
        all_decisions = []
        for m in all_meetings:
            for dec in m.get("decisions", []):
                all_decisions.append((dec, m))
        if len(all_decisions) >= 3:
            try:
                from prompts import detect_all_connections
                logging.info("Detecting cross-decision connections...")
                connections = detect_all_connections(all_decisions, api_key)
                logging.info(f"  Found {len(connections)} connections")
            except Exception as e:
                logging.warning(f"  Connection detection failed: {e}")

    site_data = {
        "generated_at": datetime.now().isoformat(),
        "total_meetings": len(all_meetings),
        "total_decisions": sum(len(m["decisions"]) for m in all_meetings),
        "total_cost_usd": round(total_cost, 4),
        "connections": connections,
        "meetings": all_meetings,
    }
    out_path = SITE_DIR / "data.json"
    out_path.write_text(json.dumps(site_data, ensure_ascii=False, indent=2), "utf-8")
    logging.info(f"Site data: {len(all_meetings)} meetings, {site_data['total_decisions']} decisions, ${total_cost:.4f} total cost → {out_path}")
    return site_data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kommun Monitor Scraper")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max", type=int, default=5)
    parser.add_argument("--model", default="haiku", choices=["haiku", "sonnet"])
    parser.add_argument("--quality-check", action="store_true", help="Run Sonnet quality check (costs more)")
    parser.add_argument("--build-site", action="store_true", help="Only rebuild site data from existing outputs")
    args = parser.parse_args()

    setup()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if args.build_site:
        build_site_data(api_key if api_key else None)
        return

    protocols = discover_all()
    if not protocols:
        logging.warning("No protocols found")
        return

    if args.list:
        for p in sorted(protocols, key=lambda x: x.get("date") or "", reverse=True):
            print(f"  {p.get('date','?'):12s} {p['body']:25s} {p['text'][:50]}")
        return

    state = load_state()
    new = protocols if args.force else [p for p in protocols if p["id"] not in state["processed"]]
    new.sort(key=lambda x: x.get("date") or "", reverse=True)

    if args.dry_run:
        print(f"\nWould process {min(len(new), args.max)} of {len(new)} new protocols")
        for p in new[:args.max]:
            print(f"  {p.get('date','?')} {p['body']}")
        return

    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY")

    count = 0
    for p in new[:args.max]:
        s = process_one(p, api_key, args.model, quality_check=args.quality_check)
        if s:
            state["processed"][p["id"]] = {
                "at": datetime.now().isoformat(), "date": p.get("date"),
                "body": p["body"], "decisions": len(s.get("decisions", [])),
            }
            count += 1
            save_state(state)
        time.sleep(2)

    logging.info(f"Done: {count} processed")

    # Rebuild site data with connection detection
    build_site_data(api_key)


if __name__ == "__main__":
    main()
