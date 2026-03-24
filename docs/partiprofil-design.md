# Partiprofil-sida — Designdokument

## Vision

En sida per parti (`/parti/{abbr}/`) som ger väljaren ett komplett, lättförståeligt svar på frågan: **"Vad har det här partiet faktiskt gjort i Örebro kommun?"**

Tänk det som en "dejtingprofil" för partiet — inte vad de *säger* att de vill, utan vad de *faktiskt* har röstat, drivit och prioriterat. Sidan ska fungera som primär ingång inför valet 2026.

---

## Nuläge vs. mål

### Vad som redan finns (`/parti/v/` som exempel)

- Grundstats: antal röstningar, JA/NEJ/AVSTOD-procent
- Nyckelfrågor (kategorier + antal)
- Alliansinfo (röstar med/mot)
- Lista på NEJ-röster
- Lista på motioner

### Vad som saknas

Nuvarande sida är en **datadump**. Den svarar på "vad" men inte "varför det spelar roll". En väljare som landar där fattar inte snabbt vad partiet *står för* i praktiken.

---

## Sidans sektioner (i prioritetsordning)

### 1. Hero / Snapshot

**Syfte:** Ge hela bilden i 5 sekunder.

Innehåll:
- Partinamn, färg, logotyp-platshållare (partiförkortning i cirkel)
- Roll: "Majoritet" eller "Opposition"
- **En AI-genererad sammanfattning på 2-3 meningar** som fångar partiets profil i klartext

Exempeltext (genereras från data):
> "Vänsterpartiet sitter i opposition och är kommunens mest aktiva motionsställare med 11 motioner. De driver framför allt välfärdsfrågor — mindre barngrupper, högre löner för personal, läxfri skola — men förlorar nästan alla omröstningar mot majoriteten S+M+C."

**Implementationsnot:** Sammanfattningen kan genereras statiskt vid byggtid med AI baserat på partiets data (motioner, röstmönster, kategorier). Alternativt: skriv en template-motor som fyller i meningar baserat på datapunkter.

Designtanke: Sammanfattningen ska vara *journalistisk*, inte byråkratisk. Undvik "69% JA-röster" — säg istället "röstar med majoriteten i två av tre frågor".

---

### 2. Röstmönster — visuellt

**Syfte:** Visa HUR partiet röstar, inte bara siffror.

Två vyer:

**a) Helhetsbild (donut/bar)**
- JA / NEJ / AVSTOD — men med kontext
- "Röstade JA i 69% av omröstningarna" är meningslöst utan att veta att majoritetspartierna ligger på 98%
- **Jämför med genomsnittet**: Visa partiets profil relativt andra. En enkel bar chart med alla partier sorterade från mest JA till mest NEJ ger kontext direkt.

**b) Tidslinje (om möjligt)**
- Om ni har tillräckligt med datapunkter per möte: visa hur röstmönstret utvecklas över tid
- Alternativ: skippa om bara 4-5 möten finns, då blir det noise

**c) "Med vem?" — Alliansdiagram**
- Nuvarande "röstar oftast med/mot" som lista -> gör om till visuell graf
- Enklaste: horisontella bars per parti med antal gemensamma röster
- Avancerat: nätverksdiagram (kan vara overkill, bedöm)
- **Highlight ovanliga allianser**: Om V och SD röstat lika i 9 frågor, markera det med en "Ovanlig allians"-badge

---

### 3. Sakområden — Partiets profil

**Syfte:** Svara på "vad bryr sig partiet om?"

Nuvarande: En lista med "Regler: 4, Budget: 4, Politik: 3..."

Förbättring:
- **Radardiagram / polärdiagram** med partiets aktivitet per kategori
- Alternativt: Horisontella bars, sorterade efter aktivitet
- **Jämför med snittet**: Om alla partier har budget som topkategori är det inte intressant. Visa vad som STICKER UT. "V är överrepresenterat i skolfrågor jämfört med andra partier."
- **Klickbara kategorier**: Klicka på "skola" -> visa alla skolbeslut med partiets röst markerad

---

### 4. Motioner & Reservationer — "Vad driver de?"

**Syfte:** Visa partiets *initiativkraft* och var de väljer att ta strid.

Nuvarande: Enkel lista med motioner.

Förbättring:
- **Gruppera motioner per tema/kategori** istället för kronologiskt
- **Visa utfall tydligt**: Avslagen / Bifallen / Under beredning / Tillgodosedd
- **"Genomslagskraft"-metric**: Hur stor andel av motionerna ledde till faktisk förändring? (Bifallna + tillgodosedda / totalt)
- **Reservationer separat**: "X gånger har partiet formellt protesterat mot ett beslut" — med länk till respektive beslut
- **Framhäv unika motioner**: Motioner som BARA det här partiet drivit (inte kopior av andras)

Exempel-presentation:

```
Skola & förskola (3 motioner)
  Mindre barngrupper i förskolan — avslagen 2025-08-27
  Läxfri skola — avslagen 2025-08-27
  Välfärdspersonalens löner — avslagen 2025-08-27

Miljö & hållbarhet (1 motion)
  Återbruk i alla led — avslagen 2025-10-14

Trygghet & demokrati (2 motioner)
  Förtroendevaldas trygghet (hot/våld) — avslagen
  Policy för stöd vid hot — avslagen

Infrastruktur (1 motion)
  Återinför tre-timmarsbiljett — under beredning
```

---

### 5. "Stridslinjerna" — Omstridda beslut

**Syfte:** Visa var den verkliga politiska konflikten ligger.

- Lista de beslut där partiet röstade MOT majoriteten
- Varje beslut: kort sammanfattning + vem som var för/emot
- **Framhäv beslut med votering** (formell omröstning = extra konfliktnivå)
- Sortera efter "intresse-score": votering > reservation > enkel oenighet

Här är berättelsen för väljaren: "Det HAR är frågorna som partiet tycker är tillräckligt viktiga för att faktiskt bråka om."

---

### 6. Kontext-ruta: Majoritet vs. Opposition

**Syfte:** Förklara VARFOR siffrorna ser ut som de gör.

Många väljare förstår inte att oppositionens roll skiljer sig radikalt från majoritetens. En kort, permanent info-ruta (kanske collapsible) som förklarar:

- **Om majoritetparti (S/M/C):** "Socialdemokraterna ingår i den styrande majoriteten tillsammans med M och C. Det betyder att de flesta förslag som kommer till omröstning redan har deras stöd — därför röstar de JA i 98% av fallen. Att de inte lämnar motioner beror på att de driver sina frågor genom budgeten och styrningen istället."

- **Om oppositionsparti:** "Vänsterpartiet sitter i opposition. Deras främsta verktyg är motioner (egna förslag) och reservationer (formella protester). Att de 'förlorar' omröstningar beror inte på att de är svaga — det är så minoritetspolitik fungerar."

**Implementationsnot:** Detta kan vara en template med if/else baserat på `position: "Majoritet"/"Opposition"` i partidatan.

---

### 7. Jämför-knapp

**Syfte:** Naturlig brygga till nästa steg.

- "Jämför med annat parti" -> dropdown eller knappar med alla partier
- Leder till en jämförelsesida (kan vara framtida feature, men knappen bör finnas redan nu som placeholder)
- Alternativt: "Se alla partier" -> tillbaka till `/parti/`-översikten

---

## Datakällor (allt finns redan i API)

| Sektion | API-endpoint | Fält |
|---|---|---|
| Snapshot | `/parties/{abbr}.json` | name, position, color, total_votes, for/against/abstained_pct, motions_count |
| Röstmönster | `/parties.json` (alla) + `/parties/{abbr}.json` | for_pct, against_pct, top_allies, top_opponents |
| Sakområden | `/parties/{abbr}.json` | top_categories |
| Motioner | `/parties/{abbr}.json` | motions_filed (array) |
| Omstridda beslut | `/decisions.json` filtrerat | contested: true, voting.against innehåller partiet |
| Alliansdiagram | `/parties.json` | top_allies, top_opponents per parti |

---

## AI-genererad sammanfattning — hur?

Två alternativ:

**Alt A: Statisk, vid byggtid**
- Kör ett script som för varje parti tar all data och skickar till Claude API
- Generera 2-3 meningars sammanfattning
- Spara som fält i `parties/{abbr}.json`
- Pro: Snabbt, inga API-anrop vid sidladdning
- Con: Uppdateras inte automatiskt

**Alt B: Template-baserad (ingen AI)**
- Bygg meningar från data med logik:
  ```
  if position == "Majoritet":
    "{name} styr Örebro tillsammans med {allies}."
  else:
    "{name} sitter i opposition och har lämnat {motions_count} motioner."

  if motions_count > 8:
    "De är kommunens {rank} mest aktiva motionsställare."

  if top_categories[0] == "skola":
    "Skolfrågor är deras starkaste profil."
  ```
- Pro: Transparent, uppdateras automatiskt med ny data
- Con: Mindre elegant prosa

**Rekommendation:** Börja med Alt B (template). Byt till Alt A om ni vill ha finare språk — men templates ger er kontroll och kräver inget extra API-anrop.

---

## Designprinciper

1. **Mobil-först.** Majoriteten av väljare som googlar "hur röstar V i Örebro" gör det på telefonen.
2. **Kontext före data.** Aldrig en siffra utan förklaring. "69%" ska aldrig stå ensamt — alltid "69% (jämfört med 98% för majoriteten)".
3. **Neutral ton.** Sidan ska inte framställa något parti positivt eller negativt. Samma struktur för alla.
4. **Progressive disclosure.** Hero-sammanfattning -> visuella grafer -> detaljlistor. Väljaren ska kunna stanna efter 10 sekunder och ändå ha lärt sig något.
5. **Partiets egen färg som accent.** Använd `color` från API:et för att ge varje sida en unik känsla utan att ändra layout.

---

## URL-struktur

Ingen förändring behövs — `/parti/{abbr}/` finns redan. Sidan behöver bara berikas med mer innehåll och bättre presentation.

---

## Framtida kopplingar (inte i scope nu, men tänk på det)

- **Valguide/quiz** som leder tillbaka till partiprofilen: "Dina svar matchar V i 4 av 6 frågor -> Läs mer om V"
- **Sakfråge-vy** (`/amne/skola/`) som visar alla partiers ställning i en fråga — korsreferens till partiprofilen
- **Jämförelsesida** (`/jamfor/v-vs-s/`) — sida vid sida
- **Närvarodata** — om/när ni kan extrahera det ur protokollen, lägg till som sektion
- **Kandidatprofiler** — individuella ledamöter, inte bara partier (stor feature, men naturlig extension)

---

## Sammanfattning: Vad ska byggas?

1. **Berika `/parti/{abbr}/`-sidan** med sektionerna ovan (prioritera 1-5)
2. **Hämta all data från befintligt API** — ingen ny datainsamling behövs
3. **Template-baserad sammanfattning** (Alt B) som hero-text
4. **Visuella grafer** med befintligt CSS-ramverk (inga tunga JS-libs — ren CSS/SVG)
5. **Kontext-ruta** som förklarar majoritet/opposition
6. **Jämför-knappar** som placeholder för framtida feature
7. **Testa på mobil** — alla grafer ska fungera i 375px bredd
