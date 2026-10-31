# Étape 5D — API Colony sécurisée et UI Colony interactive

**Statut : historique du lot 5D terminé et intégré à master via PR #8, merge `0e2ca11`.**
CI post-merge 41144706921 success, vérifiée le 31/10/2026. L’étape 6 devient le lot courant documentaire,
avec arrêt Q05 avant implémentation. Les exclusions ci-dessous décrivent la portée historique de 5D.
Base : master `ff6ef89` (fusion de PR #7, 5C), CI post-merge verte. Contrats : [5B](../03-technical/identity-contracts.md),
[C07 handoff](../03-technical/game-handoff.md), [économie v0.1](../01-game-design/colony-economy-v0.1.md),
[ADR 0007](../adr/0007-colony-economy.md), [ADR 0008](../adr/0008-control-plane-game-data-plane.md).
Canonique technique : [API et UI Colony](../03-technical/colony-api-ui.md).

## Objectif

Première boucle jouable : compte Portal → lobby → handoff → GameSession → colonie réelle → stocks
et infrastructures → construction réservée → progression persistante → achèvement par le worker →
nouvel état visible → action suivante. Les services Colony 5A restent l’autorité ; les routes
authentifient, autorisent et délèguent. Aucun deuxième scheduler, aucune donnée fictive runtime.

## Sous-tickets

| Ticket | Contenu | Sortie |
| --- | --- | --- |
| D00 | Synchronisation post-merge 5C, branche, plan, statuts historiques | Plan publié, statuts 5C fusionnés |
| D01 | Contrat API Colony et projection autorisée (service de lecture) | Canonique, projection testée sans recalcul de règles |
| D02 | Permissions et lecture HTTP (liste + détail) | Chaîne session → accès → binding → colonie, refus sans fuite |
| D03 | Commande HTTP de construction | Idempotency key, CSRF/origine, transaction unique, activité explicite |
| D04 | Annulation, idempotence et concurrence | 100/80 théoriques, Q39 plafonnement/perte atomiques, courses testées |
| D05 | UI Vue d’ensemble Colony | Données réelles, top bar ressources, file |
| D06 | UI Infrastructures interactive | Construire/améliorer/annuler, états de mutation |
| D07 | Responsive, accessibilité, erreurs | 320/390/768/1440, clavier, viewport réel |
| D08 | Résilience Portal/Game et worker | Recette Portal coupé, expiration refusée |
| D09 | Recette complète, docs, clôture | Suites, smokes, CI, PR prête pour revue |

## Données de partie

Aucun parcours produit ne crée encore Empire/Planète/Colonie : la création de partie reste hors lot
(modes Q19–Q29, Q55). Tests et recettes construisent le graphe minimal par fixtures explicitement
réservées aux bases `*_test` (Universe provisionné par Portal via mTLS, économie et colonie de
référence via les services 5A, binding Empire par `SetUniverseAccess`). Aucune fixture runtime,
aucun compte magique, aucun bouton « Créer une partie ».

## Hors lot

Recherche, galaxie, exploration, flottes, colonisation, IA, combat, diplomatie, partage d’Empire
(Q21), défense active (Q30–Q38), orbite jouable, population, commerce, WebSocket, notifications
complètes. Q39 est incluse par instruction complémentaire du 31/10/2026. L’étape 6 ne commence pas dans ce lot.
