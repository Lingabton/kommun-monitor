"""
Kommun Monitor — Auto-Discovery
================================
Monitors Örebro kommun's digital anslagstavla RSS feed for new protocols,
then discovers the actual PDF URLs via Google search.

Strategy:
    1. Fetch RSS feed from orebro.se/rss/anslag
    2. Filter for protocol announcements (skip detaljplaner, bygglov etc)
    3. Extract organ name + meeting date from each entry
    4. Search Google for the PDF URL on orebro.se/download/
    5. Return list of new protocols not yet in our state file

Usage:
    from discovery import discover_new_protocols
    new = discover_new_protocols()
    for p in new:
        print(p["organ"], p["date"], p["pdf_url"])

Or standalone:
    python discovery.py              # Show new protocols
    python discovery.py --all        # Show all protocols in RSS
    python discovery.py --organs     # List monitored organs
"""

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

RSS_URL = "https://www.orebro.se/rss/anslag"

# All organs we want to monitor. The key is a normalized slug,
# the value contains display name and patterns to match in RSS titles.
MONITORED_ORGANS = {
    "kommunfullmaktige": {
        "display": "Kommunfullmäktige",
        "patterns": ["kommunfullmäktige"],
        "priority": 1,
    },
    "kommunstyrelsen": {
        "display": "Kommunstyrelsen",
        "patterns": ["kommunstyrelsens protokoll"],
        "priority": 1,
    },
    # ── Uncomment below to add more organs later ──────────────
    # "ks-hallbarhetsutskott": {
    #     "display": "KS Hållbarhetsutskott",
    #     "patterns": ["kommunstyrelsens hållbarhetsutskott"],
    #     "priority": 2,
    # },
    # "grundskolenamnden": {
    #     "display": "Grundskolenämnden",
    #     "patterns": ["grundskolenämnden"],
    #     "priority": 2,
    # },
    # "gymnasie-arbetsmarknadsnamnden": {
    #     "display": "Gymnasie- och arbetsmarknadsnämnden",
    #     "patterns": ["gymnasie- och arbetsmarknadsnämnden"],
    #     "priority": 2,
    # },
    # "socialnamnden": {
    #     "display": "Socialnämnden",
    #     "patterns": ["socialnämndens protokoll"],
    #     "priority": 2,
    # },
    # "vard-omsorgsnamnden": {
    #     "display": "Vård- och omsorgsnämnden",
    #     "patterns": ["vård- och omsorgsnämnden"],
    #     "priority": 2,
    # },
    # "bygg-miljonamnden": {
    #     "display": "Bygg- och miljönämnden",
    #     "patterns": ["bygg- och miljönämnden"],
    #     "priority": 2,
    # },
    # "kultur-fritidsnamnden": {
    #     "display": "Kultur- och fritidsnämnden",
    #     "patterns": ["kultur- och fritidsnämnden"],
    #     "priority": 2,
    # },
    # "teknik-servicenamnden": {
    #     "display": "Teknik- och servicenämnden",
    #     "patterns": ["teknik- och servicenämnden"],
    #     "priority": 2,
    # },
    # "funktionsstodsnamnden": {
    #     "display": "Funktionsstödsnämnden",
    #     "patterns": ["funktionsstödsnämnden"],
    #     "priority": 2,
    # },
    # "forskolenamnden": {
    #     "display": "Förskolenämnden",
    #     "patterns": ["förskolenämnden"],
    #     "priority": 2,
    # },
    # "markplanering-exploatering": {
    #     "display": "Markplanerings- och exploateringsnämnden",
    #     "patterns": ["markplanerings- och exploateringsnämnden"],
    #     "priority": 2,
    # },
    # "overformyndarnamnden": {
    #     "display": "Överförmyndarnämnden",
    #     "patterns": ["överförmyndarnämnden"],
    #     "priority": 3,
    # },
    # "valnamnden": {
    #     "display": "Valnämnden",
    #     "patterns": ["valnämnden"],
    #     "priority": 3,
    # },
    # "programnamnden": {
    #     "display": "Programnämnden",
    #     "patterns": ["programnämnden"],
    #     "priority": 2,
    # },
}

# Skip these — individutskott etc. have no public-interest protocols
SKIP_PATTERNS = [
    "individutskott",
    "försörjningsstöd",
]

# Paths
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
STATE_FILE = DATA_DIR / "discovery_state.json"

# Request settings
HEADERS = {
    "User-Agent": "KommunMonitor/2.0 (https://github.com/lingabton/kommun-monitor)"
}
REQUEST_TIMEOUT = 30


# ─────────────────────────────────────────────
# RSS PARSING
# ─────────────────────────────────────────────

ANSLAGSTAVLA_URL = "https://www.orebro.se/kommun--politik/politik--beslut/digital-anslagstavla.html"


def fetch_anslagstavla() -> list[dict]:
    """
    Fetch and parse the anslagstavla HTML page for protocol links.
    Returns more items than RSS (20+ vs 10) so KF/KS don't get pushed out.
    """
    try:
        r = requests.get(ANSLAGSTAVLA_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch anslagstavla: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for a_tag in soup.find_all("a", href=True):
        title = a_tag.get_text().strip()
        href = a_tag["href"]
        if "protokoll" in title.lower() and "/anslag-protokoll/" in href:
            link = href if href.startswith("http") else f"https://www.orebro.se{href}"
            items.append({
                "title": title,
                "link": link,
                "pub_date": "",
            })

    logger.info(f"Anslagstavla: fetched {len(items)} protocol items")
    return items


def fetch_rss() -> list[dict]:
    """
    Fetch from anslagstavla HTML (primary) + RSS feed (fallback).
    Deduplicates by title.
    """
    # Primary: HTML page (has ~20 items vs RSS's 10)
    items = fetch_anslagstavla()

    # Fallback: also check RSS for any items the HTML might miss
    try:
        r = requests.get(RSS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            if title and (link or guid):
                items.append({
                    "title": title,
                    "link": link or guid,
                    "pub_date": pub_date,
                })
    except Exception as e:
        logger.debug(f"RSS fallback failed (non-critical): {e}")

    # Deduplicate by title
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for item in items:
        t = item["title"].lower().strip()
        if t not in seen_titles:
            seen_titles.add(t)
            unique.append(item)

    logger.info(f"Total unique items: {len(unique)} (HTML + RSS)")
    return unique


def is_protocol_entry(title: str) -> bool:
    """Check if an RSS entry is a protocol announcement (not detaljplan, bygglov etc)."""
    title_lower = title.lower()

    # Must contain "protokoll"
    if "protokoll" not in title_lower:
        return False

    # Skip individutskott etc
    for skip in SKIP_PATTERNS:
        if skip in title_lower:
            return False

    return True


def match_organ(title: str) -> Optional[str]:
    """
    Match an RSS title to a monitored organ.
    Returns the organ slug or None.
    """
    title_lower = title.lower()
    for slug, info in MONITORED_ORGANS.items():
        for pattern in info["patterns"]:
            if pattern in title_lower:
                return slug
    return None


def extract_meeting_date(title: str) -> Optional[str]:
    """
    Extract the meeting date from a protocol title.
    Example: "Kommunstyrelsens protokoll 2026-02-10, justerat" → "2026-02-10"
    """
    match = re.search(r"protokoll\s+(\d{4}-\d{2}-\d{2})", title.lower())
    if match:
        return match.group(1)
    return None


def extract_paragraph_info(title: str) -> Optional[str]:
    """
    Extract paragraph info if present.
    Example: "protokoll 2026-03-17,§§ 48-49,66" → "§§ 48-49,66"
    """
    match = re.search(r"(§§?\s*[\d\-,\s§]+)", title)
    if match:
        return match.group(1).strip()
    return None


def parse_rss_protocols(items: list[dict]) -> list[dict]:
    """
    Parse RSS items into structured protocol records.
    Only returns items that are protocols for monitored organs.
    """
    protocols = []
    for item in items:
        if not is_protocol_entry(item["title"]):
            continue

        organ_slug = match_organ(item["title"])
        if not organ_slug:
            logger.debug(f"Unmatched organ in: {item['title']}")
            continue

        meeting_date = extract_meeting_date(item["title"])
        if not meeting_date:
            logger.warning(f"No date found in: {item['title']}")
            continue

        paragraphs = extract_paragraph_info(item["title"])
        organ_info = MONITORED_ORGANS[organ_slug]

        protocols.append({
            "organ_slug": organ_slug,
            "organ_display": organ_info["display"],
            "priority": organ_info["priority"],
            "meeting_date": meeting_date,
            "paragraphs": paragraphs,
            "rss_title": item["title"],
            "anslag_url": item["link"],
            "pub_date": item["pub_date"],
            "pdf_url": None,  # To be filled by PDF discovery
        })

    logger.info(f"RSS: {len(protocols)} protocol announcements for monitored organs")
    return protocols


# ─────────────────────────────────────────────
# PDF DISCOVERY VIA GOOGLE SEARCH
# ─────────────────────────────────────────────

def search_google_for_pdf(organ_display: str, meeting_date: str) -> Optional[str]:
    """
    Search Google for the protocol PDF on orebro.se.
    Returns the PDF URL if found, or None.

    Uses Google's HTML search results (no API key needed).
    Rate-limited to be polite.
    """
    # Build search query
    # PDF filenames look like: "2026-02-10 Kommunstyrelsen.pdf"
    query = f'site:orebro.se/download "{meeting_date}" "{organ_display}" filetype:pdf'

    try:
        r = requests.get(
            "https://www.google.com/search",
            params={"q": query, "num": 5},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Google search failed for {organ_display} {meeting_date}: {e}")
        return None

    # Parse results
    soup = BeautifulSoup(r.text, "html.parser")

    # Look for orebro.se/download links in the results
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Google wraps links in /url?q=... format
        if "/url?q=" in href:
            match = re.search(r"/url\?q=(https?://www\.orebro\.se/download/[^&]+\.pdf)", href)
            if match:
                pdf_url = unquote(match.group(1))
                logger.info(f"Found PDF via Google: {pdf_url}")
                return pdf_url
        elif "orebro.se/download" in href and href.endswith(".pdf"):
            logger.info(f"Found PDF via Google (direct): {href}")
            return href

    logger.warning(f"No PDF found via Google for {organ_display} {meeting_date}")
    return None


def search_orebro_site_for_pdf(organ_display: str, meeting_date: str) -> Optional[str]:
    """
    Alternative: search directly on the organ's page for the PDF link.
    This is a fallback if Google doesn't find it.

    Strategy: fetch the organ's main page, look for download links
    matching the meeting date.
    """
    # Map organ to its page URL
    organ_pages = {
        "Kommunfullmäktige": "https://www.orebro.se/kommun--politik/politik--beslut/kommunfullmaktige.html",
        "Kommunstyrelsen": "https://www.orebro.se/kommun--politik/politik--beslut/kommunstyrelsen.html",
    }

    page_url = organ_pages.get(organ_display)
    if not page_url:
        return None

    try:
        r = requests.get(page_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch organ page {page_url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Look for PDF download links containing the meeting date
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/download/" in href and meeting_date in href and ".pdf" in href.lower():
            full_url = href if href.startswith("http") else f"https://www.orebro.se{href}"
            logger.info(f"Found PDF on organ page: {full_url}")
            return full_url

    return None


def discover_pdf_url(
    organ_display: str,
    meeting_date: str,
    use_google: bool = True,
    delay: float = 2.0,
) -> Optional[str]:
    """
    Try multiple strategies to find the PDF URL for a protocol.

    Order:
    1. Google search (best for indexed PDFs)
    2. Direct organ page scrape (fallback, may not work due to JS)
    3. Known URL pattern guess (last resort, usually fails due to hash)
    """
    pdf_url = None

    # Strategy 1: Google search
    if use_google:
        pdf_url = search_google_for_pdf(organ_display, meeting_date)
        if pdf_url:
            return pdf_url
        time.sleep(delay)  # Rate limit

    # Strategy 2: Organ page scrape
    pdf_url = search_orebro_site_for_pdf(organ_display, meeting_date)
    if pdf_url:
        return pdf_url

    logger.warning(f"Could not find PDF for {organ_display} {meeting_date}")
    return None


# ─────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────

def load_state() -> dict:
    """Load discovery state (which protocols we've seen/processed)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text("utf-8"))
    return {
        "seen": {},       # key: "{organ_slug}_{meeting_date}" → status
        "last_check": None,
        "stats": {
            "total_discovered": 0,
            "total_pdf_found": 0,
            "total_pdf_missing": 0,
        },
    }


def save_state(state: dict):
    """Save discovery state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_check"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")


def protocol_key(organ_slug: str, meeting_date: str, paragraphs: str = None) -> str:
    """Generate a unique key for a protocol."""
    key = f"{organ_slug}_{meeting_date}"
    if paragraphs:
        # Normalize paragraph info for key
        para_clean = re.sub(r"[§\s]", "", paragraphs)
        key += f"_{para_clean}"
    return key


# ─────────────────────────────────────────────
# MAIN DISCOVERY PIPELINE
# ─────────────────────────────────────────────

def discover_new_protocols(
    use_google: bool = True,
    force: bool = False,
    max_google_searches: int = 10,
) -> list[dict]:
    """
    Main entry point: discover new protocols from RSS feed.

    Args:
        use_google: Whether to use Google search for PDF discovery
        force: If True, re-discover even already-seen protocols
        max_google_searches: Limit Google searches per run (rate limiting)

    Returns:
        List of protocol dicts with pdf_url filled in where found.
    """
    state = load_state()

    # Step 1: Fetch RSS
    rss_items = fetch_rss()
    if not rss_items:
        logger.error("No RSS items fetched. Aborting.")
        return []

    # Step 2: Parse into protocol records
    protocols = parse_rss_protocols(rss_items)

    # Step 3: Filter out already-seen protocols
    new_protocols = []
    for p in protocols:
        key = protocol_key(p["organ_slug"], p["meeting_date"], p["paragraphs"])
        if not force and key in state["seen"]:
            logger.debug(f"Already seen: {key}")
            continue
        new_protocols.append(p)

    if not new_protocols:
        logger.info("No new protocols found.")
        save_state(state)
        return []

    logger.info(f"Found {len(new_protocols)} new protocol(s)")

    # Step 4: Discover PDF URLs
    google_searches_done = 0
    for p in new_protocols:
        should_google = use_google and google_searches_done < max_google_searches

        pdf_url = discover_pdf_url(
            p["organ_display"],
            p["meeting_date"],
            use_google=should_google,
        )

        if should_google:
            google_searches_done += 1

        p["pdf_url"] = pdf_url

        # Update state
        key = protocol_key(p["organ_slug"], p["meeting_date"], p["paragraphs"])
        state["seen"][key] = {
            "status": "found" if pdf_url else "no_pdf",
            "pdf_url": pdf_url,
            "organ": p["organ_display"],
            "meeting_date": p["meeting_date"],
            "discovered_at": datetime.now().isoformat(),
            "anslag_url": p["anslag_url"],
        }
        state["stats"]["total_discovered"] += 1
        if pdf_url:
            state["stats"]["total_pdf_found"] += 1
        else:
            state["stats"]["total_pdf_missing"] += 1

    save_state(state)

    found = [p for p in new_protocols if p["pdf_url"]]
    missing = [p for p in new_protocols if not p["pdf_url"]]

    logger.info(f"Discovery complete: {len(found)} with PDF, {len(missing)} without PDF")
    if missing:
        for p in missing:
            logger.warning(f"  Missing PDF: {p['organ_display']} {p['meeting_date']}")

    return new_protocols


def get_pending_protocols() -> list[dict]:
    """
    Get protocols that were discovered but have no PDF URL yet.
    Useful for retry logic.
    """
    state = load_state()
    pending = []
    for key, info in state["seen"].items():
        if info["status"] == "no_pdf":
            pending.append(info)
    return pending


def retry_pending(max_retries: int = 5) -> list[dict]:
    """
    Retry finding PDFs for protocols that were previously discovered
    but had no PDF URL. PDFs sometimes appear days after the anslag.
    """
    state = load_state()
    found = []
    retries = 0

    for key, info in state["seen"].items():
        if info["status"] != "no_pdf" or retries >= max_retries:
            continue

        logger.info(f"Retrying: {info['organ']} {info['meeting_date']}")
        pdf_url = discover_pdf_url(info["organ"], info["meeting_date"])

        if pdf_url:
            info["status"] = "found"
            info["pdf_url"] = pdf_url
            info["found_at"] = datetime.now().isoformat()
            state["stats"]["total_pdf_found"] += 1
            state["stats"]["total_pdf_missing"] -= 1
            found.append(info)

        retries += 1
        time.sleep(2)  # Rate limit

    save_state(state)
    return found


# ─────────────────────────────────────────────
# HISTORICAL BACKFILL
# ─────────────────────────────────────────────

def backfill_from_google(
    organs: list[str] = None,
    year: int = 2025,
    max_searches: int = 20,
) -> list[dict]:
    """
    Search Google for historical protocols not in RSS feed.
    Useful for initial population of the database.

    Args:
        organs: List of organ display names to search for.
                Defaults to KF + KS.
        year: Year to search for.
        max_searches: Maximum Google searches to perform.
    """
    if organs is None:
        organs = ["Kommunfullmäktige", "Kommunstyrelsen"]

    state = load_state()
    results = []
    searches = 0

    for organ in organs:
        if searches >= max_searches:
            break

        query = f'site:orebro.se/download "{organ}" "{year}" protokoll filetype:pdf'
        logger.info(f"Backfill search: {query}")

        try:
            r = requests.get(
                "https://www.google.com/search",
                params={"q": query, "num": 20},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                },
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            searches += 1
        except requests.RequestException as e:
            logger.error(f"Google backfill search failed: {e}")
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            match = re.search(
                r"/url\?q=(https?://www\.orebro\.se/download/[^&]+\.pdf)", href
            )
            if match:
                pdf_url = unquote(match.group(1))
                # Extract date from filename
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", pdf_url)
                if date_match:
                    meeting_date = date_match.group(1)
                    results.append({
                        "organ_display": organ,
                        "meeting_date": meeting_date,
                        "pdf_url": pdf_url,
                        "source": "backfill",
                    })

        time.sleep(3)  # Rate limit

    # Deduplicate
    seen_urls = set()
    unique = []
    for r in results:
        if r["pdf_url"] not in seen_urls:
            seen_urls.add(r["pdf_url"])
            unique.append(r)

    logger.info(f"Backfill found {len(unique)} unique protocol PDFs")
    return unique


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Kommun Monitor — Protocol Discovery")
    parser.add_argument("--all", action="store_true", help="Show all RSS protocols (including seen)")
    parser.add_argument("--organs", action="store_true", help="List monitored organs")
    parser.add_argument("--retry", action="store_true", help="Retry pending protocols")
    parser.add_argument("--backfill", type=int, metavar="YEAR", help="Backfill from Google for given year")
    parser.add_argument("--no-google", action="store_true", help="Skip Google search")
    parser.add_argument("--status", action="store_true", help="Show discovery status")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.organs:
        print("\n📋 Monitored organs:\n")
        for slug, info in sorted(MONITORED_ORGANS.items(), key=lambda x: x[1]["priority"]):
            priority_emoji = {1: "🔴", 2: "🟡", 3: "⚪"}[info["priority"]]
            print(f"  {priority_emoji} {info['display']} (priority {info['priority']})")
        print(f"\n  Skip patterns: {', '.join(SKIP_PATTERNS)}")
        return

    if args.status:
        state = load_state()
        print("\n📊 Discovery status:\n")
        print(f"  Last check: {state.get('last_check', 'Never')}")
        print(f"  Total discovered: {state['stats']['total_discovered']}")
        print(f"  PDFs found: {state['stats']['total_pdf_found']}")
        print(f"  PDFs missing: {state['stats']['total_pdf_missing']}")
        pending = get_pending_protocols()
        if pending:
            print(f"\n  ⏳ Pending (no PDF yet):")
            for p in pending:
                print(f"     {p['organ']} {p['meeting_date']}")
        return

    if args.retry:
        print("🔄 Retrying pending protocols...")
        found = retry_pending()
        if found:
            for p in found:
                print(f"  ✅ Found: {p['organ']} {p['meeting_date']} → {p['pdf_url']}")
        else:
            print("  No new PDFs found.")
        return

    if args.backfill:
        print(f"📚 Backfilling from Google for {args.backfill}...")
        results = backfill_from_google(year=args.backfill)
        for r in results:
            print(f"  📄 {r['organ_display']} {r['meeting_date']}")
            print(f"     {r['pdf_url']}")
        return

    # Default: discover new protocols
    print("🔍 Checking for new protocols...\n")
    protocols = discover_new_protocols(
        use_google=not args.no_google,
        force=args.all,
    )

    if not protocols:
        print("  No new protocols found.")
        return

    for p in protocols:
        status = "✅" if p["pdf_url"] else "❌"
        print(f"  {status} {p['organ_display']} — {p['meeting_date']}")
        if p["pdf_url"]:
            print(f"     PDF: {p['pdf_url']}")
        if p["paragraphs"]:
            print(f"     {p['paragraphs']}")

    found = [p for p in protocols if p["pdf_url"]]
    missing = [p for p in protocols if not p["pdf_url"]]
    print(f"\n  Summary: {len(found)} with PDF, {len(missing)} pending")


if __name__ == "__main__":
    main()
