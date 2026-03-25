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


def summarize_protocol(text: str, api_key: str, model: str = "haiku") -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    if len(text) > 100_000:
        text = text[:100_000] + "\n\n[Trunkerad]"

    msg = client.messages.create(
        model=MODELS.get(model, MODELS["haiku"]),
        max_tokens=16000,
        messages=[{"role": "user", "content": f"{SUMMARY_PROMPT}\n\n--- PROTOKOLL ---\n\n{text}\n\n--- SLUT ---"}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]

    result = json.loads(raw)

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
