# Carte des sources et références canoniques

**Statut : inventaire de provenance accessible au 2026-10-28, sans prétention d’accès complet aux chats.**

## Sources effectivement consultées et limites

| Source | Accès réel | Usage et limite |
| --- | --- | --- |
| S1 — instruction de passation jointe à cette mission | Texte complet lu | Validation explicite actuelle pour produit, compte global et Portal/Game ; seul son contenu projet est synthétisé |
| S2 — fil courant et extraits de conversations transmis dans ce fil | Accessibles dans le contexte de session | Historique des instructions/fusions et brief 5A ; pas l’ensemble du projet Space Game |
| S3 — dépôt sur 5be00da et master 54f928e | Fichiers/état Git lus, inventaire des documents, code/tests pertinents relus | Réalité implémentée et références canoniques ; une formulation ancienne n’est pas une validation utilisateur indépendante |
| S4 — PR #1 à #5, commits et CI GitHub | Métadonnées/descriptions #1–5, diff du dernier commit #5, CI et jobs #5 consultés | Historique technique ; les descriptions anciennes ne prouvent pas l’état actuel de leur PR |
| S5 — recherche contextuelle ciblée Space Game/Echosphere | Extraits et synthèses de messages retournés, pas conversations intégrales | Confirme partiellement demandes de passation, compte multi-parties et séparation Portal/Game ; ne prouve ni exhaustivité ni lecture des originaux |
| Sources de fichiers signalées par la recherche contextuelle | Synthèses secondaires seulement | Pas de nouveau fichier projet directement ouvert par ce biais ; ne pas compter comme confirmation indépendante de S1 |
| Autres conversations Space Game et autres pièces du projet | Pas de catalogue complet ni accès direct attesté | Non consultées, aucune promesse d’avoir tout transféré |

La liste de fichiers source attachés au projet est vide dans cette session ; cela ne prouve pas
qu’aucun document n’existe ailleurs. Les textes joints visibles sont des instructions, pas un export
automatique du projet. Aucun résultat de recherche sans rapport avec Echosphere n’est transféré.
Les sources privées sont résumées sans URL privée, identifiant de conversation ou transcript brut.

## Complément de provenance 5B — 2026-10-29

Arbitrages utilisateur explicites dans la session de travail de PR #6 : contrats successifs puis
validation du bloc complet en quatorze points avec corrections MFA, plafonds configurables et CORS.
Synthèse canonique dans [identity-contracts](../03-technical/identity-contracts.md), statuts détaillés
au registre Q40–Q56. Le bloc validé donne aussi délégation des détails techniques et reports explicites ;
aucune validation déduite de la seule proposition de l’assistant. Aucun transcript brut ajouté.
État réel de PR #6, SHA/CI observés et checks locaux dans progress et la description de PR.
Les sources S1–S5 ci-dessus restent le relevé historique de passation du 28/10.

## Références canoniques par zone

| Zone | Référence à modifier en premier | Statut / provenance |
| --- | --- | --- |
| Vision, inspirations et non-goals | [Vision](../00-product-vision.md), [boucle](../01-game-design/core-loop.md), [sessions](../01-game-design/player-session.md) | Décision validée ; S1/S2 et docs initiales PR #1 |
| Ressources, niveaux, coûts et stockage | [Économie v0.1](../01-game-design/colony-economy-v0.1.md), [game_data](../../game_data/rulesets/v0.1/colony.json), [catalogue](../../game_data/rulesets/v0.1/infrastructures.json) | Implémenté sur #5 / Balance provisoire ; brief 5A S2, S3/S4 |
| Règles de construction, arrondis, snapshots | [ADR 0007](../adr/0007-colony-economy.md), [calcul](../03-technical/resource-calculation.md) | Implémenté ; décisions techniques retrouvées via GitHub, pas une validation de toutes les politiques produit |
| Taille des planètes et spécialisation | [Planètes](../01-game-design/planets-colonies.md), [modèle](../03-technical/data-model.md) | Décision validée : 12/2 = départ de référence seulement, variation future ; S1 et brief 5A |
| Recherche, galaxie, exploration, flottes, colonisation | [Recherche](../01-game-design/research.md), [galaxie](../01-game-design/galaxy.md), [exploration](../01-game-design/exploration.md), [flottes](../01-game-design/fleets.md), [colonisation](../01-game-design/colonization.md) | Futur ; contraintes confirmées S1, valeurs/domaines proposés qualifiés dans les docs |
| AI | [IA produit](../01-game-design/artificial-intelligence.md), [moteur IA](../03-technical/ai-engine.md) | Orientation validée, non implémentée ; S1 et docs PR #1 |
| Solo, multijoueur privé, persistant, late join | [Modes](../01-game-design/game-modes.md), [ADR 0006](../adr/0006-universe-game-instance.md) | Décisions de compatibilité, modes futurs ; S1, PR #3 et S3/S4 |
| Défense et renseignement | [Défense planétaire](../01-game-design/planetary-defense.md), [fog](../01-game-design/fog-of-war.md), [combat](../01-game-design/combat.md) | Orientation validée, systèmes futurs ; brief 5A/S1, PR #5 |
| Relations/diplomatie/commerce | [IA produit](../01-game-design/artificial-intelligence.md), [backlog](../05-project/backlog.md), [Q18](../05-project/open-questions.md) | Relations minimales futures ; avancé post-MVP, mécanismes ouverts |
| Architecture actuelle et temps | [Architecture](../03-technical/architecture.md), [temps](../03-technical/event-engine.md), [ADR 0001–0007](../adr/README.md) | Implémenté selon code et PR #1–5 ; provenance initiale de certains choix seulement GitHub |
| Portal/Game, comptes et sessions | [Contrats 5B](../03-technical/identity-contracts.md), [ADR 0008](../adr/0008-control-plane-game-data-plane.md), [sécurité](../03-technical/security.md), [modèle](../03-technical/data-model.md), [API](../03-technical/api.md) | Décision validée ; C01–C08 sur PR #7, handoff/GameSession C07 livrés ; S1/S5, arbitrages 5B puis instruction C01 du 29/10 |
| UX | [Architecture de l’information](../02-ux-ui/information-architecture.md), [design system](../02-ux-ui/design-system.md), [mobile](../02-ux-ui/mobile.md) | Shell implémenté #4/#5 ; choix visuels encore proposés, parcours Portal futur S1 |
| Questions, séquence et vérification | [Questions](../05-project/open-questions.md), [roadmap](../05-project/roadmap.md), [tests](../04-quality/testing-strategy.md) | Registres canoniques ; S1 et GitHub |
| Passation et checkpoint | [AGENTS](../../AGENTS.md), [context](../../context.md), [progress](../../progress.md), [procédure](work-codex-handoff.md) | Procédure commune ; S1, état réel S3/S4 |

## Historique GitHub lu

| PR | Lot | État observé au départ / nuance |
| --- | --- | --- |
| [#1](https://github.com/ThomasPerez91/Echosphere/pull/1) | Documentation et bootstrap | Fusionnée ; 47 documents historiques, pas l’état actuel |
| [#2](https://github.com/ThomasPerez91/Echosphere/pull/2) | Fondation et modèles | Fusionnée sur master ; description develop/release historique **superseded** par #3 |
| [#3](https://github.com/ThomasPerez91/Echosphere/pull/3) | Streams génériques isolés | Fusionnée, fixe le workflow master et ADR 0006 |
| [#4](https://github.com/ThomasPerez91/Echosphere/pull/4) | Shell responsive | Fusionnée ; sa description « reste ouverte » est un historique dépassé |
| [#5](https://github.com/ThomasPerez91/Echosphere/pull/5) | Économie Colony et passation | Ouverte, mergeable, non fusionnée sur 5be00da au départ ; vérifier sa tête après cette mission |

Aucune proposition d’une ancienne description de PR n’est promue automatiquement en validation
produit. Les décisions nouvelles de S1 priment sur les anciens textes incompatibles, avec renvoi
vers l’ADR qui les affine ; leur présence en documentation ne signifie pas qu’elles sont codées.
