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

PR #2 était ouverte vers master au début et a été fusionnée sur instruction explicite de Thomas :
a065ad80eeb6db73438e61b1d6cde8bc3293e06d. PR #3 reste sur work/step-3-time-engine, cible master.
Thomas a autorisé sa correction puis sa fusion après vérification de la CI finale, ainsi que la
suppression conditionnelle de develop sans écart à conserver. Consulter GitHub pour confirmer les
résultats effectifs ; ne pas prendre ce texte pour une autorisation couvrant d'autres PR.

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
Aucune Étape 4 ni branche correspondante avant correction, revue et fusion de PR #3 ; cette mission
s'arrête après PR #3 corrigée/intégrée et le contrôle conditionnel de develop.
