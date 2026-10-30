# Documentation Echosphere

État intégré : étape 5A, domaine économique interne, scheduler et shell ; 5B contrats intégrés.
Sur PR #7 : [socle Portal C01](03-technical/portal-foundation.md) et [comptes C02](03-technical/portal-registration.md) implémentés ; [C03 sessions Portal/CSRF](03-technical/portal-sessions.md) ajouté ; [C04 opérations sensibles sans MFA](03-technical/portal-account-security.md) livré. MFA/handoff futurs. Aucune partie jouable ni
API gameplay publique. [Économie v0.1](01-game-design/colony-economy-v0.1.md) et
[défense future](01-game-design/planetary-defense.md) distinguent règles implémentées et orientations.

## Lire dans cet ordre

1. [Vision et limites](00-product-vision.md).
2. [Modes et instances futures](01-game-design/game-modes.md), [Sessions](01-game-design/player-session.md), [boucle](01-game-design/core-loop.md) et [économie](01-game-design/resources-economy.md).
3. [Architecture](03-technical/architecture.md), [modèle conceptuel](03-technical/data-model.md), [temps](03-technical/event-engine.md).
4. [Roadmap](05-project/roadmap.md), [backlog](05-project/backlog.md) et [questions ouvertes](05-project/open-questions.md).
5. [Definition of Done](04-quality/definition-of-done.md).

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
  [risques](06-handoff/known-gaps.md), [audit #5](06-handoff/pr-5-audit.md), [Work ↔ Codex](06-handoff/work-codex-handoff.md).
- [Portal/Game ADR 0008](adr/0008-control-plane-game-data-plane.md) : décision cible **auth future**, socle C01 sur PR #7 ;
  [architecture](03-technical/architecture.md), [modèle](03-technical/data-model.md), [sécurité](03-technical/security.md).
- [ADR index](adr/README.md), [roadmap](05-project/roadmap.md), [questions Q01–Q56](05-project/open-questions.md).
- [Contrats 5B](03-technical/identity-contracts.md) : décisions validées et consolidées le 2026-10-29,
  **partiellement implémentées sur PR #7 (C02–C04)** ; 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`). Le registre
  Q40–Q56 distingue clôtures, détails techniques délégués et reports support/email/modes. Lot courant
  5C : checkpoint/cadrage effectués, C01–C04 implémentés sur PR #7 ; C05 suit, 5D non commencé.

Le [source-map](06-handoff/source-map.md) est le plan de lecture par grande zone et explique les
sources accessibles/partielles/non accessibles. Pas d’export privé brut ou de garantie d’exhaustivité
sur les conversations Space Game qui n’ont pas pu être consultées.
