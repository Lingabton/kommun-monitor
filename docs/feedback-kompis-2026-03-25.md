# Feedback från kompis — 2026-03-25

## Sammanfattning
Stark idé, men känns mer som "lovande demo" än "vass publikprodukt".
Tre huvudproblem: förtroende, konkretion, vanebildning.

## Prioriterad backlog

### P1 — Förtroende & trovärdighet
- [x] "Varför lita på detta?"-sektion: offentliga källor, länk till original, AI kan ha fel, ingen koppling till kommunen, öppen data, kontakt/rättelsefunktion
- [x] Metodtransparens på insiktssidan: definiera "omstritt", "ovanliga allianser", "uppmärksamhetsvärde"
- [x] Ta bort/neutralisera laddade formuleringar ("i praktiken total kontroll" → "majoriteten vann 98% av voteringarna")
- [x] "Senast uppdaterad" + antal protokoll/beslut/tidsperiod tydligt i toppen

### P2 — Startsidan: konkret värde direkt
- [x] Visa ett riktigt skarpt beslut i hero (inte bara "så funkar det")
- [x] Starkare informationshierarki: värde först, bevis sen, metod sist
- [x] Nyckeltal i toppen: antal beslut, möten, senast uppdaterad
- [x] Teaser-kort för Partier och Insikter
- [x] Tydligare CTA: "Se senaste besluten"

### P3 — Språk & kvalitet
- [x] "voteringer" → korrekt svenska
- [x] "1 reservationer" → singularis/pluralis
- [x] Blandning svenska/engelska i API-docs
- [x] Ta bort "Gratis" överallt i endpoint-listan
- [ ] Generellt språklyft för seriösare ton

### P4 — Neutralitet
- [x] Insiktssidan: försiktigare språk, torrare formuleringar
- [x] "Mest uppmärksamhetsvärda" → "Mest omstridda"
- [x] Undvik redaktionella formuleringar i automatgenererad text

### P5 — Vanebildning & retention
- [ ] Email-prenumeration (Buttondown eller liknande)
- [ ] "Nytt sedan ditt senaste besök"
- [ ] "Veckans viktigaste beslut"
- [ ] "Följ ämne: skola, bygg, trafik"
- [x] Fixa RSS-feed (gav fel vid test — relativa URLs fixade)

### P6 — Målgrupp
- [x] Startsidan 100% medborgarfokuserad
- [x] API/docs/data nedtonat — en rad för utvecklare, inte i huvudnav
- [x] Separera medborgarupplevelse från nördupplevelse

### P8 — Närvaro/frånvaro
- [x] Frånvarolistan: visa bara >10% frånvaro, aggregerat per parti (inte individer)

### P7 — Insiktssidan
- [x] Metodtext per sektion (full "Om metoden" med definitioner)
- [ ] "Ovanliga allianser" och "Beslut som hänger ihop" = starkaste differentiering — framhäv dessa
- [x] Var tydlig med att det är automatisk analys, inte redaktionell bedömning

### P9 — Re-processa med ny prompt
- [ ] Alla 73 protokoll behöver re-processas med ny prompt (inkluderar alla ärenden, inte bara "intressanta")
- [ ] Ny prompt fångar: routine true/false flagga, kategori "formellt", inga skippade ärenden
- [ ] Uppskattad kostnad: ~$1-2 i Haiku API
- [ ] Kör via: `gh workflow run daily.yml -f mode=process-known` (hoppar över redan processade — behöver rensa process_state.json först)

### P10 — Feedback runda 2 (2026-03-25)
- [x] Skärp startsidan: "Följ vad Örebro kommun faktiskt beslutar" — mindre tech, mer relevant
- [x] Visa 3-5 riktiga beslut med ämnesetiketter direkt (skola, bygg, budget, omsorg, trafik)
- [x] Separera "Direkt från protokoll" vs "Automatiskt upptäckt mönster" med tydliga etiketter
- [x] Metodsektion: vilka möten ingår, vad ingår inte, hur beslut definieras, hur fel rapporteras
- [ ] Språktvätt: gå igenom all copy rad för rad, ta bort tech-ton, gör begrepp konsekventa
- [ ] Neutralitet: "dominerar", "ovanliga allianser", "driver frågor" behöver metodstöd eller neutral inramning

### P11 — Feedback runda 3: visuell design (2026-03-25)

Done:
- [x] Hero: kompaktare, vänsterställd, sökfält + filterchips i hero
- [x] Nav: "Senaste / Ämnen / Partier / Analys" (användarbehov > datastruktur)
- [x] Kort: skannbar struktur med "Antaget/Avslaget" + "För:/Emot:" istället för "JA:/NEJ:"
- [x] Kort klickbara (ämnes-korten)

Backlog:
- [ ] Mänskliga rubriker: "Kommunen säger nej till X" istället för "Motion om X avslås" (kräver prompt-ändring + re-processning P9)
- [ ] "Varför detta spelar roll"-rad per beslut (kräver prompt-ändring)
- [ ] Typografi: välj riktning — mer editorial/tidning eller mer dataprodukt
- [ ] Hero-siffror: flytta till tunn strip under hero istället för i den
- [ ] Alla expanderbara kort helklickbara (inte bara ▼)
- [ ] Snabbare filtrering: "Omstridda" som eget filter
- [ ] Strama upp avstånd/alignment för modernare känsla
