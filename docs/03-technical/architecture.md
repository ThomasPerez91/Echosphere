# Architecture technique

**Statuts : Game Backend implémenté jusqu’à 5A, intégré par PR #5 ; cible Portal/Game validée,
Portal C01–C05 implémenté sur PR #7, lobby/S2S/handoff futurs.** État d’intégration et CI dans [progress.md](../../progress.md).

## Réalité du dépôt

React/TypeScript/Vite ; Game Backend Python/FastAPI, SQLAlchemy/Alembic ; PostgreSQL autoritaire.
Le Compose conserve frontend, backend, postgres, migrate et worker Game ; C01 ajoute
portal-postgres/migrate/backend/frontend et local-edge, sans modifier le volume Game. API/worker sont deux
processus du même monolithe gameplay, pas deux microservices. Socle Portal C01 ajouté séparément sur PR #7 ; C02 ajoute comptes/vérification/email durable ; accès Game encore absent.
Le frontend est un shell sans partie active, pas un lobby ni un client de gameplay interactif.

| Zone actuelle | Responsabilité implémentée |
| --- | --- |
| backend/app/api, core, persistence | Sondes, configuration/pool et modèles, aucune API métier publique |
| backend/app/simulation | Horloge UTC, production exacte, EventStream/ScheduledEvent et worker |
| backend/app/colony | Domaine interne construction/économie, transactions et snapshots |
| game_data/rulesets/v0.1 | Paramètres validés strictement, balance provisoire, copie par univers |
| backend/migrations | 0001–0004, migrations explicites avant API/worker |
| frontend/src | Navigation responsive et sous-vues Colony en préparation, readiness via proxy |
| portal/backend | Sondes Portal, configuration PORTAL_*, pool/metadata Accounts et Alembic p0000–p0004 indépendants, comptes/vérification/email et sessions/CSRF/opérations sensibles/MFA Portal |
| portal/frontend | Readiness/retry et formulaires d’inscription/renvoi/confirmation, avec sessions/CSRF C03 |
| infra/local/Caddyfile | Deux origines HTTPS locales, CA Docker sans installation sur l’hôte |

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
Game établit une GameSession opaque autonome. Contrats 5B validés : ticket signé 60 s/unique,
révocations ciblées persistées, accès borné à 8 h depuis confirmation Portal, interface privée mTLS
et synchronisation idempotente. Détails techniques délégués à 5C/5D, sans nouvelle route en 5B.

L’isolation cible inclut CPU/RAM, pools, scaling, DB et réseau distincts ; la logique en modules ne
suffit pas. Portal indisponible peut bloquer nouvelles connexions/entrées, pas interrompre les
univers/workers ou sessions Game établies dans leur contrat. Pas de garantie DDoS sur la pile locale.
Le Game Backend ne conserve pas les mots de passe/credentials Accounts.

**Historique remplacé en partie** : l’ADR 0001 prévoyait initialement un backend unique pour toute
la plateforme. ADR 0008 affine cette frontière ; le monolithe modulaire gameplay est conservé.
Il ne s’agit pas d’une autorisation de créer 10–20 microservices. L’extension Compose C01 découle
du lot explicitement autorisé, sans interface interne mTLS ou nouvelle API gameplay anticipée.

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

PR #5 fusionnée sur master 8214e0b, puis **5B documentaire terminé et intégré à master via PR #6**,
merge `63bb7d1`. Les [contrats 5B](identity-contracts.md) sont validés, partiellement implémentés par C02–C05 sur PR #7.
Le [registre Q40–Q56](../05-project/open-questions.md) conserve clôtures, détails délégués et reports
support/email/modes. Lot courant autorisé : 5C compte/lobby, nouvelle branche depuis ce merge,
checkpoint documentaire et cadrage réalisés, socle C01 livré sur PR #7 ; C02 comptes/vérification livré ; C03 sessions livré ; C04 opérations sensibles et C05 MFA livrés ; C06 suit.
Aucun début de 5D API Colony,
aucune nouvelle fusion sans instruction explicite.
Voir [roadmap](../05-project/roadmap.md), [sécurité](security.md), [API](api.md),
[modèle](data-model.md) et [temps](event-engine.md).

[Socle Portal C01 et recette](portal-foundation.md) : implémenté sur PR #7, non intégré à master.

[C02 comptes et livraison](portal-registration.md) : worker email propre à Portal, Mailpit local,
clé de chiffrement dans volume privé ; aucun import ou credential Accounts dans Game.
