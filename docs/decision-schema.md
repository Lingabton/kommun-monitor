# Beslutsdataset — Schema v2

Varje beslut/arende i protokollet ger ett objekt med dessa falt.

## Identitet
| Falt | Typ | Beskrivning |
|---|---|---|
| paragraph_ref | string | Paragrafnummer, t.ex. "76" |
| headline | string | Protokollnara rubrik, max 15 ord |
| human_headline | string | Klarsprakig rubrik for vanliga manniskor. Verb forst. |

## Innehall
| Falt | Typ | Beskrivning |
|---|---|---|
| summary | string | 1-2 meningar, vad beslutades |
| plain_language_summary | string | 1 mening, for nagon utan forkunskap |
| relevance | string/null | Vem paverkas och hur? null om oklart |
| detail | string | 3-5 stycken med bakgrund och konsekvenser |
| quote | string/null | Ordagrant citat fran protokollet |
| quote_page | string/null | Sidhanvisning |

## Klassificering
| Falt | Typ | Varden |
|---|---|---|
| category | string | bygg, infrastruktur, skola, budget, miljo, trygghet, kultur, politik, regler, omsorg, naringsliv, formellt, ovrigt |
| decision_type | string | motion, interpellation, detaljplan, rapport, upphandling, budget, policy, taxa, remiss, valarende, informationsarende, delegation, ovrigt |
| outcome | string | bifallen, avslagen, besvarad, noterad, aterremitterad, bordlagd, delvis_bifallen, tillgodosedd |
| tags | string[] | 3-6 nyckelord |

## Rutin/substans
| Falt | Typ | Beskrivning |
|---|---|---|
| routine | boolean | true = formalia/rutin |
| routine_reason | string/null | Varfor det ar rutin: delegationsarende, formellt godkannande, etc |

## Paverkan
| Falt | Typ | Beskrivning |
|---|---|---|
| impact_level | string | ingen, begransad, tydlig, stor |
| public_interest_score | int 1-5 | 1=ingen bryr sig, 5=stor nyhetsvinkel |
| target_group | string[] | invanare, foretagare, elever, vardnadshavare, aldre, etc |

## Geografi
| Falt | Typ | Beskrivning |
|---|---|---|
| geographic_scope | string | hela_kommunen, stadsdel, skola, specifik_fastighet |
| location_name | string/null | Platsnamn |

## Politisk dynamik
| Falt | Typ | Beskrivning |
|---|---|---|
| controversial_level | string | ingen, lag, medel, hog |
| has_vote | boolean | Gick till formell omrostning |
| has_reservation | boolean | Nagon reserverade sig |
| voting.for | string[] | Partier som rostade ja |
| voting.against | string[] | Partier som rostade nej |
| voting.abstained | string[] | Partier som avstod |
| voting.result | string | Utfall i fritext |

## Kvalitet
| Falt | Typ | Beskrivning |
|---|---|---|
| confidence | string | hog, medel, lag — hur saker ar AI:n pa sin tolkning |
