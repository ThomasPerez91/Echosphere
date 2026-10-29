# Contexte stable — Echosphere

**Statut : référence de reprise, pas autorisation générale.** Mise à jour 2026-10-29.
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

## Implémentation — 5A intégrée, pas partie jouable

PR #5 fusionnée le 2026-10-28 ; vérification GitHub/local le 2026-10-29 : master
8214e0bd30a00bf0336264a428e6975d307350ba, CI 40765430216 verte. Recette locale WSL2/Compose
et suites 101 backend/11 frontend/5 Chromium effectuées ; périmètre et limites dans progress.

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
sessions encore valides. Décisions 5B validées le 2026-10-29 : email/mot de passe MVP, Argon2id
via bibliothèque maintenue, email vérifié avant premier handoff, récupération courte/unique et
global_user_id indépendant de l’email/méthode ; OIDC supplémentaire futur facultatif.
Portal : 7 j absolus/72 h d’inactivité ; Game : 8 h absolues/2 h d’inactivité ; ticket : 60 s/unique.
Droits Game : maximum 8 h depuis confirmation Portal, sans glissement sur activité ni reset en panne.
Révocation/suspension reçue immédiate ; à valid_until nouvelles commandes refusées, worker/univers
continuent. Renouvellement avec Portal disponible et nouvelle confirmation/handoff valide ; aucun
renouvellement autonome illimité, GameAccess pouvant expirer une session plus tôt.
Seules ces parties de Q40–Q44 sont closes ; mécanismes restants, Q45–Q56 et Q16 restent ouverts.
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
Le 2026-10-29, l’utilisateur autorise le prochain lot : préparation 5B sur
work/step-5b-identity-contracts depuis master synchronisée, PR #6 brouillon non fusionnée.
Les [contrats](docs/03-technical/identity-contracts.md) distinguent désormais les décisions
utilisateur ci-dessus des mécanismes encore proposés ; aucun compte/Portal/API livré.
Prochain arbitrage nécessaire : activité réinitialisant l’inactivité (Q41/Q43), dont polling.
Le lot reste 5B ; sa rédaction ne le déclare pas terminé et 5C/5D restent des lots séparés.
Après revue/intégration et nouveau lot autorisé : 5B contrats identité/Portal-Game, 5C fondation
compte/lobby selon cadrage, 5D API Colony sécurisée/UI réelle. Ne pas commencer Portal complet ou
multijoueur automatiquement. [Roadmap](docs/05-project/roadmap.md), [Q01–Q56](docs/05-project/open-questions.md).
