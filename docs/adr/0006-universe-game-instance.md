# 0006 — Universe est la frontière d'une instance de jeu

- Statut : acceptée, contrainte explicite de compatibilité future.
- Date : 2026-10-28.

## Contexte

Le MVP solo ne doit pas imposer une architecture incapable d'accueillir des parties entre amis ou
un univers persistant partagé. Les données, permissions, règles et échéances doivent rester isolées.

## Décision

Universe est une instance de jeu, pouvant être solo, privée ou persistante. Les entités d'une partie
y appartiennent directement/indirectement ; les workers peuvent traiter plusieurs instances.
Aucune hypothèse Universe=User ou processus=Universe, aucune dépendance à un navigateur connecté.
Les règles de gameplay futures sont configurables/versionnées par instance ou ruleset, pas en singleton.

La participation humaine sera conceptuellement Account/User ↔ UniverseMembership ↔ éventuellement
Empire ↔ rôle/permissions. Elle ne se réduit pas à Empire.owner_user_id. Authentification future :
User → Membership → Universe → permissions → Entity, contrôlée à chaque opération concernée.
Le controller_type human/ai existant ne représente ni identité ni autorisation.

## Conséquences et limites

Les FK inter-univers existantes sont conservées ; EventStream/ScheduledEvent et leurs adaptateurs
portent aussi une appartenance d'univers vérifiable en base. Les API filtreront leurs projections
selon participation et fog of war. WebSockets/notifications éventuels ne deviennent jamais autorité.

Aucun mode, compte, membership, invitation, lobby, matchmaking, équipe, alliance ou logique PvP ajouté.
Aucune valeur de vitesse, places, durée, fin ou protection nouvel arrivant fixée. L'univers persistant
n'a pas de durée maximale obligatoire ; ses modalités de late join restent ouvertes. Les familles
sont détaillées dans game-modes.md et Q19–Q29, pas converties en colonnes/configuration maintenant.

[Modes](../01-game-design/game-modes.md) · [Modèle](../03-technical/data-model.md) · [Questions](../05-project/open-questions.md)

## Portée et évolution documentaire

Note d’évolution : [ADR 0008](0008-control-plane-game-data-plane.md) confirme compte global,
plusieurs parties par utilisateur, Membership et sessions Game, sans implémentation de tables.
L’isolation Universe reste valide ; la v0.1 5A épingle désormais règles/vitesses économie/construction.
Les exclusions de code et valeurs non fixées ci-dessus décrivent le lot historique étape 3.
