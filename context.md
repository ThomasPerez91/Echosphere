# Contexte stable — Echosphere

**Statut : référence de reprise, pas autorisation générale.** Mise à jour 2026-10-30.
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

## Implémentation — Game 5A intégré, Portal C01–C08 sur PR #7

PR #5 fusionnée le 2026-10-28 ; vérification GitHub/local le 2026-10-29 : master
8214e0bd30a00bf0336264a428e6975d307350ba, CI 40765430216 verte. Recette locale WSL2/Compose
et suites 101 backend/11 frontend/5 Chromium effectuées ; périmètre et limites dans progress.

Checkpoint du 28/10/2026 : 5A et la passation sont portées par PR #5, alors ouverte.
Vérifier GitHub : après fusion de #5, considérer 5A/passation comme intégrées à master ; l’état
GitHub réel prévaut sur ce checkpoint. Fondations et shell 0–4 intégrés dans master 54f928e au départ ;
source fonctionnelle 58e8f7c, checkpoint 5be00da vert (101 backend, 11 frontend, 5 Chromium, Compose).
Sur master après 5B : aucun compte, authentification, membership, lobby fonctionnel ou API gameplay.
**5C intégré à master via PR #7 (`ff6ef89`) : C01** ajoute le socle Portal backend/frontend,
Accounts DB/metadata/pool/Alembic p0000 séparés et HTTPS local portal.echosphere.localhost/game.echosphere.localhost:8443.
C02 ajoute inscription/Argon2id/vérification email/outbox durable et formulaires, migration p0001.
[Recette C02](docs/03-technical/portal-registration.md). C03 ajoute connexion/sessions/profils Portal, CSRF et intentions de logout persistées.
[Recette C03](docs/03-technical/portal-sessions.md). [C04](docs/03-technical/portal-account-security.md) ajoute step-up, reset/changements sensibles sans MFA
et logout global. [C05](docs/03-technical/portal-mfa.md) ajoute TOTP/WebAuthn, dix secours, récupération
limitée et preuves MFA des opérations sensibles ; garde-fous privilégiés WebAuthn, sans console admin.
[C06](docs/03-technical/portal-game-control.md) ajoute memberships/lobby, outbox et listener privé
mTLS Game : droits effectifs, révisions/epochs et acquittements des révocations compte/appareil.
[C07](docs/03-technical/game-handoff.md) ajoute le handoff et les sessions Game, sans API Colony. [Recette C01](docs/03-technical/portal-foundation.md).
Routage/TLS, mTLS privé et livraison réelle sur bases temporaires testés ; aucune protection de charge prétendue.
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
Ticket signé asymétriquement court/unique (60 s), pré-auth navigateur 5 min puis GameSession opaque
autonome ; client gameplay directement à Game sans appel Portal par commande. Interface privée mTLS,
outbox Portal, état d’accès Game versionné et application idempotente. Portal possède l’intention,
Game les droits effectifs. Aucun credential Accounts en Game DB.

**5B validé et consolidé le 2026-10-29, partiellement implémenté par C02–C08 sur PR #7** :
[contrats canoniques](docs/03-technical/identity-contracts.md),
[statuts Q40–Q56](docs/05-project/open-questions.md).
Email/mot de passe Argon2id MVP, identité indépendante, vérification email avant handoff ; récupération
30 min/unique, changement d’email 1 h avec preuves liées, révocation globale après reset/changement
sensible selon contrat. MFA TOTP/WebAuthn facultative joueurs ; WebAuthn obligatoire privilégiés,
deux authentificateurs avant privilèges production. Step-up par action 5 min/unique ; dix secours
≥128 bits, récupération limitée 15 min sans Game/admin ; perte totale bloquée sans procédure approuvée.

Portal : 7 j absolus/72 h inactif ; Game : 8 h absolues/2 h inactif, au plus valid_until. Seules les
interactions explicites classées serveur comptent, trafic automatique et timestamp client exclus.
Droits Game : maximum 8 h depuis confirmation Portal, sans glissement ni reset en panne ; révocation
reçue immédiate, refus à échéance, univers/workers et actions acceptées continuant. Renouvellement
avec Portal disponible et nouvelle confirmation/handoff. Retour lobby sans logout ; portées de logout
session Game, appareil ou compte entier distinctes, révocation distante persistée/rejouée et UI fidèle.

Corrections finales : ajout de facteur ou régénération volontaire de secours avec step-up existant
sans révocation globale imposée, toujours audités/notifiés ; autres effets MFA selon tableau canonique.
Appareil = profil navigateur ; plafonds initiaux 10 appareils/compte et 10 univers Game actifs/appareil
configurables, jamais limites de memberships. Chaque frontend utilise son API même origine ; CORS
credentials refusé par défaut, exception uniquement sur besoin explicite et allowlist minimale.

Détails techniques délégués aux lots dépendants, sans nouveau questionnaire par paramètre. Restent
différés : procédure support joueur/privilégié Q48 (blocage sans procédure), fournisseur et configuration
production Q49, règles des modes Q55/Q19–Q29 et partage Empire Q21. Aucun arbitrage supplémentaire
nécessaire à 5B identifié. Architecture cadrée ne signifie pas sécurité implémentée/testée.
[ADR 0008](docs/adr/0008-control-plane-game-data-plane.md), [architecture](docs/03-technical/architecture.md).

## Workflow et prochain travail

master stable, work/... → PR master → CI/revue → merge explicitement autorisé. Pas de develop
permanente, force push, branche empilée ou release implicite. ChatGPT Work (GitHub), Codex local et
Claude Code local (WSL2) suivent les mêmes règles/DoD, sans mémoire partagée : checkpoint « Reprise
rapide » de progress, revue croisée dans les PR, un seul écrivain par répertoire/branche et worktrees
pour le parallélisme ; [protocole commun](docs/06-handoff/work-codex-handoff.md), validé le 2026-10-30.
La passation documentaire de la branche #5 est historique depuis la fusion de #5 ; tout nouveau lot
autorisé part de master synchronisée sur une nouvelle branche work/....
PR #6 fusionnée sur instruction explicite le 2026-10-29 : master
63bb7d1c902e9c0fbae3497d4a36c107a80eb611. **5B documentaire terminé et intégré à master** ;
contrats validés, sous-ensembles C02–C08 implémentés sur PR #7 seulement. Q40–Q47, Q50–Q54 et Q56 clos pour le cadrage 5B ;
reports Q48/Q49/Q55 conservés selon le registre, aucun arbitrage rouvert.

Lot précédent **5C — Portal Account/Lobby foundation**, branche
work/step-5c-portal-account-lobby créée depuis master fraîchement synchronisée en fast-forward.
Premier checkpoint documentaire 1c27497 et cadrage 8122cf7 publiés avant code. L’utilisateur a ensuite
autorisé « alors go » : C01–C08 implémentés et testés sur PR #7, recette de clôture C09 réalisée puis revue/validations finales par Claude Code le 2026-10-30 : 5C terminé, PR #7 fusionnée dans master le 2026-10-30 (`ff6ef89`, CI post-merge verte).
**Lot courant autorisé : 5D — API Colony sécurisée et UI Colony interactive** sur
work/step-5d-secure-colony-ui depuis ce master ; [plan 5D](docs/05-project/step-5d-plan.md). Étape 6 non commencée ;
aucune fusion sans instruction explicite. [Roadmap](docs/05-project/roadmap.md),
[Q01–Q56](docs/05-project/open-questions.md), [checkpoint](progress.md).
