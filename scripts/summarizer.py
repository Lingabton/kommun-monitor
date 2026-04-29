"""
Kommun Monitor — Core Summarization Engine
Extracts text from protokoll PDFs and generates structured summaries via Claude AI.
"""

import json
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

MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
}

def _get_summary_prompt():
    """Get prompt from prompts.py if available, otherwise use fallback."""
    try:
        from prompts import PROMPTS
        return PROMPTS["summarize"]["prompt"]
    except ImportError:
        return "Extrahera alla beslut fran detta protokoll som JSON."

SUMMARY_PROMPT = _get_summary_prompt()

SOCIAL_PROMPT = """Skriv sociala medie-inlagg, ETT per beslut. Max 250 tecken, svenska,
borja med emoji, avsluta med #OrebroKommun. Sakligt, specifikt, ej clickbait.
Svara BARA med JSON: {"posts": [{"text": "...", "decision_id": "..."}]}

Beslut:
"""


def extract_text_from_pdf(pdf_path: str) -> str:
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n\n".join(parts)


def summarize_protocol(text: str, api_key: str, model: str = "haiku", max_retries: int = 3) -> dict:
    """Summarize protocol with retry logic and JSON validation."""
    import logging
    import time
    import random
    logger = logging.getLogger(__name__)

    client = anthropic.Anthropic(api_key=api_key)
    if len(text) > 100_000:
        text = text[:100_000] + "\n\n[Trunkerad]"

    prompt = f"{SUMMARY_PROMPT}\n\n--- PROTOKOLL ---\n\n{text}\n\n--- SLUT ---"
    last_error = None

    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=MODELS.get(model, MODELS["haiku"]),
                max_tokens=16000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.content[0].text.strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:])
                if raw.rstrip().endswith("```"):
                    raw = raw.rstrip()[:-3]

            result = json.loads(raw)

            # Validate required structure
            if not isinstance(result.get("decisions"), list):
                raise ValueError(f"'decisions' missing or not a list")
            if len(result["decisions"]) == 0:
                raise ValueError("Empty decisions array — Claude may have failed to parse PDF")
            for dec in result["decisions"]:
                if not dec.get("headline"):
                    raise ValueError(f"Decision missing 'headline': {dec.get('id', 'unknown')}")

            # Generate stable IDs and normalize paragraph refs
            mt = result.get("meeting_type", "x")[:2].lower()
            d = result.get("date", "unknown")
            for i, dec in enumerate(result.get("decisions", [])):
                pr = dec.get("paragraph_ref", str(i))
                if "id" not in dec:
                    dec["id"] = f"{d}_{mt}_{pr.replace(', ', '_')}"
                if pr and not pr.startswith("§"):
                    dec["paragraph_ref"] = f"§ {pr}"

            return result

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"Summarize attempt {attempt+1} failed (validation): {e}. Retrying...")
                time.sleep(1)
            else:
                raise ValueError(f"Summarization failed after {max_retries} attempts: {last_error}")

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = min(2 ** attempt + random.random(), 30)
                logger.warning(f"API call failed (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"API call failed after {max_retries} attempts: {last_error}")


def generate_social_posts(decisions: list, api_key: str, model: str = "haiku") -> list:
    client = anthropic.Anthropic(api_key=api_key)
    txt = "\n".join(
        f"- [{d.get('id','')}] {d['headline']}: {d['summary']}"
        for d in decisions
    )
    msg = client.messages.create(
        model=MODELS.get(model, MODELS["haiku"]),
        max_tokens=2000,
        messages=[{"role": "user", "content": f"{SOCIAL_PROMPT}\n{txt}"}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]
    return json.loads(raw).get("posts", [])
