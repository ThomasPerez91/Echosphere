# Index central des décisions

**Statut : index, pas une seconde spécification.** Mise à jour 2026-10-28. Modifier d’abord le document
canonique, puis ce tableau et les Qxx concernés. « Implémenté » décrit le code de la branche, pas
une validation produit ou une fusion. Statuts définis dans [docs/README](../README.md).
Sources S1–S5 : [carte de provenance](source-map.md). Une proposition d’assistant seule n’est pas validée.
Actualisation 2026-10-29 : PR #5 fusionnée sur 8214e0b ; PR #6 en cadrage 5B avec arbitrages
utilisateur partiels Q40–Q44 acceptés, non implémentés. Aucun mécanisme Q45–Q56 fermé.

| Décision / élément | Statut | Justification | Canonique / ADR | Impact | Date/source |
| --- | --- | --- | --- | --- | --- |
| Web asynchrone, persistance et univers continu | Décision validée | Progression indépendante de la présence | [Vision](../00-product-vision.md), ADR 0002 | Produit et temps | 28/10/2026, S1/S2, PR #1 |
| Environ 10 min/jour, 1–2 h utiles sans rendement de connexion | Décision validée | Décider/analyser plutôt que récolter par clic | [Sessions](../01-game-design/player-session.md) | UX et métriques | S1, docs initiales |
| Empire + Command, combat éventuel dans la boucle | Décision validée | Deux rythmes compatibles avec l’asynchrone | [Boucle](../01-game-design/core-loop.md) | MVP cible, pas encore jouable | S1, PR #1 |
| Alliages / Flux / Données seulement | Décision validée | Lisibilité, pas de quatrième cœur implicite | [Ressources](../01-game-design/resources-economy.md) | Moteur/données/UI | S1, PR #1/#5 |
| Micro-unités, UTC, événements transactionnels | Implémenté | Exactitude et reprise | [Calcul](../03-technical/resource-calculation.md), ADR 0002/0005 | Autorité Game | PR #3, S3/S4 |
| Économie Colony, file 3/1, réservation et remboursement 100/80 | Implémenté / Balance provisoire | Première boucle interne et snapshots | [Économie v0.1](../01-game-design/colony-economy-v0.1.md), ADR 0007 | Pas d’API publique | Brief 5A S2, PR #5 fusionnée |
| Niveaux continus, 1–5 = early game | Décision validée / Implémenté | Progression longue | [Infrastructures](../01-game-design/buildings.md) | Remplace ancienne orientation I–V | Brief 5A et S1, 28/10/2026 |
| Croissances et chiffres v0.1 | Balance provisoire | À rééquilibrer par simulation | [Économie v0.1](../01-game-design/colony-economy-v0.1.md), game_data | Jamais constantes de service | PR #5, S1/S2 |
| 12 secteurs / 2 orbitaux | Balance provisoire, départ seulement | Capacités futures variables | [Planètes](../01-game-design/planets-colonies.md) | Initialiseur de référence actuel limité | S1, audit #5 |
| Refus de remboursement saturé Q39 | Question ouverte, code implémenté | Pas de perte/overflow caché, politique à valider | [Q39](../05-project/open-questions.md) | Ne pas généraliser en décision définitive | PR #5, S1 |
| Cascade d’annulation dépendante | Implémenté / Proposition produit | Préserve la continuité des niveaux | [Audit #5](pr-5-audit.md), Q01 | UX à confirmer | Choix technique retrouvé via S3/S4 |
| Recherche globale d’empire | Décision validée, future | Pas de centaines de technologies | [Recherche](../01-game-design/research.md) | Domaines/noms provisoires | S1 ; ancienne portée orientée précisée |
| Graphe 2D, routes, seed | Décision validée, future | Choix de chemins plutôt que grille OGame | [Galaxie](../01-game-design/galaxy.md) | 30–50 prototype = repère, tailles configurables | S1, PR #1 |
| Fog UNKNOWN/DETECTED/MAPPED/MONITORED | Orientation validée, future | Connaissance limitée aussi pour IA | [Fog](../01-game-design/fog-of-war.md) | Transitions/fiabilité Q08 | S1 ; aucun contrat final déduit |
| Flottes courtes et missions asynchrones | Orientation validée, future | Catalogue lisible, pas de designer complexe | [Flottes](../01-game-design/fleets.md) | Stats/routes/rappels Q09 | S1, docs initiales |
| Combat automatisé et protections offline | Futur / Question ouverte | Équité et lisibilité avant code | [Combat](../01-game-design/combat.md), Q02/Q10 | Préconditions combat | S1, docs initiales |
| Défense persistante à capacité limitée et modules | Orientation validée, future | Coût d’opportunité, dommages/réparation | [Défense](../01-game-design/planetary-defense.md) | Sous-vue Colony, Q30–Q38 ouvertes | Brief 5A/S1, PR #5 |
| IA Utility/Goals, testable sans LLM, mêmes règles/fog | Orientation validée, future | Autonomie sans triche ni moyens gratuits | [IA](../01-game-design/artificial-intelligence.md), [moteur](../03-technical/ai-engine.md) | Poids/profils Q11 | S1, docs PR #1 |
| Dialogue génératif non stratégique | Futur / post-MVP | Couche facultative sans autorité | [IA](../01-game-design/artificial-intelligence.md) | Aucun LLM moteur requis | S1 |
| Solo humain+IA puis privé/persistant | Décision validée, modes futurs | Universe frontière d’instance | [Modes](../01-game-design/game-modes.md), ADR 0006 | Late join et protections restent ouverts | PR #3, S1 |
| Compte global, plusieurs parties, Membership | Décision validée, non implémentée | Séparer compte et empire/partie | [Modèle](../03-technical/data-model.md), ADR 0008 | Empire partagé Q21 non fermé | S1, corroboration partielle S5 |
| Portal/Game, Accounts DB/Game DB séparés | Décision validée, non implémentée | Exposition et disponibilité distinctes | [ADR 0008](../adr/0008-control-plane-game-data-plane.md) | Affine la frontière plateforme de 0001 | S1, 28/10/2026 |
| Portal sans SQL Game, interface interne idempotente | Décision validée, non implémentée | Frontière de propriété et autorisation | [ADR 0008](../adr/0008-control-plane-game-data-plane.md) | Auth S2S et synchronisation ouvertes | S1 |
| Ticket court/unique puis GameSession autonome | Orientation validée, non implémentée ; durée 60 s/usage unique désormais validés | Pas de dépendance Portal par commande | [Contrats 5B](../03-technical/identity-contracts.md), ADR 0008 | Format/crypto/rejeu restent ouverts sous Q42/Q56 | S1, S5 partiel puis arbitrage utilisateur explicite du 29/10/2026 pour PR #6 |
| Login MVP email/mot de passe, Argon2id, email vérifié avant premier handoff, récupération courte/unique, identité globale indépendante | Décision validée, non implémentée | OIDC supplémentaire futur facultatif, aucun fournisseur imposé | [Contrats 5B](../03-technical/identity-contracts.md) | Q40 partiellement close ; paramètres, email et MFA ouverts | Arbitrage utilisateur explicite du 29/10/2026 pour PR #6 |
| Portal 7 j/72 h inactif, Game 8 h/2 h inactif, droits Game non glissants au plus 8 h depuis confirmation | Décision validée, non implémentée | Panne sans reset, révocation reçue immédiate, refus à valid_until, renouvellement via Portal/confirmation/handoff | [Contrats 5B](../03-technical/identity-contracts.md) | Parties de Q41/Q43/Q44 closes ; activité explicite seule, classée côté serveur, validée ; mécanismes ouverts | Arbitrage utilisateur explicite du 29/10/2026 pour PR #6 |
| Accès local versionné, ticket signé, sessions opaques, epoch et interface interne | Proposition, non implémentée | Préparer les mécanismes de 5B avec alternatives et scénarios | [Contrats 5B](../03-technical/identity-contracts.md) | Aucun mécanisme accepté par les seuls arbitrages temporels ; 5B en cours | 29/10/2026, préparation Codex local autorisée ; choix à valider |
| UX responsive et sept domaines globaux | Implémenté / Proposition visuelle | Mobile/clavier et états explicites | [UX](../02-ux-ui/information-architecture.md), ADR 0003 | Q15 reste ouverte ; Portal non livré | PR #4/#5, S1 |
| Diplomatie/commerce avancés, alliances, espionnage | Futur / post-MVP | Ne pas inventer des mécaniques pour compléter le MVP | [Roadmap](../05-project/roadmap.md), Q18 | Relations IA minimales étape 13 | Docs initiales ; S1 préserve les questions |
| master stable, PR, merge explicite | Décision validée | Référence commune Work/Codex | [AGENTS](../../AGENTS.md) | develop historique superseded | Instructions visibles S2, PR #3 |
| Clone OGame, RTS, city-builder détaillé, population/logistique lourdes | Abandonné / hors périmètre | Préserver un jeu web stratégique lisible | [Vision](../00-product-vision.md) | Aucune licence d’implémentation implicite | S1, non-goals initiaux |

La [roadmap](../05-project/roadmap.md) donne l’ordre, le [registre](../05-project/open-questions.md)
garde les inconnues, [progress](../../progress.md) porte les preuves réelles. Ne pas lire ce tableau
comme une autorisation générale de développement, fusion, déploiement ou publication de secrets.
