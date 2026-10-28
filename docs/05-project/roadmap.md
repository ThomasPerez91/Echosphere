# Roadmap

**Statut : ordre de travail orientatif validé dans le brief ; aucun calendrier engagé.**

Le MVP est la cible atteinte après l'étape 17, pas après le bootstrap. Les étapes structurent les
livraisons ; tests, mobile, sécurité et balance commencent dès qu'ils deviennent pertinents.
L'étape 16 industrialise les simulations, elle n'interdit pas les petits tests d'équilibre plus tôt.

| Étape | Intitulé | Livrable | Critère de sortie |
| --- | --- | --- | --- |
| 0 | Documentation + bootstrap | Docs complètes, sondes, placeholder, Compose, checks | Démarrage et qualité ; PR ouverte sans merge |
| 1 | Fondation technique | Configuration, contrats applicatifs, préparation auth et migrations | Limites modulaires claires, Q16 cadrée |
| 2 | Universe / Empire / System / Planet / Colony | Modèles et migrations minimales | Relations et contraintes testées, pas de génération prématurée |
| 3 | Moteur temporel | Production différée, événements persistants et reprise | Horloge injectée, idempotence, concurrence et rattrapage vérifiés |
| 4 | Design system responsive | Navigation et composants des vrais écrans | Parcours mobile/clavier et états réseau validés |
| 5 | Boucle Colony | Stocks, secteurs, infrastructures et petites files | Dépenses transactionnelles, coûts versionnés et production correcte |
| 6 | Research | Recherche globale et programmation suivante | Prérequis et application unique à échéance |
| 7 | Galaxy + Exploration | Générateur seedé, missions et connaissances | 30–50 systèmes orientatifs, reproductibilité et non-fuite |
| 8 | System View | Lecture des mondes et présences connues | Détails datés selon connaissances, mobile utilisable |
| 9 | Fleets | Petit catalogue et missions asynchrones | Unités engagées une seule fois et arrivées récupérables |
| 10 | Colonization | Expansion significative et intégration colonie | Concurrence sur un monde résolue sans double propriétaire |
| 11 | Première AI | Utility/Goals et profils simples | Services communs, décisions reproductibles, connaissance limitée |
| 12 | Combat MVP | Résolution et rapports militaires simples | Q02/Q10 arbitrées, simulation et rejeu des résultats |
| 13 | Relations IA minimales | Interactions compréhensibles entre civilisations | Q18 arbitrée, pas de diplomatie avancée anticipée |
| 14 | UX sessions courtes | Bilan, alertes et actions prioritaires | Préparation quotidienne en environ dix minutes sur mobile |
| 15 | Onboarding | Démarrage guidé vers première exploration | Premier cycle compris sans surcharge |
| 16 | Simulation/balance headless | Campagnes multi-seeds et profils | Métriques et versions consignées, écarts discutés |
| 17 | Stabilisation MVP | Bugs, sécurité, performance, sauvegarde et recette | Boucle complète jouable et DoD satisfaite |

## Suivi et workflow actuels

Statut exact dans [progress.md](../../progress.md). master est l'intégration stable ; nouvelles
branches work/... depuis master et PR vers master, CI/revue puis merge sur autorisation. Tags et
releases identifiées plus tard. develop n'est plus une étape permanente ou obligatoire.
PR #2 est fusionnée sur master ; la correction de PR #3 se fait sur work/step-3-time-engine, sans
branche empilée ni branche Étape 4. Étape 4 seulement après correction, revue et fusion de PR #3.

## Compatibilité des modes futurs

Le MVP se construit en solo avec IA. Parties privées entre amis et univers multijoueurs persistants
sont futurs, sans code de modes/participation maintenant. Universe reste une frontière d'instance
isolée ; pas de durée maximale obligatoire pour la famille persistante. Q19–Q29 cadreront règles,
places, participation, fin, accès et vitesses avant d'ajouter un jalon d'implémentation multijoueur.
Le séquencement post-MVP reste indicatif et n'impose pas de développer ces systèmes à l'étape 3.
Voir [modes](../01-game-design/game-modes.md) et [ADR 0006](../adr/0006-universe-game-instance.md).

## Dépendances et risques

Le temps précède construction/recherche ; la connaissance précède exploration et IA ; flottes et
colonisation précèdent une IA expansionniste utile ; les protections hors connexion précèdent un
combat exposé aux joueurs. À chaque étape, réduire le périmètre plutôt qu'introduire les systèmes
post-MVP pour combler une question ouverte.

## Après le MVP

| Version envisagée | Contenu |
| --- | --- |
| v0.2 | Coop |
| v0.3 | Diplomatie avancée |
| v0.4 | Renseignement / espionnage |
| v0.5 | Commerce |
| v0.6 | IA avancée, mémoire, réputation |
| v0.7 | Exploration avancée et événements |
| v0.8 | Combat avancé |
| v0.9 | Alliances |
| v1.0 | Stabilisation et première release publique complète |

Ce séquencement n'oblige pas l'IA MVP à commercer avant l'existence des règles de commerce.
Voir [releases](releases.md), [backlog](backlog.md) et [questions ouvertes](open-questions.md).
