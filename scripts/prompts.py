"""
Kommun Monitor — Prompt Library
================================
Specialized prompts for each stage of the pipeline.
Each prompt is optimized for its task and target model.

Usage:
    from prompts import PROMPTS
    prompt = PROMPTS["summarize"]["prompt"]
    model = PROMPTS["summarize"]["model"]

Strategy:
    - Heavy lifting (summarize) → Haiku (cheap, good enough)
    - Precision tasks (voting) → Haiku with strict format
    - Creative tasks (SEO, social) → Haiku with examples
    - Connection detection → Haiku with context window
    - Quality check → Sonnet (only when reviewing)
"""

PROMPTS = {

    # ═══════════════════════════════════════════
    # 1. MAIN SUMMARIZATION
    # Model: Haiku (default) or Sonnet (premium)
    # Cost: ~$0.005/protocol with Haiku
    # ═══════════════════════════════════════════
    "summarize": {
        "model": "haiku",
        "max_tokens": 8000,
        "description": "Extract and summarize all interesting decisions from a protocol",
        "prompt": """Du ar en erfaren lokal journalist som bevakar Orebro kommun.
Sammanfatta protokollet for Orebrobor — invanare, foretagare, journalister och politiker.

=== TA MED beslut som: ===
1. Paverkar invanare: byggen, infrastruktur, skolor, budget, miljo, trygghet
2. Paverkar foretagare: regler, uteserveringar, parkering, tillstand, avgifter, taxor
3. Ar politiskt intressant: omstridda, reservationer, voteringer, avslag
4. Handlar om pengar: investeringar >1 MSEK, forsaljningar, avskrivningar
5. Andrar regler: policyer, riktlinjer, strategier, styrdokument, delegationsordningar
6. Ror motioner/ledamotsinitiativ, oavsett utfall
7. Handlar om personal/organisation: omorganisationer, chefsrekryteringar

=== HOPPA OVER: ===
- Val av justerare, godkannande av dagordning
- "Rapporten laggs till handlingarna" UTAN intressant innehall
- Rutindelegationsbeslut utan nyhetsvinkel

=== JSON-FORMAT (svara BARA med detta): ===
{
  "meeting_type": "Kommunstyrelsen",
  "date": "2024-04-09",
  "summary_headline": "Max 12 ord, viktigaste beslutet forst",
  "decisions": [
    {
      "headline": "Max 15 ord, specifikt och informativt",
      "summary": "1-2 meningar. Vad beslutades? Varfor spelar det roll?",
      "detail": "3-5 stycken (\\n\\n). Inkludera: bakgrund, konkret beslut, belopp/tider/platser, partier for/mot, konsekvenser for invanare/foretagare.",
      "category": "bygg|infrastruktur|skola|budget|miljo|trygghet|kultur|politik|regler|ovrigt",
      "contested": true,
      "location": "Plats i Orebro eller null",
      "paragraph_ref": "76",
      "quote": "Ordagrant citat, max 2 meningar, som fangar beslutet",
      "quote_page": "s. 12",
      "voting": {
        "for": ["S","M","C"],
        "against": ["OrP"],
        "abstained": ["V"],
        "result": "Bifall/Avslaget/Enhalligt/Aterremiss/Bordlagt"
      },
      "tags": ["nyckelord1","platsnamn","amnesord"]
    }
  ],
  "motions_of_interest": [
    {"title": "Beskrivning", "party": "X", "status": "Bereds/Avslagen/Remitterad/Bordlagd/Tillgodosedd"}
  ],
  "skipped_items_count": 5
}

=== REGLER ===
paragraph_ref: BARA siffran (t.ex. "76").
VOTING: "deltar inte" = abstained. "reserverar sig" = against. "yrkar avslag" = against.
Om votering: ange resultatet som "Avslags 39-22 (votering)".
QUOTE: Kopiera ORDAGRANT. Valj den mening som bast forklarar beslutet.
TAGS: 3-6 st. Inkludera platsnamn, amnen, nyckelbegrepp. Anvands for att koppla beslut over tid.
KATEGORI "regler": Styrdokument, policyer, taxor, avgifter, delegationsordningar, tillstandskrav.
DETAIL: Skriv sa en lasare utan forkunskap forstar kontexten.

Svara BARA med JSON."""
    },

    # ═══════════════════════════════════════════
    # 2. VOTING DATA EXTRACTION
    # Model: Haiku (strict format, cheap)
    # Use case: Re-extract voting when main summary missed details
    # Cost: ~$0.001/protocol
    # ═══════════════════════════════════════════
    "extract_voting": {
        "model": "haiku",
        "max_tokens": 4000,
        "description": "Extract only voting/party data from a protocol paragraph",
        "prompt": """Extrahera rostningsdata fran foljande protokolltext.
For VARJE paragraf/beslut, identifiera:
- Vilka partier som rostade FOR (inklusive de som yrkade bifall)
- Vilka partier som rostade MOT (inklusive de som reserverade sig)
- Vilka partier som AVSTOD (inklusive "deltar inte i beslutet")
- Resultatet (Bifall/Avslaget/Enhalligt/Aterremiss/Bordlagt)
- Om votering skedde, ange antal ja/nej-roster

Partiforkortningar: S, M, C, L, KD, V, SD, OrP, MP

VIKTIGT:
- "reserverar sig" = MOT
- "deltar inte i beslutet" = AVSTOD
- Om bara majoriteten namns som bifall, anta att S+M+C ar FOR
- Om "enhalligt" eller inga reservationer = alla partier FOR

Svara BARA med JSON:
{
  "paragraphs": [
    {
      "ref": "76",
      "title": "Kort beskrivning",
      "for": ["S","M","C"],
      "against": ["OrP"],
      "abstained": ["V"],
      "result": "Bifall",
      "vote_count": null,
      "reservations": ["OrP reserverade sig till forman for eget yrkande"]
    }
  ]
}"""
    },

    # ═══════════════════════════════════════════
    # 3. SEO TITLE & META GENERATION
    # Model: Haiku
    # Use case: Generate Google-optimized titles and descriptions
    # Cost: ~$0.0005/decision
    # ═══════════════════════════════════════════
    "generate_seo": {
        "model": "haiku",
        "max_tokens": 3000,
        "description": "Generate SEO-optimized titles and meta descriptions per decision",
        "prompt": """Generera SEO-optimerade titlar och meta-beskrivningar for kommunala beslut.
Malgrupp: Orebrobor som googlar efter information om kommunens beslut.

For varje beslut, skapa:
1. seo_title: Max 60 tecken. Inkludera "Orebro" + nyckelord folk soker pa.
   Bra: "Nya cykelvägar i Sörbyängen — Örebro kommun beslutar"
   Daligt: "Beslut om cykelstrategi antagen av KF"

2. seo_description: Max 155 tecken. Sammanfatta beslutet + varfor det spelar roll.
   Bra: "Kommunfullmäktige antog ny cykelstrategi. Nya cykelvägar i Sörbyängen, Adolfsberg och Brickebacken. Målet: dubbla cykelresorna till 2030."
   Daligt: "Sammanfattning av kommunfullmäktiges beslut om cykelstrategi."

3. search_keywords: 5-10 ord/fraser folk faktiskt soker pa.
   Bra: ["cykelväg sörbyängen", "örebro cykel", "nya cykelvägar örebro"]
   Daligt: ["kommunfullmäktige beslut", "protokoll"]

4. social_title: Max 80 tecken. Engagerande for delning pa sociala medier.
   Bra: "Örebro satsar på cykel — nya vägar i tre stadsdelar"
   Daligt: "Ny cykelstrategi antagen"

5. social_description: Max 200 tecken. For Open Graph / Twitter cards.

Svara BARA med JSON:
{
  "decisions": [
    {
      "id": "decision_id",
      "seo_title": "...",
      "seo_description": "...",
      "search_keywords": ["...", "..."],
      "social_title": "...",
      "social_description": "..."
    }
  ]
}

Beslut att generera SEO for:
"""
    },

    # ═══════════════════════════════════════════
    # 4. CROSS-DECISION CONNECTION DETECTION
    # Model: Haiku
    # Use case: Find relationships between decisions across meetings
    # Cost: ~$0.002/batch
    # ═══════════════════════════════════════════
    "detect_connections": {
        "model": "haiku",
        "max_tokens": 4000,
        "description": "Identify connections between decisions across different meetings",
        "prompt": """Du far en lista med beslut fran olika sammantraden i Orebro kommun.
Din uppgift ar att identifiera KOPPLINGAR mellan beslut — fragor som foljs upp,
fortsatter, eller haenger ihop over tid.

Typer av kopplingar:
1. UPPFOLJNING: Ett beslut ar en direkt uppfoljning av ett tidigare
   Ex: "Kop av fastighet" -> "Forsaljning av samma fastighet"
2. RELATERAT_AMNE: Beslut handlar om samma amne men ar inte direkt kopplade
   Ex: "Motion om flygplats" -> "Budget for flygplatsbolag"
3. MOTREAKTION: Ett beslut ar en reaktion pa ett tidigare
   Ex: "Stangning av skola" -> "Motion om att utreda stangningen"
4. ATERKOMMER: Samma fraga som bordlagts och kommer tillbaka
   Ex: "Motion bordlagd i maj" -> "Samma motion behandlad i augusti"

Svara BARA med JSON:
{
  "connections": [
    {
      "from_id": "2024-04-09_ks_76",
      "to_id": "2025-09-24_kf_266",
      "type": "UPPFOLJNING",
      "description": "Eyrafaltet-fastighet som koptes 2024 saljs vidare 2025",
      "shared_tags": ["eyrafaltet", "orebroporten"]
    }
  ]
}

Beslut att analysera:
"""
    },

    # ═══════════════════════════════════════════
    # 5. SOCIAL MEDIA POSTS
    # Model: Haiku
    # Cost: ~$0.001/batch
    # ═══════════════════════════════════════════
    "social_posts": {
        "model": "haiku",
        "max_tokens": 2000,
        "description": "Generate engaging social media posts per decision",
        "prompt": """Skriv sociala medie-inlagg for kommunala beslut. ETT per beslut.

REGLER:
- Svenska, max 250 tecken
- Borja med relevant emoji
- Informativt, INTE clickbait
- Specifika detaljer: plats, belopp, partier
- Avsluta med #OrebroKommun
- Om omstritt: namn det kort
- Om votering: namn resultatet
- Variera tonen — inte alla inlagg ska lata likadana

BRA EXEMPEL:
"🏗️ Örebro köper mark vid Eyrafältet för 154 MSEK — vill styra idrottsområdets framtid. ÖrP röstade emot. #ÖrebroKommun"
"🗳️ Votering 39-22: Cirkulationsbibliotek för skolor avslogs. L, SD, KD, MP och ÖrP röstade för. #ÖrebroKommun"
"⚠️ 202 socialtjänstbeslut väntar på att verkställas. V ville tvinga fram en lösning — röstades ned. #ÖrebroKommun"

DALIGA EXEMPEL:
"Kommunen fattade ett viktigt beslut idag! Läs mer... #ÖrebroKommun" (clickbait, inga detaljer)
"📋 Kommunstyrelsen sammanträdde och behandlade flera ärenden. #ÖrebroKommun" (intetsägande)

Svara BARA med JSON:
{"posts": [{"text": "...", "decision_id": "...", "platform": "twitter"}]}

Beslut:
"""
    },

    # ═══════════════════════════════════════════
    # 6. NEWSLETTER SUBJECT LINES
    # Model: Haiku
    # Cost: ~$0.0003/batch
    # ═══════════════════════════════════════════
    "newsletter_subject": {
        "model": "haiku",
        "max_tokens": 1000,
        "description": "Generate compelling newsletter subject lines",
        "prompt": """Skriv 5 forslag pa amnesrader for ett nyhetsbrev om kommunala beslut.
Nyhetsbrevet sammanfattar de senaste besluten fran Orebro kommun.

REGLER:
- Max 60 tecken (viktigt for mobil!)
- Borja med emoji
- Namna det mest intressanta beslutet
- Variera mellan: fraga, pastaende, siffra, platsnamn
- Ska fa folk att oppna mejlet, inte bara scrolla forbi

BRA EXEMPEL:
"🏗️ 154 miljoner till Eyrafältet — vad händer nu?"
"⚠️ 202 beslut väntar. Vad gör kommunen?"
"🗳️ Votering i fullmäktige — 39 mot 22"
"📜 Nya regler för uteserveringar i Örebro"

DALIGA:
"Sammanfattning av kommunens beslut" (trakig)
"Kommun Monitor nyhetsbrev mars 2025" (ingen anledning att oppna)

Svara BARA med JSON:
{"subjects": ["forslag1", "forslag2", "forslag3", "forslag4", "forslag5"]}

De viktigaste besluten denna period:
"""
    },

    # ═══════════════════════════════════════════
    # 7. QUALITY CHECK (for review workflow)
    # Model: Sonnet (higher quality, used sparingly)
    # Use case: Verify that a summary is accurate
    # Cost: ~$0.03/check
    # ═══════════════════════════════════════════
    "quality_check": {
        "model": "sonnet",
        "max_tokens": 3000,
        "description": "Verify summary accuracy against original protocol text",
        "prompt": """Du ar en faktagranskare. Jamfor foljande AI-genererade sammanfattning
med originaltexten fran protokollet.

Kontrollera:
1. FAKTA: Ar belopp, datum, namn och platser korrekta?
2. ROSTNING: Ar partiernas positioner korrekt aterspeglade?
3. NYANS: Ar sammanfattningen rattvissande eller vinklad?
4. UTELAMNANDE: Finns det nagot viktigt som missats?
5. CITAT: Ar citatet ordagrant korrekt?

Svara BARA med JSON:
{
  "overall_score": 8,
  "issues": [
    {
      "decision_id": "...",
      "type": "FACT_ERROR|VOTING_ERROR|BIAS|OMISSION|QUOTE_ERROR",
      "severity": "critical|moderate|minor",
      "description": "Beloppet ar fel: 154 MSEK, inte 145 MSEK",
      "suggestion": "Andras till 154 MSEK"
    }
  ],
  "missing_decisions": [
    "Paragraf 85 om obesvarade motioner namndes inte men innehaller intressant information om..."
  ],
  "verdict": "APPROVE|REVISE|REJECT"
}

=== SAMMANFATTNING ATT GRANSKA ===
{summary_json}

=== ORIGINALPROTOKOLL ===
{protocol_text}
"""
    },
}


# ═══════════════════════════════════════════
# Helper: Build prompt with context
# ═══════════════════════════════════════════

def build_prompt(prompt_key: str, **kwargs) -> dict:
    """
    Build a ready-to-use prompt with context inserted.

    Returns dict with: prompt (str), model (str), max_tokens (int)

    Usage:
        p = build_prompt("summarize", protocol_text="...")
        p = build_prompt("generate_seo", decisions_json="...")
        p = build_prompt("detect_connections", decisions_list="...")
        p = build_prompt("quality_check", summary_json="...", protocol_text="...")
    """
    config = PROMPTS[prompt_key]
    prompt = config["prompt"]

    # Insert kwargs into prompt
    for key, value in kwargs.items():
        placeholder = f"{{{key}}}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(value))

    # For prompts that take appended content
    if "protocol_text" in kwargs and "{protocol_text}" not in config["prompt"]:
        prompt += f"\n\n--- PROTOKOLL ---\n\n{kwargs['protocol_text']}\n\n--- SLUT ---"

    if "decisions_json" in kwargs and "{decisions_json}" not in config["prompt"]:
        prompt += f"\n{kwargs['decisions_json']}"

    if "decisions_list" in kwargs and "{decisions_list}" not in config["prompt"]:
        prompt += f"\n{kwargs['decisions_list']}"

    if "decisions_text" in kwargs:
        prompt += f"\n{kwargs['decisions_text']}"

    if "headlines_text" in kwargs:
        prompt += f"\n{kwargs['headlines_text']}"

    return {
        "prompt": prompt,
        "model": config["model"],
        "max_tokens": config["max_tokens"],
    }


# ═══════════════════════════════════════════
# Pipeline: Run multiple prompts in sequence
# ═══════════════════════════════════════════

def run_pipeline(protocol_text: str, api_key: str, quality_check: bool = False) -> dict:
    """
    Run the full summarization pipeline:
    1. Summarize (main extraction)
    2. Generate SEO metadata
    3. Generate social posts
    4. Generate newsletter subject
    5. (Optional) Quality check with Sonnet

    Returns combined result dict.
    """
    import anthropic
    import json

    client = anthropic.Anthropic(api_key=api_key)
    results = {}

    def call_llm(prompt_key, **kwargs):
        p = build_prompt(prompt_key, **kwargs)
        model_map = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-4-20250514"}
        msg = client.messages.create(
            model=model_map[p["model"]],
            max_tokens=p["max_tokens"],
            messages=[{"role": "user", "content": p["prompt"]}]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3]
        return json.loads(raw), msg.usage

    # Step 1: Main summarization
    print("  1/4 Summarizing...")
    summary, usage1 = call_llm("summarize", protocol_text=protocol_text)
    results["summary"] = summary
    results["tokens"] = {"input": usage1.input_tokens, "output": usage1.output_tokens}

    # Normalize IDs and paragraph refs
    mt = summary.get("meeting_type", "x")[:2].lower()
    d = summary.get("date", "unknown")
    for i, dec in enumerate(summary.get("decisions", [])):
        pr = dec.get("paragraph_ref", str(i))
        if "id" not in dec:
            dec["id"] = f"{d}_{mt}_{pr.replace(', ', '_')}"
        if pr and not pr.startswith("§"):
            dec["paragraph_ref"] = f"§ {pr}"

    # Step 2: SEO metadata
    if summary.get("decisions"):
        print("  2/4 Generating SEO...")
        decisions_text = "\n".join(
            f'- ID:{dec["id"]} | {dec["headline"]} | {dec.get("summary","")}'
            for dec in summary["decisions"]
        )
        try:
            seo, usage2 = call_llm("generate_seo", decisions_text=decisions_text)
            results["seo"] = seo
            results["tokens"]["input"] += usage2.input_tokens
            results["tokens"]["output"] += usage2.output_tokens
            # Merge SEO data back into decisions
            seo_map = {s["id"]: s for s in seo.get("decisions", [])}
            for dec in summary["decisions"]:
                if dec["id"] in seo_map:
                    dec["seo"] = seo_map[dec["id"]]
        except Exception as e:
            print(f"  SEO generation failed: {e}")

    # Step 3: Social posts
    if summary.get("decisions"):
        print("  3/4 Generating social posts...")
        decisions_text = "\n".join(
            f'- [{dec["id"]}] {dec["headline"]}: {dec.get("summary","")}'
            + (f' (Omstritt)' if dec.get("contested") else "")
            for dec in summary["decisions"]
        )
        try:
            social, usage3 = call_llm("social_posts", decisions_text=decisions_text)
            results["social_posts"] = social.get("posts", [])
            results["tokens"]["input"] += usage3.input_tokens
            results["tokens"]["output"] += usage3.output_tokens
        except Exception as e:
            print(f"  Social posts failed: {e}")

    # Step 4: Newsletter subject
    print("  4/4 Generating newsletter subject...")
    headlines_text = "\n".join(
        f'- {dec["headline"]}' + (f' (Omstritt)' if dec.get("contested") else "")
        for dec in summary.get("decisions", [])
    )
    try:
        subj, usage4 = call_llm("newsletter_subject", headlines_text=headlines_text)
        results["newsletter_subjects"] = subj.get("subjects", [])
        results["tokens"]["input"] += usage4.input_tokens
        results["tokens"]["output"] += usage4.output_tokens
    except Exception as e:
        print(f"  Newsletter subject failed: {e}")

    # Step 5: Quality check (optional, uses Sonnet = more expensive)
    if quality_check:
        print("  5/5 Quality check (Sonnet)...")
        try:
            qc, usage5 = call_llm("quality_check",
                summary_json=json.dumps(summary, ensure_ascii=False),
                protocol_text=protocol_text[:50000])  # Trim for context window
            results["quality_check"] = qc
            results["tokens"]["input"] += usage5.input_tokens
            results["tokens"]["output"] += usage5.output_tokens
        except Exception as e:
            print(f"  Quality check failed: {e}")

    # Calculate cost
    tin = results["tokens"]["input"]
    tout = results["tokens"]["output"]
    # Haiku pricing (approximate)
    results["cost_usd"] = (tin * 0.25 / 1_000_000) + (tout * 1.25 / 1_000_000)
    if quality_check:
        # Sonnet pricing for the QC step is higher
        results["cost_usd"] += (usage5.input_tokens * 3 / 1_000_000) + (usage5.output_tokens * 15 / 1_000_000)

    return results


# ═══════════════════════════════════════════
# Standalone: Run connection detection across all protocols
# ═══════════════════════════════════════════

def detect_all_connections(all_decisions: list, api_key: str) -> list:
    """
    Analyze all decisions across meetings and find connections.
    all_decisions: list of (decision_dict, meeting_dict) tuples
    Returns list of connection dicts.
    """
    import anthropic, json

    # Build a compact list for the prompt
    lines = []
    for dec, meeting in all_decisions:
        contested = " [OMSTRITT]" if dec.get("contested") else ""
        tags = ", ".join(dec.get("tags", []))
        lines.append(
            f'- ID:{dec["id"]} | {meeting["date"]} {meeting["meeting_type"]} | '
            f'{dec["headline"]}{contested} | Tags: {tags}'
        )

    decisions_list = "\n".join(lines)
    p = build_prompt("detect_connections", decisions_list=decisions_list)

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=p["max_tokens"],
        messages=[{"role": "user", "content": p["prompt"]}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]

    result = json.loads(raw)
    return result.get("connections", [])
