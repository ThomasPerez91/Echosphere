# Architecture Decision Records

**Statut : index canonique.** Une ADR décrit une décision et ses conséquences, pas une autorisation
de l’implémenter dans n’importe quel lot. Conserver l’historique et signaler explicitement ce qui
est affiné/superseded. Les détails produit ouverts restent dans [Qxx](../05-project/open-questions.md).

| ADR | Statut de décision / état du code |
| --- | --- |
| [0001 — Monolithe modulaire](0001-modular-monolith.md) | Historique bootstrap ; frontière plateforme affinée/superseded partiellement par 0008, monolithe Game conservé |
| [0002 — Modèle temporel](0002-event-driven-time-model.md) | Décision validée ; implémentée depuis #3, document original historique 0 |
| [0003 — Responsive](0003-responsive-web-ui.md) | Décision validée ; shell implémenté #4/#5, détails visuels Q15 |
| [0004 — Persistance](0004-world-persistence.md) | Décision technique implémentée, portée historique 1–2 |
| [0005 — Streams et temps](0005-colony-time-engine.md) | Décision technique implémentée/corrigée #3, generic EventStream |
| [0006 — Instance Universe](0006-universe-game-instance.md) | Décision validée ; scope implémenté, modes/memberships futurs, identité précisée en 0008 |
| [0007 — Colony et ruleset](0007-colony-economy.md) | Implémenté sur #5 ouverte, balance provisoire et Q39 ouverte ; non renuméroté |
| [0008 — Portal/Game isolables](0008-control-plane-game-data-plane.md) | Décision validée le 2026-10-28, **cible non implémentée**, mécanismes Q40–Q56 ouverts |

Dates de transcription des ADR 0001–0008 : 2026-10-28 ; cela ne prétend pas dater exactement chaque
conversation d’origine. [Index des décisions](../06-handoff/decision-status.md) et
[provenance](../06-handoff/source-map.md) qualifient les validations effectivement retrouvées.
