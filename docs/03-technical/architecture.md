# Architecture technique

**Statuts : Game Backend implémenté jusqu’à 5A, intégré par PR #5 ; cible Portal/Game validée,
non implémentée.** État d’intégration et CI dans [progress.md](../../progress.md).

## Réalité du dépôt

React/TypeScript/Vite ; Game Backend Python/FastAPI, SQLAlchemy/Alembic ; PostgreSQL autoritaire.
Le Compose actuel comprend frontend, backend, postgres, migrate et worker. API/worker sont deux
processus du même monolithe gameplay, pas deux microservices. Aucun Portal ou Accounts DB présent.
Le frontend est un shell sans partie active, pas un lobby ni un client de gameplay interactif.

| Zone actuelle | Responsabilité implémentée |
| --- | --- |
| backend/app/api, core, persistence | Sondes, configuration/pool et modèles, aucune API métier publique |
| backend/app/simulation | Horloge UTC, production exacte, EventStream/ScheduledEvent et worker |
| backend/app/colony | Domaine interne construction/économie, transactions et snapshots |
| game_data/rulesets/v0.1 | Paramètres validés strictement, balance provisoire, copie par univers |
| backend/migrations | 0001–0004, migrations explicites avant API/worker |
| frontend/src | Navigation responsive et sous-vues Colony en préparation, readiness via proxy |

Les domaines Game futurs restent modulaires : recherche, exploration/connaissance/rapports,
flottes/combat, relations et IA. Ils partagent les transactions Game pertinentes. Humains, IA et
headless doivent utiliser les mêmes services ; le domaine ne dépend pas d’HTTP ou de la présence.
Redis/WebSocket ne sont pas livrés et ne seront jamais l’autorité gameplay.

## Cible de plateforme — décision validée, future

[ADR 0008](../adr/0008-control-plane-game-data-plane.md) est la référence canonique : deux backends
indépendants, chacun monolithe modulaire, bases conceptuellement distinctes et séparables.

| Plan | Backend et DB futurs | Frontière |
| --- | --- | --- |
| Portal Control Plane | Accounts/Auth/Lobby → Accounts DB | Comptes globaux, plusieurs parties, création/join et cycle de vie global des participations |
| Game Data Plane | Monolithe gameplay existant → Game DB | État autoritaire, droits minimaux nécessaires au jeu, événements et workers |

Portal ne peut pas écrire en SQL dans Game DB. Provision/grant/revoke/join passent par une interface
Game interne, authentifiée et idempotente. Le client fait ensuite ses commandes **directement à
Game**, sans transit ni appel synchrone au Portal par commande. Après ticket très court/unique,
Game établit une GameSession autonome ; format, durées, révocation et protocoles restent ouverts.

L’isolation cible inclut CPU/RAM, pools, scaling, DB et réseau distincts ; la logique en modules ne
suffit pas. Portal indisponible peut bloquer nouvelles connexions/entrées, pas interrompre les
univers/workers ou sessions Game établies dans leur contrat. Pas de garantie DDoS sur la pile locale.
Le Game Backend ne conserve pas les mots de passe/credentials Accounts.

**Historique remplacé en partie** : l’ADR 0001 prévoyait initialement un backend unique pour toute
la plateforme. ADR 0008 affine cette frontière ; le monolithe modulaire gameplay est conservé.
Il ne s’agit pas d’une autorisation de créer 10–20 microservices ni de modifier Docker maintenant.

## Invariants d’instance et temps

Universe est la frontière d’une partie, pas un User ou un processus. Compte global →
UniverseMembership → Universe → éventuellement Empire/rôle/permissions ; l’empire partagé reste Q21.
Les FK composites, scopes d’univers et projections de fog complètent les contrôles applicatifs.
Controller_type human/ai ne prouve ni identité ni droit. Memberships/comptes restent sans tables.

EventStream(universe_id,cursor_at,next_sequence) → ScheduledEvent(stream_id,universe_id).
ColonyTimeline associe explicitement colonie/stream/univers ; settled_at et ResourceBalance règlent
l’économie. Pas de owner_kind/owner_id sans FK ni second scheduler. Handlers sans commit, effet
externe ou verrou d’un autre stream. Rattrapage complet avant dépense ; exactitude indépendante
de la fréquence de lecture. Ruleset et vitesses par univers, jamais en singleton métier.

## Prochain travail

PR #5 fusionnée sur master 8214e0b. Le lot 5B autorisé le 2026-10-29 prépare les contrats
identité/session/Portal-Game dans [identity-contracts](identity-contracts.md) : décisions utilisateur
partielles Q40–Q44 sur login et limites temporelles, mécanismes encore proposés et non implémentés.
Les arbitrages nécessaires précèdent 5C fondation compte/lobby, puis 5D API Colony protégée.
Voir [roadmap](../05-project/roadmap.md), [sécurité](security.md), [API](api.md),
[modèle](data-model.md), [temps](event-engine.md) et [questions](../05-project/open-questions.md).
