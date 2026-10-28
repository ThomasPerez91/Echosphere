# Contexte stable — Echosphere

**Statut : référence de reprise, pas autorisation générale.** Mise à jour 2026-10-28.
Vérifier GitHub réel puis lire AGENTS → context → progress → [passation](docs/06-handoff/README.md).

## Produit validé, état distinct

Jeu web de stratégie spatiale asynchrone/persistant ; environ 10 minutes quotidiennes, 1–2 h utiles
pour analyser/décider sans rendement de présence. Trois ressources Alliages/Flux/Données, pas de
récolte manuelle ou pay-to-win. Empire lent + Command actif/asynchrone, combat éventuel dans la boucle.
IA stratégique sans LLM, Utility/Goals testable, mêmes règles/services/fog que les humains, pas de triche.
[Vision](docs/00-product-vision.md), [décisions](docs/06-handoff/decision-status.md).

Solo humain+IA = MVP ; privé/persistant futurs, pas de durée maximale obligatoire en persistant.
Universe = frontière d’instance, ni User ni processus ; late join et protections restent ouverts.
Compte global multi-parties validé conceptuellement : User → UniverseMembership → Universe →
éventuellement Empire/rôles/permissions ; pas de owner_user_id unique, empire partagé Q21 non arbitré.

## Implémentation — checkpoint du 28/10/2026, pas partie jouable

Checkpoint du 28/10/2026 : 5A et la passation sont portées par PR #5, alors ouverte.
Vérifier GitHub : après fusion de #5, considérer 5A/passation comme intégrées à master ; l’état
GitHub réel prévaut sur ce checkpoint. Fondations et shell 0–4 intégrés dans master 54f928e au départ ;
source fonctionnelle 58e8f7c, checkpoint 5be00da vert (101 backend, 11 frontend, 5 Chromium, Compose).
Aucun compte, Portal/auth, membership, lobby, API gameplay ou multijoueur implémenté.
Game : FastAPI/SQLAlchemy/Alembic/PostgreSQL + worker, React/TypeScript/Vite ; UTC, autorité serveur.
EventStream/ScheduledEvent génériques ; ColonyTimeline/ResourceBalance pour économie exacte.
Migration 0004 ajoute les quatre tables économiques sans modifier les anciennes révisions.

Ruleset JSON v0.1 strict, copie par univers, vitesses rationnelles et snapshots d’ordres ; balance
provisoire. Niveaux continus, pas plafond 5. 12 secteurs/2 orbitaux = planète de départ de référence
seulement, pas invariant futur. File 3/1, réservation immédiate, annulation 100/80, bonus industriel
à activation ; production réglée à date logique. Q39 reste ouverte pour saturation du remboursement.
Cascade dépendante implémentée, confirmation produit/UX à garder sous Q01. Voir [économie](docs/01-game-design/colony-economy-v0.1.md)
et [audit](docs/06-handoff/pr-5-audit.md) pour limites de capacité/immutabilité/initialiseur.

Défense future : réseau persistant à capacité/modules limités, coût surface/orbite, dommages/réparation,
Flux et renseignement à cadrer. UI Colony réservée à Vue d’ensemble/Infrastructures/Orbite/Défense,
sans données fictives ni huitième domaine global. Aucun combat/défense effective ; Q30–Q38 ouvertes.

## Architecture validée future — ADR 0008

Deux backends indépendants et isolables, chacun monolithe modulaire : Portal Accounts/Auth/Lobby
avec Accounts DB, Game gameplay existant avec Game DB. Bases/pools/CPU/RAM/scaling/réseau séparables.
Portal n’écrit jamais en SQL Game DB ; provision/grant/revoke/join via interface interne contrôlée,
authentifiée et idempotente. Pas de credentials de compte en Game DB.
Ticket court/unique puis GameSession autonome, commandes client directement à Game sans appel
Portal par commande. Panne Portal peut empêcher nouvelles entrées, pas arrêter univers/workers ou
sessions établies dans le contrat à définir. Mécanismes/durées/révocation restent Q40–Q56, Q16 partielle.
Ceci affine le backend unique historique ; aucun Portal, protocole ou Compose nouveau dans ce lot.
[ADR 0008](docs/adr/0008-control-plane-game-data-plane.md), [architecture](docs/03-technical/architecture.md).

## Workflow et prochain travail

master stable, work/... → PR master → CI/revue → merge explicitement autorisé. Pas de develop
permanente, force push, branche empilée ou release implicite. Work/Codex publient leur checkpoint
pour l’autre environnement ; [procédure commune](docs/06-handoff/work-codex-handoff.md).
La passation était limitée aux documents sur la branche existante #5, sans nouvelle PR, merge,
code métier, migration, game_data, dépendance, Docker ou test modifié. Si #5 est encore ouverte et
que la mission porte dessus, reprendre cette branche. Après sa fusion, synchroniser master et
partir sur une nouvelle branche work/... pour tout nouveau lot autorisé, sans recréer la branche #5.
progress porte le checkpoint et les actions de reprise avant/après fusion.
Après revue/intégration et nouveau lot autorisé : 5B contrats identité/Portal-Game, 5C fondation
compte/lobby selon cadrage, 5D API Colony sécurisée/UI réelle. Ne pas commencer Portal complet ou
multijoueur automatiquement. [Roadmap](docs/05-project/roadmap.md), [Q01–Q56](docs/05-project/open-questions.md).
