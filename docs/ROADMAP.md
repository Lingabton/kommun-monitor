# Beslutskollen — Färdplan & Strategi

## Vision
Sveriges mest tillgängliga källa för kommunala beslut. Börja i Örebro, skala till fler kommuner.

## Nuläge (April 2026)
- 596 beslut från KF + KS, 2023–2026
- AI-sammanfattningar via Claude
- Daglig pipeline via GitHub Actions
- Statisk sajt på GitHub Pages
- Alla nämnder aktiverade i discovery

## Fas 1: Etablera Örebro (Q2 2026)
**Mål:** Bli referenskälla för Örebro-politik

- [x] KF + KS-beslut
- [x] Daglig automation
- [x] Google Search Console
- [x] GoatCounter analytics
- [x] Alla 11 nämnder aktiverade
- [ ] Nyhetsbrev efter varje sammanträde (Buttondown/Mailchimp)
- [ ] Dela-funktion med OG-bilder per beslut
- [ ] Kontakta NA (Nerikes Allehanda) om datadelning
- [ ] 1000+ beslut milestone

## Fas 2: Växa i Örebro (Q3 2026)
**Mål:** Bli oumbärlig för journalister och medborgare

- [ ] Eget domännamn (beslutskollen.se)
- [ ] E-postalerts: "Nytt beslut om [ditt område]"
- [ ] Personliga bevakningar per ämne/område
- [ ] Bättre mobilupplevelse (PWA, offline)
- [ ] Kontakta ÖrebroKompassen, NA, SVT Örebro

## Fas 3: Monetisering (Q4 2026)
**Mål:** Hållbar finansiering

### Intäktsmodeller (ranked):
1. **Journalist-API** (150 kr/mån) — strukturerad data, webhooks vid nya beslut
2. **Organisationsbevakningar** (500 kr/mån) — företag/föreningar som berörs av beslut
3. **Kommun-SaaS** — erbjud andra kommuner samma tjänst (5000 kr/mån/kommun)
4. **Sponsring** — "Beslutskollen stöds av [lokal aktör]"
5. **Grants** — Vinnova, Internet Foundation, civic tech-fonder

### Inte:
- Inga annonser (förtroendefråga)
- Ingen betalvägg på enskilda beslut (offentlighetsprincipen)

## Fas 4: Skala nationellt (2027)
**Mål:** 10+ kommuner

- [ ] Multi-tenant arkitektur (en pipeline per kommun)
- [ ] Generisk scraper för kommunala anslagstavlor
- [ ] Central dashboard: "Sveriges kommunbeslut"
- [ ] Jämförelser mellan kommuner
- [ ] Partnerskap med SKR (Sveriges Kommuner och Regioner)

## Teknisk skuld att lösa
- [ ] Splitta data.json per år (prestanda)
- [ ] Schema-versioning på AI-output
- [ ] Validering av Claude-svar (JSON schema)
- [ ] Flytta från GitHub Pages till Cloudflare Pages (snabbare, custom domain)
- [ ] Backend för nyhetsbrev (Cloudflare Workers eller liknande)

## KPI:er att följa
- Unika besökare/vecka (GoatCounter)
- Antal beslut i databasen
- Tid från protokoll-publicering till sammanfattning
- Nyhetsbrevsprenumeranter
- API-anrop/dag
- Antal kommuner (fas 4)
