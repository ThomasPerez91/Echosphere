# Documentation Echosphere

État intégré : étape 5A, domaine économique interne, scheduler et shell ; 5B contrats intégrés.
Sur PR #7 : [socle Portal C01](03-technical/portal-foundation.md) et [comptes C02](03-technical/portal-registration.md) implémentés ; [C03 sessions Portal/CSRF](03-technical/portal-sessions.md) ajouté ; [C04 opérations sensibles sans MFA](03-technical/portal-account-security.md) livré. [C05 MFA](03-technical/portal-mfa.md) et [C06 lobby/mTLS](03-technical/portal-game-control.md) livrés ; [C07 handoff/sessions Game](03-technical/game-handoff.md) livré, fusionnés via PR #7. Intégrée via PR #8 (`0e2ca11`) :
[API Colony sécurisée et UI Colony](03-technical/colony-api-ui.md), première boucle jouable. [Économie v0.1](01-game-design/colony-economy-v0.1.md) et
[défense future](01-game-design/planetary-defense.md) distinguent règles implémentées et orientations.

## Lire dans cet ordre

1. [Vision et limites](00-product-vision.md).
2. [Modes et instances futures](01-game-design/game-modes.md), [Sessions](01-game-design/player-session.md), [boucle](01-game-design/core-loop.md) et [économie](01-game-design/resources-economy.md).
3. [Architecture](03-technical/architecture.md), [modèle conceptuel](03-technical/data-model.md), [temps](03-technical/event-engine.md).
4. [Roadmap](05-project/roadmap.md), [backlog](05-project/backlog.md) et [questions ouvertes](05-project/open-questions.md).
5. [Definition of Done](04-quality/definition-of-done.md).

Pour un travail UI, consulter aussi les [références visuelles cibles](visual-reference/README.md) :
direction artistique distincte des spécifications métier.

Les fichiers de chaque domaine sont indexés depuis la vision, l'architecture et la roadmap.

## Statuts obligatoires

| Statut | Sens |
| --- | --- |
| Implémenté | Présent dans le code de la branche indiquée ; ne signifie ni fusionné ni validé produit |
| Décision validée | Validation utilisateur claire et source identifiable |
| Balance provisoire | Chiffre/nom/courbe à simuler et rééquilibrer |
| Orientation validée | Direction confirmée, détails et implémentation encore ouverts |
| Proposition | Suggestion non validée, même si ancienne réponse d’assistant |
| Question ouverte | Arbitrage Qxx à résoudre, pas réponse déduite du code |
| Futur / post-MVP | Système non implémenté ou reporté ; ne l’autorise pas dans le lot présent |
| Abandonné / hors périmètre | Exclu de la cible concernée, pas une feature en attente automatique |

Les anciennes marques « validé/orientation/provisoire/futur » se lisent selon cette table et la
portée indiquée. Une valeur v0.1 peut être implémentée et provisoire simultanément. Les ADR acceptées
ne prouvent pas la présence de leur code ; une proposition ne devient décision qu’avec validation claire.

## Accès durable et références

- [Passation](06-handoff/README.md), [sources](06-handoff/source-map.md), [décisions](06-handoff/decision-status.md),
  [risques](06-handoff/known-gaps.md), [audit #5](06-handoff/pr-5-audit.md), [collaboration Work/Codex/Claude Code](06-handoff/work-codex-handoff.md).
- [Portal/Game ADR 0008](adr/0008-control-plane-game-data-plane.md) : frontières validées et socle 5C intégré via PR #7, sans certification production ;
  [architecture](03-technical/architecture.md), [modèle](03-technical/data-model.md), [sécurité](03-technical/security.md).
- [ADR index](adr/README.md), [roadmap](05-project/roadmap.md), [questions Q01–Q56](05-project/open-questions.md).
- [Contrats 5B](03-technical/identity-contracts.md) : décisions validées et consolidées le 2026-10-29,
  **implémentées dans leur périmètre 5C (C02–C08), fusionnées via PR #7** ; 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`). Le registre
  Q40–Q56 distingue clôtures, détails techniques délégués et reports support/email/modes. 5C
  terminé et fusionné (`ff6ef89`), 5D intégrée via #8 (`0e2ca11`). Lot courant :
  étape 11 Première IA (AI00/AI01 documentaires, Q11 ouverte) ; Colonisation intégrée via PR #13 (`a33a452`) ; étape 9 Flottes intégrée via PR #12 (`3a528b6`) ; étape 8 System View intégrée via PR #11 (`e011fd3`) ; étape 7 Galaxy + Exploration intégrée via PR #10 (`773e05c`), [technique](03-technical/galaxy-api-ui.md).
  [Research](05-project/step-6-plan.md) intégrée via PR #9 (`437844e4`), Q05 close ; [API/UI](03-technical/research-api-ui.md). Étape 12 non commencée.

Le [source-map](06-handoff/source-map.md) est le plan de lecture par grande zone et explique les
sources accessibles/partielles/non accessibles. Pas d’export privé brut ou de garantie d’exhaustivité
sur les conversations Space Game qui n’ont pas pu être consultées.


Compléments actuels sur PR #7 : [C08 parcours et shell](03-technical/portal-game-ui.md),
[C09 recette et opérations](03-technical/portal-operations.md). 5D intégrée via #8 ; Research intégrée via PR #9, aucune exposition production.

Plan historique : [plan étape 7](05-project/step-7-plan.md), Q06/Exploration validées avec amendements le 31/10/2026 ; G02–G10 autorisés après CI préalable 5/5 verte.

## État post-merge étape 7 — 31/10/2026

Étape 7 intégrée via PR #10, merge `773e05c`, CI post-merge 41220568486 success (5/5).
Q06/Q08 et Exploration livrées ; anciens checkpoints ci-dessus historiques.
Étape 8 ensuite menée sur `work/step-8-system-view` (S00–S10).

## État post-merge étape 8 — 31/10/2026

Étape 8 intégrée via PR #11, merge `e011fd3`, CI post-merge 41231820338 success (5/5).
Étape 9 ensuite menée sur `work/step-9-fleets` (F00–F11).

## État post-merge étape 9 — 01/11/2026

Étape 9 intégrée via PR #12, merge `3a528b6`, CI post-merge 41322146062 success (5/5).
Historique avant fusion : étape 10 Colonisation, branche `work/step-10-colonization` (PR #13). Q07 close
avec amendements, COL02–COL11 réalisés. Étape 11 alors non commencée, aucun merge autorisé.

Étape 13 : [Relations Q18](01-game-design/relations.md), [contrat technique](03-technical/relations-api-ui.md), [plan R00–R11](05-project/step-13-plan.md) ; lot 13B : [premier contact](01-game-design/first-contact.md).
Étape 10 : [Colonisation Q07](01-game-design/colonization.md), [contrat technique](03-technical/colonization-api-ui.md), [plan COL00–COL11](05-project/step-10-plan.md).
Étape 9 : [Flottes Q09](01-game-design/fleets.md), [contrat technique](03-technical/fleets-api-ui.md), [plan F00–F11](05-project/step-9-plan.md).
Étape 8 : [contrat System View](01-game-design/system-view.md), [projection/navigation](03-technical/system-view.md), [plan S00–S09](05-project/step-8-plan.md).

## État post-merge étape 10 — 01/11/2026

Étape 10 intégrée via PR #13, merge `a33a452b416ec83d4e8b91d84292913d18db5a40` ;
CI post-merge 41340653571 success (5/5), vérifiée le 01/11/2026. Colonisation/Q07 et la
sous-décision Q04 v0.5 livrées. Lot courant : **étape 11 Première IA**, branche
`work/step-11-first-ai` depuis master propre. AI00/AI01 documentaires seuls autorisés ;
Q11 ouverte, aucun code IA engageant avant sa validation explicite. Étape 12 Combat non commencée.
[Plan AI00–AIxx](05-project/step-11-plan.md). Aucun merge ni suppression de branche autorisé.

Étape 11 AI01 : [audit/architecture proposés](03-technical/ai-engine.md#ai01--audit-du-code-intégré),
[Q11 A1–A10 non validée](01-game-design/artificial-intelligence.md#arbitrages-demandés-avant-ai02),
[plan conditionnel](05-project/step-11-plan.md). Arrêt avant AI02 ; aucun code IA ni étape 12.

État courant étape 11 : Q11 close avec amendements le 01/11/2026 ; AI02–AI10 réalisés sur la
PR #14 (reprise Claude Code après limite Codex, travail local préservé), [contrat technique](03-technical/first-ai.md).
AI11 revue/CI/Ready en cours ; aucun merge ni Combat. Les statuts documentaires AI01 ci-dessus sont historiques.

## État post-merge étape 11 — 02/11/2026

Étape 11 Première IA intégrée via PR #14, merge `f79d9f6d0c3ebd9d230344b5a0c2aeaef9f4ce6b` ;
CI post-merge 41358533969 success (5/5), vérifiée le 02/11/2026 ; Q11 close. Les états courants
étape 11 ci-dessus sont historiques. Lot courant : **étape 12 Combat MVP**, branche
`work/step-12-combat`, PR Draft unique. Q02/Q10 closes pour le Combat MVP v0.7 seulement,
[décisions](01-game-design/combat.md#q02q10--décisions-combat-mvp-v07-02112026), [plan COM00–COM11](05-project/step-12-plan.md).
Étape 13 Relations non commencée ; aucun merge ni suppression de branche autorisé.

## État post-merge étape 12 — 02/11/2026

Étape 12 Combat MVP intégrée via PR #15, merge `067a4e58863b910785764591d8bf3af4b0ec18e0` ;
Full CI post-merge 41375165508 success (5/5), vérifiée le 02/11/2026. Les états courants étape 12
ci-dessus sont historiques. Lot courant : **étape 13 Relations IA minimales**, branche
`work/step-13-ai-relations`, PR Draft unique. Q18 close pour l'étape 13 le 02/11/2026 avec amendements,
[proposition B1–B12](01-game-design/relations.md), [plan R00–R11](05-project/step-13-plan.md).
R02–R11 autorisés. Lot 13B pré-MVP [premier contact](01-game-design/first-contact.md) (Q57/Q58) documenté,
non implémenté avant fusion de l'étape 13. Aucun merge ni suppression de branche autorisé.
