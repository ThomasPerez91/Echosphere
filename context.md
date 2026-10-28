# Contexte de reprise — Echosphere

Mis à jour le 2026-10-28. Lire [AGENTS.md](AGENTS.md) puis [progress.md](progress.md) et vérifier
l'état GitHub réel avant toute action. Ce fichier décrit le cadre stable, pas une autorisation générale.

## Produit et instance

Stratégie spatiale persistante web, préparation quotidienne d'environ dix minutes, sessions longues
pour mieux décider et non produire par clic. Trois ressources Alliages/Flux/Données. IA sans LLM
au départ, mêmes règles/services et connaissance limitée. Pas de pay-to-win ni de récolte manuelle.

Universe est la frontière d'une instance isolée : solo (MVP humain+IA), partie privée future, univers
multijoueur persistant futur. Ce dernier fonctionne sans durée maximale obligatoire et indépendamment
des connexions. Ne pas supposer Universe=User ou processus=Universe. Aucune fonctionnalité multijoueur
implémentée : pas de comptes, membership, invitations, lobby, matchmaking, équipe ou alliance.
Concept futur : User/Account ↔ UniverseMembership ↔ éventuellement Empire ↔ rôles/permissions.
Pas de owner_user_id ajouté à Empire ; controller_type human/ai n'authentifie personne.
Règles/vitesses futures par Universe/ruleset/version, jamais singleton gameplay serveur.

## Workflow actuel (remplace develop)

master = intégration stable. Synchroniser master, créer work/feature, CI, PR vers master, revue puis
merge uniquement sur instruction. Pas de develop permanente ni de branche empilée pour contourner
une dépendance non intégrée. Tags/releases identifiées plus tard. Aucun changement du workflow ne
constitue une autorisation permanente de merge, publication ou suppression de branches.

## État et autorisation de cette mission

PR #4 fusionnée sur master : 54f928e2348781db43b335d4dcf569aadc0db6e9.
CI master verte vérifiée, run 40716684879, avant création de work/step-5a-colony-domain.
Thomas demande de poursuivre le brief joint : Étape 5A, domaine Colony et économie v0.1.
PR #5 vise master et reste non fusionnée. Source 58e8f7c entièrement verte en CI (101 backend,
11 frontend, 5 Chromium, migrations/Compose) ; checkpoint et limites dans progress.md. Aucun merge/tag/release/déploiement autorisé pour ce lot.
Domaine interne uniquement ; Q16 bloque API publique et UI interactive de 5B. Pas de faux user.

## Architecture et garanties

Monolithe modulaire React/TypeScript/Vite, Python/FastAPI, PostgreSQL, SQLAlchemy/Alembic. UTC,
backend autoritaire, migrations explicites avant API/worker. Aucun endpoint métier non protégé.
Scheduler générique : EventStream(universe_id,cursor_at,next_sequence) → ScheduledEvent.
ColonyTimeline lie explicitement colonie/stream/univers et garde settled_at/ResourceBalance.
FK composites, ordre due_at/séquence, idempotence, SKIP LOCKED, transactions/SAVEPOINT, retries et
reprise après crash. Les futurs adaptateurs typés de scope ne nécessitent pas de réécrire les événements.
Aucun owner_kind/owner_id sans FK. Les workers traitent plusieurs univers sans présence de navigateur.

## Reprise

Voir progress.md pour CI/SHA, [ADR 0005](docs/adr/0005-colony-time-engine.md) pour la correction du temps,
[ADR 0006](docs/adr/0006-universe-game-instance.md) et [modes](docs/01-game-design/game-modes.md).
Q01–Q29 restent au registre selon leur statut, sans inventer réponses multijoueurs/équilibrage.
Une future API vérifie User → Membership → Universe → permissions → Entity, plus fog of war.
5A ajoute universe_economies/colony_economies/colony_infrastructures/construction_orders et 0004.
JSON strict v0.1, règles épinglées par univers, multiplicateurs rationnels et snapshots d’ordres.
Niveaux continus (pas de plafond 5), secteurs identifiés, réservation et file 3/1, annulation 100/80 %.
Bonus industriel au démarrage du suivant, production/stockage exacts à date logique. Refus atomique
si remboursement exact ne tient pas (Q39) ; upgrades dépendants annulés en cascade.
Défense : préparation documentaire/UI seulement, réseau persistant à modules limité, Q30–Q38 ouvertes.
Colony : Vue d’ensemble/Infrastructures/Orbite/Défense sans données fictives ni huitième entrée globale.
Prochain lot : 5B quand identité/autorisation Q16 est cadrée, après revue/intégration de 5A.
Voir [économie](docs/01-game-design/colony-economy-v0.1.md), [défense](docs/01-game-design/planetary-defense.md)
et [ADR 0007](docs/adr/0007-colony-economy.md).
