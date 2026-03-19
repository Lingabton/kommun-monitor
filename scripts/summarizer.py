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

SUMMARY_PROMPT = """Du ar en erfaren lokal journalist som bevakar Orebro kommun.

=== VAD SKA TAS MED ===
Ta med ALLA beslut som uppfyller MINST ETT av dessa:
1. Paverkar invanare: byggen, infrastruktur, skolor, budget, miljo, trygghet
2. Paverkar foretagare: regler, uteserveringar, parkering, tillstand, avgifter
3. Politiskt intressant: omstridda beslut, reservationer, avslag
4. Handlar om pengar: investeringar, forsaljningar, avskrivningar, anslag
5. Andrar regler/styrdokument: policyer, riktlinjer, strategier
6. Ror motioner/ledamotsinitiativ: oavsett utfall

=== HOPPA OVER ===
Bara rena formaliteter: val av justerare, godkannande av dagordning,
"rapporten laggs till handlingarna" (undantag: intressanta siffror).

=== JSON-FORMAT ===
Svara BARA med JSON:
{
  "meeting_type": "Kommunstyrelsen",
  "date": "2024-04-09",
  "summary_headline": "Max 12 ord",
  "decisions": [
    {
      "headline": "Max 15 ord",
      "summary": "1-2 meningar",
      "detail": "3-5 stycken med \\n\\n. Bakgrund, konkret beslut, belopp/tider/platser, partier for/mot, konsekvenser.",
      "category": "bygg|infrastruktur|skola|budget|miljo|trygghet|kultur|politik|regler|ovrigt",
      "contested": true,
      "location": "Plats eller null",
      "paragraph_ref": "76",
      "quote": "Ordagrant citat, max 2 meningar",
      "quote_page": "s. 12",
      "voting": {
        "for": ["S","M","C"],
        "against": ["OrP"],
        "abstained": ["V"],
        "result": "Bifall/Avslaget/Enhälligt/Aterremiss"
      },
      "tags": ["nyckelord1","platsnamn"]
    }
  ],
  "motions_of_interest": [
    {"title": "Beskrivning", "party": "X", "status": "Bereds/Avslagen/Remitterad"}
  ],
  "skipped_items_count": 5
}

=== REGLER ===
KATEGORI "regler": For styrdokument, policyer, riktlinjer, tillstandskrav.
VOTING: "deltar inte" = abstained. "reserverar sig" = against. Partier: S,M,C,L,KD,V,SD,OrP,MP.
QUOTE: Kopiera ordagrant fran protokollet, max 2 meningar.
TAGS: 3-6 nyckelord inkl platsnamn.
paragraph_ref: Bara siffran, t.ex. "76".

Svara BARA med JSON."""

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
        max_tokens=8000,
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
