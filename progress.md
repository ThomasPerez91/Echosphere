# Progression — Echosphere

Mise à jour : 2026-10-30. [Contexte](context.md), [passation](docs/06-handoff/README.md).

## Lot courant — 5C : Portal Account/Lobby foundation

**Statut : C01–C03 implémentés et testés sur PR #7 ; 5C en cours, C04 opérations sensibles à suivre.**
5B documentaire terminé et intégré à master via PR #6 ; contrats validés, sous-ensembles comptes/vérification/sessions C02/C03 implémentés sur PR #7 seulement.
L’utilisateur autorise 5C et exige présentation du cadrage avant implémentation substantielle ; 5D exclu.
Aucune nouvelle fusion autorisée. Environnement : Codex local/WSL2.
Les checkpoints pré-code ci-dessous sont historiques ; l’état actuel de C03 est décrit en premier.

### C03 — connexion, appareils et sessions Portal, 2026-10-30

Instruction utilisateur « On poursuit » après C02. GitHub réel vérifié avant modification : PR #7
OPEN/brouillon, tête locale/distante 2025490b2e51f62519125bf2c859ebfc4cc9c3ba, base master
63bb7d1c902e9c0fbae3497d4a36c107a80eb611. Fetch et merge ff-only : déjà synchronisée, arbre propre.
CI C02 push 40942091538 et PR 40942099627 success observées. Dernier lot attesté : Codex local C02 ;
aucune autre tête publiée ni agent délégué. Même branche work/step-5c-portal-account-lobby, pas de merge.

Livré : [C03 canonique](docs/03-technical/portal-sessions.md), modules Portal sessions/API, migration
Accounts p0002 additive (browser_profiles, account_devices, portal_sessions, login_challenges,
logout_requests), login/challenge, cookies __Host- Secure/HttpOnly/host-only/SameSite Strict,
CSRF lié au secret/challenge, rotation sans report de l’absolu. Sessions Portal sept jours absolus /
72 h inactives, vérification avant activité, aucune résurrection. GET/bootstrap/readiness/flags client
ne comptent pas ; action explicite de navigation/actualisation dédiée avec CSRF. Profil navigateur
opaque, cap initial dix appareils configurable, comptage concurrent sous verrou User et aucune
éviction silencieuse. Même profil/onglets partagent la session ; cookies effacés ne révoquent pas
l’ancien état serveur. Quotas login/bootstrap persistants et distincts des demandes email.

Déconnexion ciblée : Portal révoqué + intention Game appareil/compte/session/epoch atomique. FK
composites et génération monotone ; répétition sans nouvelle génération ni cible étrangère. Aucun
transport/acquittement Game encore implémenté : état pending/UI fidèle, consommateur et tests
inter-plans C06/C07 futurs. Pas de logout tous appareils sans step-up futur, aucun reset/changement
email/MFA/membership/handoff/commande Colony dans C03. Les comptes non vérifiés peuvent accéder à
ce Portal minimal, jamais à Game (aucun handoff disponible). Aucune identité/partie runtime fictive.

Frontend : connexion, erreurs/cap avec action possible, connexions actives, actualisation volontaire
et fermeture ciblée. CSRF uniquement en mémoire, aucun stockage navigateur. Rotation dans un autre
onglet : relecture de la preuve sans rejouer l’action refusée ; réponse automatique tardive antérieure
à la connexion ignorée. Présence d’un onglet ou bootstrap automatique sans maintien de session.
Documentation/indexs/AGENTS/context/roadmap/passation et smoke TLS mis à jour ; contrats de décisions
5B et lignes Q01–Q56 inchangés, seuls statuts d’implémentation actualisés. Aucun code/dépendance ou
migration Game modifié ; p0000/p0001 Portal et ADR 0008 inchangés. Pas de nouvelle dépendance.

Tests locaux réellement exécutés dans les images Python 3.12/Node 22 :

- Backend : Ruff réussi ; **53 tests réussis, aucun ignoré** sur echosphere_c03_test dédiée,
  dont échéances exactes/rotation/non-activité, challenge concurrent unique, cap concurrent sans
  éviction, périmètres, FK de compte/session, génération monotone et rollback session/intention.
  Upgrade/check/roundtrip et downgrade peuplé refusé. Base jetable recréée lors de l’affinage de la
  migration encore non publiée, puis supprimée après recette ; aucune base conservée downgradée.
  Warning Starlette/httpx connu, sans échec.
- Frontend : npm ci, lint, **14 tests**, build et **9 scénarios Chromium** réussis : parcours C02
  préservés, login/refresh explicite/logout 320/1440, quatre largeurs clavier/retry et same-site natif.
  Captures inspectées ; UI à API interceptée distincte des tests HTTP/API/PostgreSQL.
- Compose initialement arrêté hors workers, remis en marche par up --build --wait ; volumes et
  données préservés. Deux bases/APIs/frontends/Mailpit healthy, workers running, migrate et
  secrets-init Exited(0). Alembic check Portal p0002 et Game 0004 sans dérive.
- smoke_compose.py et smoke_portal_compose.py réussis : TLS strict/noms, routage, CORS et pannes
  croisées/reprises. Extension C03 vérifie challenge/cookie sous TLS et refus sans session/mauvaise
  origine ; aucun compte créé, seulement des challenges anonymes expirables. Base Accounts
  conservée vérifiée à zéro User. Aucun changement hosts ou magasin de confiance hôte.
- 68 documents requis/liens valides, git diff --check sans erreur ; Qxx et décisions 5B comparées à
  2025490, aucun fichier Game ou migration Portal déjà publiée modifié. Secrets/artefacts exclus.

Échecs intermédiaires corrigés : format/tri/longueur Ruff et option Testing Library non typée dans
un test frontend (tests alors verts, build TypeScript en échec ; nouveau build réussi ensuite).
Aucune suite en échec n’est présentée comme passée. Source CI configurée inchangée, résultats de
la nouvelle tête à observer après commit/push puis consigner dans PR #7 avec son SHA effectif.

Limites : pas de recette complète navigateur hôte HTTPS, Windows/tactile/lecteur d’écran ou charge
attestée. Smokes TLS réels et scénarios UI interceptés sont séparés. Logout Game reste pending jusqu’à
C06/C07, aucune révocation distante annoncée instantanée ; procédures/fournisseur production Q49,
support Q48 et modes Q55 inchangés. WSL2/Docker utilisables pour les commandes exécutées, outils en
conteneurs jetables. Suite : **C04 opérations sensibles/step-up**, itérative avec C05 MFA selon le
plan ; aucune route sensible utilisable sans ses preuves. 5D exclu, PR #7 reste en brouillon.

### C02 — comptes et vérification email, 2026-10-29

Instruction utilisateur « enchaine » après livraison de C01. Reprise GitHub : PR #7 OPEN/brouillon,
branche/base/tête work/step-5c-portal-account-lobby / 63bb7d1c902e9c0fbae3497d4a36c107a80eb611 /
79500f65728ef14a302b8e400f3f43e05792517f, arbre propre et branche synchronisée après fetch.
CI C01 push 40935556492 et PR 40935563025 relues success, cinq jobs chacune. Pas d’agent délégué.

Livré : [C02](docs/03-technical/portal-registration.md), comptes UUID stables/credentials Argon2id,
inscription et vérification initiale 24 h unique, renvoi invalidant l’ancienne génération. Mot de
passe requis à la confirmation/au renvoi contre la préinscription par un tiers. Réponses non
énumérables, pas d’auto-login. Contrôle Pwned Passwords par préfixe HTTPS/padding, panne refusée 503.
Migration Accounts p0001 additive (six tables) ; création credential/preuve/outbox/audit atomique,
quota PostgreSQL distinct/concurrent, erreurs sans entrée privée, Origin/JSON stricts et corps borné.
Outbox Fernet, clé privée persistante Docker hors Git, retry sans extension de validité, payload
effacé après SMTP/annulation/expiration. Worker dédié + récepteur Mailpit isolé sans relais externe.
UI du récepteur via local-edge sur loopback 8025 ; SMTP reste réseau interne sans port publié.
Première tentative de publication directe du port Mailpit sur réseau interne inaccessible localement ;
corrigée par ce proxy, puis vérifiée réellement. Volumes et données Game conservés.
Formulaires Portal inscription/renvoi/confirmation, token de fragment retiré immédiatement de l’URL,
secrets uniquement en mémoire, mobile/clavier. Aucune connexion/session/MFA/membership/handoff,
fixture runtime, compte créé dans la base conservée ou API Colony. C03 est la suite ; 5D exclu.

Choix techniques sous délégation 5B, sources primaires dans C02. Argon2id 64 MiB/3 passes/p1 : cinq
calculs hash+verify successifs, médiane locale 160 ms dans l’image Python 3.12 (pas une mesure de
charge production). Appel réel Pwned Passwords avec mot de passe jetable généré : réponse reçue,
non compromis, aucune valeur privée imprimée. Aucun fournisseur email de production sélectionné.

Validations locales exécutées :

- Backend Portal : Ruff réussi et **36 tests réussis, aucun ignoré**, dont intégrations sur
  echosphere_c02_test dédiée : upgrade/check/roundtrip, refus de downgrade peuplé, atomicité,
  inscriptions/confirmations/renvois/quota concurrents, expiration exacte, SMTP TCP réel en panne
  puis reprise, deux workers et effacement des payloads. Base de test supprimée après recette.
  Passage initial sans opt-in : 16 réussis/17 ignorés avant les deux derniers tests ajoutés,
  distinct de la suite complète. Warning Starlette/httpx connu, sans échec.
- Frontend Portal : npm ci, ESLint, **8 tests** et build réussis. Chromium jetable Node 22/Debian :
  **7 scénarios réussis**, quatre largeurs clavier/retry, same-site natif, formulaires inscription/
  renvoi/confirmation 320 et 1440, fragment retiré et absence de stockage navigateur ; captures
  320/1440 inspectées. API UI interceptée ; intégrations API/PostgreSQL/SMTP testées séparément.
- Compose config/build/up --wait réussis ; Game et Accounts sans dérive Alembic ; deux smokes
  réellement passés, TLS strict/noms/routage/CORS et pannes indépendantes avec reprise.
  Aucun downgrade de base conservée, suppression de volume, modification hosts ou magasin CA.
- Documentation : 67 documents requis/liens valides, diff sans whitespace ; tables Q01–Q56 et
  sections de décisions 5B conservées, seulement statuts d’implémentation actualisés. Aucun code,
  dépendance ou migration backend/frontend/game_data Game modifié. Secrets et artefacts exclus.

Échecs intermédiaires corrigés : import bootstrap TypeScript manquant ; tri/format Ruff ; parsing
Compose après insertion incorrecte ; premier pytest lancé sans installation de package dans une
image Python brute (relancé via python -m pytest). Aucun de ces passages n’est présenté comme réussi.
Première tête C02 d965ca9 : CI push 40941610709 et PR 40941616489 observées success, cinq jobs chacune
et journaux relus (101/11/5 Game, 36/8/7 Portal, deux smokes). Le journal a révélé une tentative
de contrôle de version Mailpit, bloquée par son réseau isolé : contrôle désactivé explicitement.
CI de cette correction de configuration à observer après push ; workflow configuré ne vaut pas résultat exécuté.
Résultat effectif/SHA publiés dans PR #7 après observation, sans boucle de commits de checkpoint.

Limites : SMTP au moins une fois, doublon possible après acceptation avant commit ; pas de remise
publique démontrée. Dépendance de contrôle de mots de passe externe, refus temporaire si indisponible.
Procédures de clés/production et fournisseur Q49 futurs ; support Q48 et modes Q55 inchangés.
Pas de recette navigateur hôte HTTPS, Windows/tactile/lecteur d’écran, charge ou DDoS attestée.
WSL2/Docker fonctionnels pour ces commandes ; outils Python/Node exécutés en conteneurs jetables.

### C01 — socle Portal séparé, 2026-10-29

Instruction utilisateur « alors go » après présentation du plan et confirmation qu’aucun arbitrage
ne bloque C01. Reprise : PR #7 OPEN/brouillon, tête/base 8122cf77d3fb00a8cd5d4c0fa332f42d9d1a2253 /
63bb7d1c902e9c0fbae3497d4a36c107a80eb611 ; fetch, branche synchronisée/propre. CI push 40930143792
et PR 40930208556 observées success. Aucun agent délégué ni travail concurrent détecté.

Livré sur work/step-5c-portal-account-lobby, pas sur master : portal/backend (FastAPI, config PORTAL_*,
engine/pool/metadata indépendants, sondes sans détails privés), Accounts PostgreSQL/rôle/secret/volume/
réseau propres, migration p0000_portal_baseline initialisant uniquement portal_alembic_version.
portal/frontend : écran de préparation responsive, readiness propre au Portal et retry explicite.
Compose garde les cinq services Game et ajoute portal-postgres/migrate/backend/frontend/local-edge.
Caddy : deux origines HTTPS locales, CA dans volumes Docker, admin et installation de confiance hôte
désactivées. Aucun compte, User, session, Argon2id, MFA, outbox, mTLS S2S ou API Colony ajouté.
Aucun changement game_data/migrations/services métier ou lockfile Game ; contrats et Qxx inchangés.

Tests locaux réellement exécutés dans les versions Docker prévues, sans Python/Node installés hôte :

- Backend Portal : Ruff portal_app/migrations/tests et scripts réussi ; premier pytest sans opt-in
  8 réussis/1 intégration ignorée ; passage complet 9 réussis/aucun ignoré sur base dédiée
  echosphere_c01_<identifiant>_test créée puis supprimée, aucun downgrade de la base conservée.
  Upgrade répété/check/downgrade/base/upgrade et timezone UTC vérifiés. Un warning Starlette/httpx.
- Frontend Portal : npm ci, ESLint, 4 tests et build réussis. Lock autonome, Vitest 4.1.12/Vite 7.3.7 ;
  npm audit initial 0 vulnérabilité. Génération du lock avec npm 12 après échec interne npm 10
  « edgesOut » ; consommation ultérieure par npm ci de Node 22 réussie, aucun outil installé hôte.
- Chromium Debian jetable : 5 scénarios réussis, dont 320/390/768/1440 clavier/focus/retry et absence de
  débordement et classement same-site des hôtes sur serveur local réel. Les hôtes définitifs
  portal.echosphere.localhost et game.echosphere.localhost ont un parent commun, conforme à 5B.
  Captures 320/1440 inspectées. Sondes interceptées pour les tests UI ; pas de recette
  graphique Windows, tactile ou lecteur d’écran. Captures hors Git.
- docker compose config --quiet et up --build --wait réussis ; bases/APIs/frontends healthy,
  worker Game running et migrations Game/Portal Exited(0). Caddy observé v2.11.7.
- smoke_portal_compose.py réussi : TLS strict avec CA publique en mémoire/noms vérifiés, deux
  origines/routage et CORS refusé, historiques séparés, panne Accounts sans panne Game puis inverse,
  reprises. smoke_compose.py Game réussi. Alembic check Portal et Game sans dérive, Game reste 0004.
  Volumes de données conservés, aucune CA installée dans Windows/WSL2.

CI étendue : jobs portal-backend/portal-frontend et smoke HTTPS ; jobs Game préservés. Documentation
opérationnelle [portal-foundation](docs/03-technical/portal-foundation.md), références et état courant
actualisés. Le code CI est une recette, pas encore une CI passée sur la nouvelle tête à ce checkpoint.
Checks finaux exécutés : 66 documents/chemins/liens valides, git diff --check sans erreur ; registre
Q01–Q56 et identity-contracts intégralement identiques à 8122cf7. Diff/périmètre/confidentialité relus,
aucun backend/frontend/game_data Game modifié, aucune clé/certificat/artefact privé staged.
Après publication, observer SHA/CI
propres et consigner leurs résultats exacts dans PR #7, sans nouvelle boucle de commits de checkpoint.

Limites : socle local, aucune auth implémentée ; UI Chromium HTTP et smoke TLS réel vérifiés séparément.
Pas de recette HTTPS navigateur hôte ni résilience de commandes Game futures, charge ou isolation
CPU/RAM. Dépréciations dev ESLint/whatwg-encoding et Starlette conservées sans échec ; avis Game
historiques inchangés. C01 ne ferme aucune Qxx supplémentaire. Prochain ticket : C02 comptes,
Argon2id/vérification email et livraison durable, selon 5B, sans choix de fournisseur production imposé.
5D non commencé ; PR #7 à actualiser et laisser non fusionnée.

### Synchronisation après fusion de PR #6 — 2026-10-29

GitHub réel : PR #6 était encore OPEN/brouillon sur 4b17c16494bc9949d3387ccbfb13a2359e74f59e,
malgré la formulation initiale de la demande ; CI push 40924593354 et PR 40924600793 completed/success.
Sur instruction explicite « Merge la PR6 », passage prêt pour revue puis fusion normale, tête attendue
contrôlée. Merge réel : **63bb7d1c902e9c0fbae3497d4a36c107a80eb611**, parents 8214e0b et 4b17c16.
Aucune branche supprimée. Fetch GitHub, bascule master, fast-forward vers origin/master et arbre propre
vérifiés. Nouvelle branche **work/step-5c-portal-account-lobby** créée directement depuis ce merge ;
branche 5B non réutilisée. CI master [40929141873](https://github.com/ThomasPerez91/Echosphere/actions/runs/40929141873)
observée completed/success sur le merge avant publication du checkpoint.

Premier travail de cette branche : références courantes README/context/progress, index docs,
identity-contracts, Qxx, roadmap/backlog, passation/lacunes/décisions, architecture/API/sécurité,
ADR 0008, AGENTS et DoD synchronisées avec l’intégration réelle. Les checkpoints antérieurs ci-dessous
restent des relevés historiques, leurs formulations de revue/brouillon ne décrivent pas le lot courant.
Q40–Q47, Q50–Q54 et Q56 clos pour le cadrage 5B ; reports Q48/Q49/Q55 inchangés. Aucune décision
5B modifiée, aucun compte/auth/Portal ajouté. Diff limité à la synchronisation documentaire.

Validations locales exécutées : `python3 scripts/check_docs.py` réussi, 64 documents/chemins/liens ;
`git diff --check` sans erreur. Q01–Q56 présentes exactement une fois ; toutes les lignes de décision
Qxx strictement identiques au merge. Sections métier 1–8, matrice d’acceptation 10 et sources 11 de
identity-contracts identiques au merge ; seules les mentions de statut/intégration changent.
Diff des 18 fichiers Markdown relu : synchronisation documentaire uniquement, sans décision nouvelle.
Tests backend/frontend, migrations et Compose non relancés pour ce diff documentaire ; aucune
implémentation 5C ni preuve d’authentification testée à ce stade.

Premier checkpoint publié : **1c2749773c3bb3cf7eedf9a0f4013b9ce7c8f98a**, tête distante relue et
arbre propre. CI [40929423582](https://github.com/ThomasPerez91/Echosphere/actions/runs/40929423582)
observée completed/success sur cette tête, jobs backend/frontend/compose-smoke réussis.

### Cadrage 5C présenté avant code substantiel — 2026-10-29

Après publication du premier checkpoint, analyse du dépôt réel (configuration/persistance Game,
migrations, services Colony, shell/Vite, Compose et dépendances). Nouveau
[plan 5C](docs/05-project/step-5c-plan.md) : sous-tickets C00–C09, tables/migrations Accounts séparées,
applications Portal backend/frontend, minimum d’accès Game nécessaire au handoff, frontière 5D et
reports. Plan technique et périmètre proposés pour présentation, pas décision produit supplémentaire.
C01 est le prochain incrément de code ; aucune implémentation substantielle dans ce checkpoint.

Limite de périmètre explicitée : le domaine 5A ne crée pas une partie complète. Lobby fondé sur
participations réelles, sans fixture/public join ; un bouton créant une partie jouable nécessiterait
cadrage de démarrage dédié avant implémentation, sans inventer les questions de modes/progression.
Reports Q48/Q49/Q55 inchangés. Les détails techniques restent délégués, pas de questionnaire par
paramètre. Cadrage documenté séparément du premier commit de synchronisation demandé.

Validation locale du cadrage exécutée : `python3 scripts/check_docs.py` réussi (65 documents et
liens), `git diff --check` sans erreur ; Q01–Q56 et toutes leurs lignes strictement inchangées depuis
le merge 5B, diff Markdown uniquement. Checks fonctionnels non relancés localement pour ces documents. Après publication, observer la CI de sa tête et consigner les résultats dans
la PR du lot. Prochaine action : présentation du plan à l’utilisateur avant code substantiel ; aucun
5D ni nouveau merge autorisé.

## Historique du lot 5B — contrats identité / Portal-Game consolidés

**Statut : 5B documentaire terminé, prêt pour revue finale de PR #6 sous réserve de la CI publiée.**
Contrats validés et non implémentés ; aucun début de 5C et aucun merge autorisé.

### Consolidation finale du bloc 5B — 2026-10-29

Objectif : intégrer la validation utilisateur de l’ensemble des quatorze points, avec trois corrections,
puis revue de cohérence de toute PR #6. Provenance : arbitrage utilisateur explicite, synthétisé dans
le canonique sans conversation brute. Environnement Codex local/WSL2, aucune délégation à des agents.

Reprise vérifiée : branche work/step-5b-identity-contracts propre et synchronisée depuis
10499b6f60f241a5fecc2cfd56c19ff7da548708 ; master/origin master inchangées sur
8214e0bd30a00bf0336264a428e6975d307350ba. PR #6 OPEN/brouillon vers master, non fusionnée ;
CI de départ push 40920709168 et PR 40920717330 completed/success sur 10499b6, trois jobs verts.
Fetch initial refusé par sandbox (.git en lecture seule), puis réussi avec autorisation ; aucun défaut
Git/WSL2 démontré. Aucun travail concurrent ni divergence distante détecté.

Résultat : canonique identity-contracts réécrit pour séparer décisions closes, détails techniques
explicitement délégués et reports. Registre Q40–Q56 consolidé sans renumérotation ni fermeture des
questions gameplay Q01–Q39 ; Q16 actualisée uniquement pour le cadrage identité/autorisation couvert.
Corrections prioritaires : pas de global systématique pour ajout MFA/régénération volontaire des
secours avec step-up existant ; caps 10 appareils/10 univers actifs configurables sans limite de
memberships ; APIs même origine et CORS credentials refusé par défaut, exceptions explicites minimales.
MFA/step-up/secours, compte/email, appareil, handoff/clés, S2S, synchronisation/révocation, permissions,
anti-abus et audit désormais cadrés. Aucun arbitrage produit supplémentaire inventé.

Décisions fermées dans le périmètre 5B : Q40–Q47, Q50–Q54 et Q56. Q48 : contrat MVP clos mais procédures
support renforcé joueur/privilégié différées, aucun déblocage sans approbation. Q49 : flux clos mais
fournisseur/domaines/configuration de production différés. Q55 : règles des modes futurs explicitement
différées ; Q19–Q29/Q21 préservées. Détails techniques délégués à 5C/5D avant code dépendant ; aucun
nouveau questionnaire par bibliothèque/paramètre, aucun bypass ou service payant implicite.

Fichiers : 22 Markdown de consolidation : identity-contracts, registre Qxx, ADR 0008/index, sécurité,
API, modèle, architecture, roadmap/backlog, UX, DoD, index docs/décisions/provenance, README/AGENTS/
context/progress et passation/lacunes. Revue de PR entière
contre master, pas seulement du dernier diff. Anciennes mentions ouvertes/proposées remplacées
pour décisions validées ; checkpoints historiques ci-dessous conservés et identifiés comme tels.
Aucun code métier, test, migration, game_data, dépendance ou Compose modifié par cette consolidation.
Le script check_docs.py déjà changé au début de PR #6 reste limité à son document requis ajouté.

Validation locale exécutée : `python3 scripts/check_docs.py` réussi (64 fichiers, chemins requis et
liens locaux), `git diff --check` sans erreur. Vérification ponctuelle du registre : Q01–Q56 exactement
une fois ; lignes Q01–Q39 identiques à la tête de reprise sauf cadrage Q16 ; toutes Q40–Q56 séparent
clôture/délégation/report. Consolidation Markdown seulement ; PR complète = 22 Markdown + unique ajout
REQUIRED identity-contracts de check_docs.py. Diff complet contre master relu, confidentialité et
renvois/statuts obsolètes contrôlés ; aucune revue ou discussion inline existante sur GitHub.
Après commit/push, relire SHA distant et observer sa propre CI ; résultats exacts à consigner dans
la description de PR #6 après exécution, sans nouvelle boucle de commits de checkpoint.
Aucun test fonctionnel Portal/MFA/GameSession exécuté,
ces mécanismes étant absents. Suites fonctionnelles locales et Docker non relancés pour le diff
documentaire ; les résultats de reprise antérieure restent historiques et distincts.

Prochaine action : revue finale de PR #6 ; fusion uniquement sur instruction. 5C n’a pas commencé.
Après intégration et lot distinct autorisé : cadrer l’incrément compte/lobby 5C, appliquer les détails
techniques délégués et prérequis de son périmètre ; 5D pour l’accès Colony interactif et résilience.

## Historique des checkpoints 5B — superseded pour les statuts ouverts

Les sections suivantes conservent l’état et les preuves à leur date. Les formulations « prochain
arbitrage », « proposition » ou « question ouverte » décrivent ces checkpoints, pas le contrat final
ci-dessus. Les décisions actuelles et reports font foi dans identity-contracts et le registre Qxx.

### Facteurs et récupération MFA Q48 — 2026-10-29

Source : arbitrage explicite utilisateur pour PR #6. Non implémenté : TOTP/WebAuthn MVP, joueur
choisit l’un ou les deux ; un seul secret TOTP actif, remplacement sans accumulation ; jusqu’à
5 credentials WebAuthn nommables. Privilèges plateforme : WebAuthn obligatoire et preuve WebAuthn
sur opérations sensibles, TOTP complémentaire seulement ; prévoir deux WebAuthn en production.
Secours : autre facteur enregistré et codes uniques, générés à activation, régénération invalidant
anciens ; robustes, vérification sans secret exploitable stocké en clair, jamais journalisés.
Perte totale : support renforcé à définir, aucun bypass email/mot de passe. Secours privilégié :
état de récupération sans droits admin, WebAuthn réenregistré + procédure privilégiée requis.
Changements audités et step-up via facteur disponible, identité/gameplay conservés. Q48 reste
partiellement ouverte : crypto/RP, stockage TOTP, format/nombre des codes, support final, effets
sur sessions et step-up détaillé. Aucune autre Q fermée ni mécanisme implémenté.

Reprise : fetch, work/step-5b-identity-contracts propre/synchronisée sur
830f3e41e04daa2a8723707bd9f79555438b1c1f ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête vérifiée : push 40918608285 et PR 40918613929, backend/frontend/compose-smoke verts.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, décisions, références API/ADR/index/
passation/lacunes. Critères futurs : limites en concurrence, secours uniques/régénération, refus
privilégié et audit. Aucun comportement futur testé. Checks locaux : docs/liens, diff, Markdown,
Q01–Q56 uniques et seule ligne Q48 modifiée. Suites backend/frontend/Compose et Ruff non relancées
localement ; observer nouvelle CI après publication et consigner résultats dans PR.
Prochain arbitrage : effets des changements/récupérations MFA sur sessions et fraîcheur/portée
step-up ; support final reste à spécifier sans bypass. Aucun merge ni démarrage de 5C.

### Périmètre MFA Q48 — 2026-10-29 (checkpoint antérieur aux facteurs)

Source : arbitrage explicite utilisateur pour PR #6. Q48 partiellement close, non implémentée :
MFA facultative joueurs MVP via paramètres, exigence normale après activation ; obligatoire avant
fonctions privilégiées plateforme/admin/opération, sans exemption interne ni assimilation aux
rôles Empire. Step-up des comptes équipés avant email, désactivation/remplacement MFA et moyens de
récupération ; logout tous appareils seulement éventuel. Sans MFA, Q40/Q49 inchangées. Identité,
memberships/empires/univers/gameplay conservés. Facteur/nombre, secrets, récupération/codes,
remplacement/réinitialisation et mécanismes précis step-up restent ouverts, aucune autre Q fermée.

Reprise : fetch, branche work/step-5b-identity-contracts propre/synchronisée sur
ce6353a8a4870103bd6d0f7fc696279c364b5d12 ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête vérifiée : push 40917882587 et PR 40917891299, backend/frontend/compose-smoke verts.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, décisions et références
API/ADR 0008/index/passation/lacunes. Critères futurs complétés pour périmètre MFA, refus privilégié
et step-up ; aucun comportement futur exécuté/testé. Checks locaux : docs/liens, diff, périmètre
Markdown et Q01–Q56 uniques, seule ligne Q48 modifiée. Suites backend/frontend/Compose et Ruff
non relancées localement pour ce diff documentaire ; observer CI du nouveau commit après push,
résultats consignés dans PR. Prochain arbitrage à ce checkpoint : facteurs/récupération,
depuis partiellement validés ci-dessus.
Aucune implémentation, console admin ou MFA anticipée, aucun merge PR #6 ni passage à 5C.

### Complément email : échéance, remplacement et sessions — 2026-10-29 (checkpoint antérieur à Q48)

Source : arbitrage explicite utilisateur Q40/Q49 pour PR #6. Non implémenté : demande active unique
par compte, maximum 1 h depuis création, échéance commune aux deux confirmations sans glissement.
Nouvelle demande invalide ancienne/liens/confirmations ; deux nouvelles preuves requises sans mélange.
Succès après toutes validations : adresse active, global_user_id et gameplay conservés ; toutes
sessions Portal/Game révoquées, courante incluse, tous appareils/univers ; connexion normale avec
nouvelle adresse. Notifications aux deux adresses sans credential/token sensible. Game injoignable :
intention persistée/rejouée jusqu’à acquittement, aucune instantanéité prétendue ni reset des 8 h.
Q40/Q49 partiellement ouvertes, mécanismes/fournisseur non choisis ; Q48/Q50/Q53/Q54 non fermées.

Reprise : fetch, work/step-5b-identity-contracts propre/synchronisée sur
a4cb854307cb022bfd907f59ea57c8709cca4835 ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête observée verte : push 40897245953 et PR 40897261938, backend/frontend/compose-smoke.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, décisions et références
API/ADR 0008/index/passation/lacunes. Critères futurs complétés pour échéance commune, remplacement,
non-mélange/concurrence, révocation globale/courante et panne sans extension ; aucun test de ces
mécanismes futurs exécuté. Checks locaux : docs/liens, diff, périmètre Markdown et Q01–Q56 uniques ;
seules lignes Q40/Q49 modifiées. Suites backend/frontend/Compose et Ruff non relancées localement.
Vérifier la CI propre du nouveau commit après publication ; résultats consignés dans PR après observation.
Prochain arbitrage à ce checkpoint : périmètre Q48, désormais partiellement validé ci-dessus ;
facteur et récupération restent ouverts.
Aucun merge de PR #6, implémentation ou démarrage de 5C.

### Changement d’email Q40/Q49 — 2026-10-29 (checkpoint avant complément)

Source : arbitrage explicite utilisateur pour PR #6, synthèse unique des deux réponses identiques.
Non implémenté : session Portal valide, mot de passe actuel ressaisi, confirmations ancienne et
nouvelle adresses ; nouvelle pending jusqu’aux deux confirmations et validation effective. Succès :
notifications aux deux adresses, nouvelle authentification, global_user_id et états de jeu conservés.
Ancienne adresse inaccessible : blocage sans récupération indépendante déjà établie et disponible,
pas de bypass mot de passe seul. Variante MFA conditionnelle à Q48 validée/implémentée, politique
exacte ouverte ; aucun MFA/code de secours/support inventé. Durées/cycle des confirmations et
portée exacte d’invalidation des sessions toujours ouvertes ; aucune autre Qxx fermée par implication.

Reprise : fetch, branche work/step-5b-identity-contracts propre/synchronisée sur
38a2b6ac4f79fb66dc165a843c95c8761eb83b17, PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête vérifiée : push 40896112238 et PR 40896122379, backend/frontend/compose-smoke verts.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, index des décisions et références
API/ADR 0008/index/passation/lacunes. Critères futurs : pas de bascule avec une seule confirmation,
refus sans preuve indépendante, notifications/réauthentification et identité conservée.
Checks locaux : documentation/liens, diff, Q01–Q56 uniques, seules lignes Q40/Q49 modifiées ;
Markdown uniquement. Aucune suite backend/frontend/Compose ou Ruff relancée localement ; aucun
comportement futur testé. Après publication vérifier SHA et CI propres, résultats consignés dans PR.
Prochain arbitrage à ce checkpoint : durées/cycle et sessions, désormais validés dans le complément
ci-dessus ; Q48 reste ouverte. Aucun merge de PR #6, démarrage de 5C ou implémentation.

### Récupération Q40/Q49 — 2026-10-29 (checkpoint antérieur au changement d’email)

Source : arbitrage explicite utilisateur pour PR #6, synthétisé sans transcript. Décision validée,
non implémentée : jeton 30 min maximum depuis émission, unique, expiration serveur ; réémission
invalide tous les anciens liens. Reset réussi : invalidation de toutes les PortalSessions et jetons
de récupération, demande de révocation de toutes les GameSessions tous appareils/univers ; nouvelle
connexion normale sans auto-login, notification email sans mot de passe. Réponse de demande non
énumérable ; memberships/empires/états conservés. Si Game injoignable, révocation persistée/rejouée
jusqu’à acquittement, aucune instantanéité promise, valid_until/8 h jamais relancés au reset.
Seules ces parties Q40/Q49 sont closes ; Q48/Q50/Q53/Q54 restent ouvertes.

Reprise vérifiée : fetch, arbre propre, branche work/step-5b-identity-contracts synchronisée sur
cbf088c5c22974ce0c548fe4faeb2e1b9eec5533 ; PR #6 OPEN/brouillon, master 8214e0b inchangée.
CI de cette tête observée verte : push 40892359042 et PR 40892370513, backend/frontend/compose-smoke.
Fichiers : contrats, Qxx, context/progress, sécurité, roadmap, index des décisions et références
passation/index/API/ADR 0008. Critères futurs ajoutés : frontière 30 min, réémission/consommation
concurrentes, reset global et panne sans extension. Aucun mécanisme futur testé ou implémenté.
Checks locaux : documentation/liens, diff et périmètre Markdown, Q01–Q56 sans trou/doublon et seules
lignes Q40/Q49 modifiées. Suites fonctionnelles backend/frontend/Compose et Ruff non relancées
localement pour ce diff documentaire. Relire SHA distant/CI de la nouvelle tête après push ;
les résultats du commit précédent ne valent pas ceux du nouveau. Résultats publiés dans PR après observation.
Prochain arbitrage à ce checkpoint : changement d’email, depuis partiellement validé ci-dessus ;
durées/cycle et portée des sessions restent ouverts, puis MFA Q48. Aucun merge ni démarrage de 5C.

### Déconnexions Q45 — 2026-10-29 (checkpoint antérieur à la récupération)

Source : validation explicite utilisateur pour PR #6. Comportement produit Q45 clos, non implémenté :
retour lobby sans logout ; déconnexion Game d’une seule session ; compte sur appareil courant
(PortalSession courante + toutes ses GameSessions du compte) ; tous appareils comme action distincte.
Autres appareils préservés lors du logout normal ; memberships/empires/états/progression/actions
acceptées conservés. Révocation globale persistée/rejouée jusqu’à acquittement, état UI en attente
si service injoignable, borne valid_until/8 h inchangée. Aucune autre Qxx close par implication.
Regroupement appareil sous Q41/Q43 ; protocoles sous Q53/Q54 et tickets en vol sous Q42/Q56 ouverts.
Un epoch d’accès commun ne peut implémenter le logout d’un seul appareil : limite explicitée,
sans adopter un nouveau modèle de stockage. Matrice d’acceptation future complétée, aucun test
fonctionnel de ces mécanismes exécuté.

Reprise : fetch, branche work/step-5b-identity-contracts propre et synchronisée sur d879f7e5002d91342f08819ff2bad69ee83ad7d0 ;
PR #6 OPEN/brouillon, base master 8214e0b inchangée. CI de cette tête observée verte :
push 40879933579 et PR 40879939979, backend/frontend/compose-smoke réussis.
Fichiers : contrats, registre Qxx, context/progress, sécurité, API/architecture, ADR 0008, roadmap,
README/index/passation/décisions/lacunes. Résumés périmés corrigés ; Markdown uniquement.
Checks locaux : check documentaire, diff, Q01–Q56 et comparaison des statuts ; seules les décisions
Q45 changent, aucune autre fermeture. Suites fonctionnelles backend/frontend/Compose et Ruff
non relancées localement pour ce diff documentaire ; CI de la nouvelle tête à observer après push.
Prochain arbitrage à ce checkpoint : récupération Q40/Q49, depuis validée dans le complément
ci-dessus ; changement d’email et MFA restent ouverts.
Aucun merge de PR #6, passage à 5C ou implémentation ; résultats CI publiés dans la PR après observation.

### Complément activité Q41/Q43 — 2026-10-29 (checkpoint antérieur à Q45)

Source : arbitrage explicite utilisateur, synthétisé dans identity-contracts et Qxx. Seules les
interactions explicites classées côté serveur réinitialisent l’inactivité ; toutes les catégories
automatiques citées dans le contrat sont exclues. Heure serveur, aucun timestamp client autoritaire ;
aucune modification des maxima absolus ou de valid_until. Q41/Q43 restent partiellement ouvertes,
Q45–Q56 inchangées. Aucune implémentation ni fusion autorisée.

Reprise : fetch effectué, arbre propre, tête locale/distante 5dbd9184509ca6323279365944dea9567207cd17,
PR #6 OPEN/brouillon, base master 8214e0b inchangée. CI de cette tête vérifiée : push 40878132584
et PR 40878144213, backend/frontend/compose-smoke réussis.
Fichiers : identity-contracts, open-questions, context, progress, sécurité, roadmap et index des décisions.
Scénarios futurs complétés : catégories automatiques sans effet, interactions explicites, timestamp
client falsifié, échéance contrôlée avant réinitialisation et maxima inchangés. Aucun test de ces
mécanismes futurs exécuté. Vérifications locales : check documentaire, diff et périmètre Markdown ;
aucune suite fonctionnelle backend/frontend/Compose ni Ruff relancée pour ce complément documentaire.
Après publication, relire SHA distant et CI effective de cette nouvelle tête ; les résultats de
5dbd918 ci-dessus ne prouvent pas la CI du présent commit.
Prochaine décision à ce checkpoint : Q45, depuis arbitrée dans le complément ci-dessus. 5C/5D restent hors de ce lot documentaire.

### Arbitrages utilisateur intégrés — 2026-10-29, checkpoint antérieur à Q45

Source : validation explicite utilisateur pour poursuivre PR #6, synthétisée dans le canonique
identity-contracts.md et le registre Qxx, sans transcript brut. Aucune validation implicite
du reste de la proposition et aucune autorisation de fusion.

- Q40, parties closes : MVP email/mot de passe ; email vérifié avant premier handoff ; récupération
  courte/unique ; Argon2id via bibliothèque maintenue ; global_user_id indépendant de l’email et de
  la méthode. Google/OIDC supplémentaire futur facultatif. Bibliothèque/paramètres et récupération
  détaillée restent ouverts ; fournisseur email et MFA dans leurs Q49/Q48 restent à arbitrer.
- Q41, partie close : Portal 7 jours absolus et **72 heures** d’inactivité, remplaçant la proposition
  initiale de 24 h. Activité sans prolongation du maximum absolu ; cookies/stockage/rotation ouverts.
- Q42, parties closes : ticket de handoff 60 secondes et usage unique. Format, crypto, liaison
  navigateur et mécanismes anti-rejeu toujours ouverts ; aucune durée de récupération déduite.
- Q43, parties closes : Game 8 h absolues/2 h d’inactivité, GameAccess pouvant expirer plus tôt ;
  absolu non prolongé par activité. Stockage et limites simultanées ouverts ; activité arbitrée dans le complément ci-dessus.
- Q44, parties closes : droits au plus 8 h depuis dernière confirmation Portal, non glissants et
  sans reset en panne ; révocation/suspension reçue immédiate ; nouvelles commandes refusées à
  valid_until, univers/workers continuant. Renouvellement avec Portal disponible et nouvelle
  confirmation/handoff valide ; aucune autonomie illimitée. Protocoles/synchronisation non choisis.

Q40–Q44 restent partiellement ouvertes ; Q16/Q21/Q45–Q56 ne sont pas fermées. Les comptes,
sessions et tickets ne sont toujours pas implémentés. La validation de la fenêtre ne vaut pas
acceptation de mTLS, JWT, stockage opaque, cookies, epoch, outbox ou politique de logout.

Poursuite documentaire : expressions des échéances et exemples de confirmation retardée/panne
ajoutés, scénarios futurs de frontière et compte MVP précisés. Aucun test artificiel ou code ajouté.
À ce checkpoint antérieur, l’activité Q41/Q43 restait à arbitrer ; le complément ci-dessus
consigne désormais sa validation explicite.
Les autres questions techniques restent listées pour la suite, pas repoussées implicitement à 5C.

Fichiers de cette continuation : identity-contracts, open-questions, context/progress et références
README/docs/index/architecture/API/sécurité/ADR 0008/roadmap/passation/known-gaps pour éviter des
mentions périmées « durées/login encore proposés ». Diff Markdown uniquement, aucun changement de
code, test, dépendance, migration, ruleset, Compose ou script.

Vérification initiale de cette continuation : arbre propre, branche locale et distante à
2d1efdabac4a5e6396b515f63fc02684869c8ac9 après fetch, PR #6 OPEN/draft sur la même tête vers
master 8214e0b ; seule PR ouverte listée. CI de cette tête relue :
[40873616329](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873616329) et
[40873623209](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873623209), tous les jobs
backend/frontend/compose-smoke réussis. Aucun merge, changement de branche ou travail concurrent.
Checks de cette continuation exécutés : 64 documents/liens valides, git diff --check sans erreur,
Q01–Q56 sans trou/doublon ; comparaison avec HEAD confirmant que seuls les libellés Q40–Q44
changent dans les tableaux du registre et qu’ils restent explicitement partiellement clos.
Relecture des limites/formules/exemples, de la séparation validé/proposé et du diff de confidentialité.
Périmètre Markdown uniquement vérifié. Aucune suite backend/frontend/Compose ou Ruff relancée
localement pour ce changement documentaire ; aucun nouveau mécanisme de session testé.
Publication effectuée sur la même PR #6 brouillon, restée OPEN/non fusionnée :
56e43a9bf5a9100e22ad3c4363095a45b0452db9, SHA distant relu ; master reste 8214e0b.
CI de ces arbitrages : [push 40877809734](https://github.com/ThomasPerez91/Echosphere/actions/runs/40877809734)
et [PR 40877818343](https://github.com/ThomasPerez91/Echosphere/actions/runs/40877818343),
backend/frontend/compose-smoke tous réussis sur cette tête. Description de PR actualisée avec
les décisions partielles et les mécanismes non validés. Ce checkpoint consigne ces résultats
après leur observation ; vérifier également sa propre CI publiée. Aucune CI présentée comme
preuve d’un mécanisme Portal/Game futur, aucun merge ni passage à 5C.

### Base et périmètre initiaux (historique de préparation)

GitHub relu : PR #5 MERGED, tête acde9d358bfe724be61198cd60fd1e72c6e38459, base master,
merge 8214e0bd30a00bf0336264a428e6975d307350ba. Fetch effectué ; master locale propre et identique
à origin/master. Aucune PR ouverte au contrôle, aucune develop. CI master
[40765430216](https://github.com/ThomasPerez91/Echosphere/actions/runs/40765430216) completed/success
sur ce merge, jobs backend/frontend/compose-smoke verts. Dernière livraison consignée : passation
Work par #5 ; cette recette locale lui succède sans attribuer un nom non attesté à son auteur.

Branche : work/step-5b-identity-contracts, créée depuis cette master sans empilement.
Premier commit publié : e3d2f8ec1dcb647a147dc9d885be4f06f9f46802,
[PR #6](https://github.com/ThomasPerez91/Echosphere/pull/6) brouillon OPEN vers master.
Le présent checkpoint documentaire suit ce commit ; consulter aussi sa propre CI publiée.
Aucune fusion, suppression de branche, release ou déploiement autorisé.

Fichiers : nouveau docs/03-technical/identity-contracts.md ; références API/sécurité/modèle/architecture,
index docs/ADR/décisions, README/passation, roadmap/questions/known-gaps, context/progress et liste
des documents requis de scripts/check_docs.py. Aucun code métier, game_data, migration, dépendance,
Compose, composant UI ou test fonctionnel modifié.

### Préparation initiale et statut des propositions (avant les arbitrages ci-dessus)

Contrats proposés : autorités Portal/Game, participation/accès local versionné/bindings d’Empire,
interface interne idempotente avec révisions/outbox/réconciliation, handoff lié au navigateur,
consommation atomique, session opaque et contrôles locaux, concurrence avec révocation, logout,
rotation de clés, isolation et matrice de scénarios futurs. Alternatives et sources OWASP/RFC
publiques consignées. À ce premier checkpoint, aucun protocole, algorithme, fournisseur ni durée
nouveau n’était présenté comme accepté.
Relecture : distinguer la révision de livraison de l’epoch d’invalidation des sessions pour qu’un
renouvellement à droits inchangés ne déconnecte pas les sessions valides ; cookies par univers
proposés pour les onglets multi-parties, limite de sessions/cleanup restant sous Q43.

Arbitrage principal alors proposé : validité locale des droits bornée à 8 h, session Game 8 h absolues/
2 h d’inactivité, ticket 60 s ; autonomie en panne Portal jusqu’aux limites, révocation appliquée
dès livraison mais non instantanée si liaison coupée. Ces valeurs étaient des propositions à revoir,
depuis acceptées uniquement dans le périmètre décrit en tête. Q21 et les questions de modes restent ouvertes. 5C ne commence
pas automatiquement après la rédaction ; recueillir les arbitrages nécessaires et leur provenance.

### Recette de reprise locale réalisée avant création de la branche

Cette recette appartient à la mission de reprise du 2026-10-29, sur master 8214e0b inchangée ;
elle ne valide aucun mécanisme futur de 5B et n’a pas été relancée pour le diff documentaire.

- `python3 scripts/check_docs.py` : 63 documents/liens valides.
- `docker compose ps -a` : postgres/backend/frontend healthy, worker running, migrate Exited (0).
- `docker compose exec backend alembic check` : aucune dérive ; current = 0004_colony_economy head.
- `python3 scripts/smoke_compose.py` : succès, frontend/proxy/sondes et panne/reprise PostgreSQL.
- Backend dans un conteneur Python 3.12 : premier passage 42 réussis/59 ignorés sans RUN_DB_TESTS.
  Passage complet avec base dédiée echosphere_codex_20261029_test : initialement 100 réussis/1 échec
  de chemin game_data, puis 101 réussis après montage de l’arborescence complète en lecture seule.
  La base dédiée a été supprimée ensuite ; aucune suite de downgrade sur la base de jeu.
  Ruff backend/scripts passe. Avertissement Starlette/httpx déprécié observé.
- Frontend conteneur Node 22 : npm ci, lint, 11 tests et build réussis. Les empreintes des fichiers
  App, test, CSS, ColonyView, scénario E2E et package-lock de l’image concordaient avec le dépôt.
- Playwright : installation impossible dans Alpine (apt-get absent), puis 5 scénarios Chromium
  réussis dans un conteneur Debian Node 22 jetable, copie de sources montées en lecture seule.
  Largeurs 320/390/768/1440 et navigation clavier/retry. Aucun test navigateur Windows attesté.
- Chargement du ruleset dans l’image worker : v0.1. Diff et état Git propres à la fin de la recette.

Limites environnement : noyau 6.18.54.1-microsoft-standard-WSL2, Compose v5.6.1, Python hôte 3.14.4,
pas de Node/npm hôte ni backend/.venv. Les tests ont utilisé les versions Docker prévues, sans
installer les outils sur l’hôte. Les premiers accès fetch/socket Docker/localhost ont été refusés
par le bac à sable puis ont réussi avec autorisation ; aucun défaut WSL2 démontré par ces refus.
Pas de recette graphique Windows, tactile, lecteur d’écran, Safari/Firefox, charge massive ou
résilience Portal/Game réel (inexistant). Pile Compose laissée démarrée, volume de jeu conservé.

`npm audit --json` : 3 dépendances affectées (1 modérée, 2 critiques) dans la chaîne de développement
Vitest/@vitest/mocker/tinypool. Aucun correctif automatique effectué. Voir known-gaps pour les avis.

### Validation du premier checkpoint documentaire (historique)

Checks du diff 5B exécutés : 64 documents/liens valides, git diff --check sans erreur,
Q01–Q56 présentes exactement une fois dans les tableaux du registre ; périmètre Markdown et
liste REQUIRED de check_docs.py vérifié. Ruff de scripts/check_docs.py passe dans le conteneur
Python 3.12 avec dépendances de développement figées. Relecture du nouveau contrat, de ses statuts,
de ses liens et du diff de confidentialité effectuée. Aucune suite fonctionnelle relancée pour
ces changements documentaires ; les scénarios 5B sont des critères futurs non exécutés.
Branche publiée, SHA distant e3d2f8e relu, PR #6 brouillon créée et non fusionnée.
[CI push 40873175483](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873175483)
completed/success sur e3d2f8e, jobs backend/frontend/compose-smoke verts. Ces résultats ne prouvent
aucune implémentation des contrats futurs. Le présent checkpoint et les précisions de relecture
suivent cette tête ; leur CI propre reste à relire après publication, sans la présumer réussie.
Prochaine action à ce checkpoint : revue et arbitrage, désormais partiellement effectués comme
consigné en tête ; pas d’implémentation Portal/API Colony sur la seule présence du document.

---

## Lot précédent — passation documentaire Work / Codex (historique)

**Périmètre : documents uniquement**, plus liste des documents requis dans scripts/check_docs.py.
Aucun service, gameplay, migration/SQL, game_data, dépendance, Compose/Docker ou test fonctionnel changé.
Branche existante work/step-5a-colony-domain et PR #5 conservées ; pas de nouvelle branche/PR,
force push, suppression, merge, tag ou déploiement. Environnement de cette livraison : ChatGPT Work.

### État initial vérifié

PR #5 ouverte, mergeable, non fusionnée, tête 5be00da4726abd8fb38bd159deab1f1cf687df52 vers master
54f928e2348781db43b335d4dcf569aadc0db6e9. CI 40721303421 verte (backend/frontend/compose-smoke).
Dernier commit : context/progress seulement après 58e8f7c fonctionnel. Seules master et la branche #5
restent listées ; les anciennes branches work ont disparu, sans action de cette mission. Pas de develop.
Audit code/tests et limites dans [audit #5](docs/06-handoff/pr-5-audit.md).

### Travail et sources

Vision et documents existants enrichis, chiffres v0.1 préservés. 12 secteurs/2 orbitaux explicitement
limités au départ de référence ; Q39 toujours ouverte. Status implémenté/validé/provisoire/proposé/futur
séparés. Architecture actuelle réconciliée avec code, anciennes contradictions signalées superseded.

ADR 0008 créé sans renuméroter 0007 : compte global multi-parties, deux backends Portal/Game isolables,
Accounts DB/Game DB distinctes, interface interne contrôlée sans SQL Portal→Game, GameSession autonome
après ticket court/unique et gameplay direct. Décision validée **non implémentée**, protocoles non choisis.
Q16 partiellement cadrée, Q01–Q39 préservées, Q40–Q56 ouvertes. Roadmap : 5A → 5B contrats identité/
Portal-Game → 5C compte/lobby selon cadrage → 5D API Colony/UI sécurisées. Aucun Portal complet anticipé.

Dossier docs/06-handoff : README, source-map, decision-status, work-codex-handoff, known-gaps,
pr-5-audit. Procédure symétrique fetch/lecture/qualité/commit/push/SHA-CI pour Work et Codex ; reprise
locale WSL2 proposée mais jamais présentée comme testée. AGENTS devient la procédure commune.

Sources : dépôt, PR #1–5/CI/commits, contexte visible et brief de mission ; recherche contextuelle
partielle ciblée a retrouvé des extraits cohérents, pas toutes les conversations originales.
Aucun accès exhaustif au projet ChatGPT attesté. Source secondaire de fichier signalée par recherche
non lue intégralement. Pas de conversation brute, information personnelle/secret/identifiant privé
ou sujet hors Echosphere publié. Les décisions anciennes seulement retrouvées dans GitHub restent
qualifiées selon leur preuve, sans promotion des suggestions d’assistant.

### Vérifications et point de reprise

Check documentaire : 63 fichiers et liens locaux ; index ADR 0001–0008, Q01–Q56 sans trou/doublon,
recherche develop/plafond 5/12-2/backend unique et diff documentaire contre 5be00da. Ruff du script.
Les limitations techniques relevées sont consignées, non corrigées : borne secteur au service,
immutabilité de snapshot par contrat applicatif, initialiseur limité à la référence ; Q39 et UX de
cascade encore à valider. Aucun problème bloquant nouveau démontré par la lecture ciblée.

Passation publiée en deux commits :
- 14fd4db40b3a422228433af7ede9842caa61c363 — docs: consolidate product and Portal-Game isolation decisions.
- 2748d41fba0fdd3fcf09ce2e60c4ad1f07e999cd — docs: add durable Work and Codex handoff procedure.

[CI 40742149137](https://github.com/ThomasPerez91/Echosphere/actions/runs/40742149137) entièrement
verte sur 2748d41 : backend/frontend/compose-smoke, 101 tests backend (42 unitaires + 59 PostgreSQL),
11 frontend, 5 Chromium, build/lint, 63 documents/liens et démarrage/panne-reprise PostgreSQL.
Les tests fonctionnels ne sont pas relancés localement pour la mission docs ; leurs fichiers sont
inchangés. Ces résultats CI ne sont pas une recette WSL2/tactile/charge/anti-DDoS. Le présent commit
de checkpoint suit cette tête validée : vérifier aussi sa propre CI avant toute fusion autorisée.

### Prochaine action selon l’état GitHub réel

L’état GitHub réel prévaut sur les états historiques de ce document.

- **Si PR #5 est encore ouverte** : vérifier sa tête publiée et sa CI, effectuer la revue ;
  merge uniquement sur autorisation explicite. Reprendre sa branche pour une mission sur #5,
  sans créer de nouvelle branche ou PR pour ce lot.
- **Si PR #5 est déjà fusionnée** : synchroniser master, considérer 5A/passation comme intégrées,
  puis effectuer la recette locale WSL2/Docker/Codex selon la procédure de passation. Cette recette
  n’a pas encore été effectuée. Ne pas recréer une branche #5. Le prochain développement fonctionnel
  est 5B (Q16/Q40–Q56), uniquement après instruction, sur une nouvelle branche work/... issue de
  master synchronisée ; ne pas commencer directement une API Colony ou le multijoueur.

Le futur agent ne doit pas déduire une autorisation de merge ou de développement de ce checkpoint.

## Historique du checkpoint fonctionnel 5A (antérieur à la passation)

Les sections suivantes conservent les preuves/limites du lot fonctionnel, pas une déclaration de
nouveaux tests exécutés dans la passation. La séquence 5B historique est affinée plus haut.

## Reprise et autorisation vérifiées

PR #4 fusionnée sur instruction de l’utilisateur : master `54f928e2348781db43b335d4dcf569aadc0db6e9`.
[CI master 40716684879](https://github.com/ThomasPerez91/Echosphere/actions/runs/40716684879)
verte avant création de `work/step-5a-colony-domain`. Brief joint appliqué : Étape 5A uniquement.
[PR #5](https://github.com/ThomasPerez91/Echosphere/pull/5) vers master ; aucune autorisation de fusion.
Aucune develop recréée, branche empilée, release ou déploiement.

## Domaine et règles livrés

- game_data/rulesets/v0.1 : resources.json, colony.json, infrastructures.json. JSON/Pydantic strict,
  clés dupliquées/versions mixtes/extras/mauvais types refusés ; erreur explicite sans fallback.
- Référence : 12 secteurs, 2 slots orbitaux réservés, 4 infrastructures I, 8 secteurs libres,
  Command Core conceptuel hors secteurs. Stocks 2000/1500/750, taux 120/100/60 par heure, capacité 10000.
- Cinq infrastructures configurables : trois producteurs répétables ; industrie/logistique uniques.
  Un secteur par exemplaire, aucun secteur de plus à l’upgrade ; niveaux continus sans plafond 5.
- Niveaux explicites 1–5 puis récurrence : producteurs coût/durée/production ×1,38/1,28/1,12 ;
  industrie ×1,40/1,30 et +5 points de bonus ; logistique ×1,40/1,30/1,18. Aucun facteur en service.
- Entiers micro-unités et microsecondes, fractions exactes. Scaling coût/durée plafond,
  production/capacité plancher, durée effective plafond, remboursement plancher. Refus de dépassement.
- Snapshot complet validé par univers, vitesses rationnelles par instance ×1 ; économie/construction
  actives, recherche/flotte seulement réservées. Pas de singleton ni changement implicite des instances.
- Ordre : snapshot version/coût/durée/type/niveau/secteur/vitesse/remboursements. Réservation à l’entrée,
  trois ordres actif inclus, un actif, clé de commande idempotente, prochain bonus industriel évalué
  à l’activation. Prérequis sur infrastructures achevées ; niveaux contigus avec prédécesseurs réservés.
- Annulation 100 % queued / 80 % active, idempotente. Cascade des upgrades dépendants du même secteur ;
  les autres gardent leur ordre. Démarrage suivant à la date logique d’annulation. Remboursement exact
  impossible faute de stockage : refus atomique sans perte/overflow caché, Q39 pour validation produit.
- Production réglée avant changement de niveau/capacité ; perte de production au plafond, reste nul.
  CONSTRUCTION_COMPLETE réutilise EventStream, SAVEPOINT, retries et worker ; aucune seconde file timer.
- Services internes configure_universe/initialize_colony/enqueue/cancel, scope univers/empire/colonie,
  verrou du stream et catch-up complet avant mutation. Transaction du caller, aucun commit interne.

## Persistance et image

Migration `0004_colony_economy`, migrations 0001–0003 intactes. Tables universe_economies,
colony_economies, colony_infrastructures et construction_orders. FK composites, secteur unique,
niveau >=1, unicité de clé/séquence, index partiel un actif. Capacité de planète et limites du ruleset
vérifiées par les services sous lock ; pas de duplication de game_data dans des CHECK de catalogue.
Upgrade/downgrade/upgrade vide et alembic check ; downgrade peuplé refusé avant DDL, pas de suppression
silencieuse. Pas de backfill fictif des anciennes timelines : leur adoption métier reste hors lot.
Contexte build backend à la racine pour inclure game_data ; .dockerignore et emplacement image explicites.
Compose conserve monolithe API/worker/PostgreSQL, vérifie le chargement des données dans le worker.

## UI et documentation

Colony : Vue d’ensemble / Infrastructures / Orbite / Défense, liens directs #colony/<vue>, sélection
globale Colonie conservée, focus/clavier/historique. Aucune huitième entrée principale, colonie/stock/
bâtiment/timer fictif ou commande de défense. État « Aucun univers / aucune colonie active ».
Défense documentée dans planetary-defense.md : réseau stratégique limité, modules persistants,
coût d’opportunité surface/orbite, dommages/réparation/Flux et révélation par renseignement futurs.
Aucune table DefenseNetwork/Module ou effet actif. Q30–Q38 ajoutées et ouvertes ; Q39 remboursement.
ADR 0007, docs produit/UX/tech/qualité, AGENTS, context et roadmap actualisés. Historique 5A : la mention 5B API/UI était la séquence de ce checkpoint,
**superseded** par 5B contrats / 5C fondation Portal / 5D API/UI (passation, ADR 0008).
Les arbitrages v0.1 ne ferment pas les questions générales d’équilibrage et de modes.

## Validation source vérifiée

Local : Ruff, 42 tests unitaires backend, ESLint, 11 tests frontend, build, 5 scénarios Chromium et
56 documents/liens. Captures Colony/Défense inspectées à 320 et 1440 ; scénarios aux quatre largeurs
320/390/768/1440. Les 59 intégrations PostgreSQL sont à exécuter par la CI, pas revendiquées en local.
101 tests backend collectés au total ; tests antérieurs conservés et complétés.

Première CI source 789aa96 : frontend et Compose verts, backend 98 réussis/1 échec de test.
L’intervalle de saturation logistique était de dix jours, insuffisant pour les Données ; corrigé
à vingt jours. Ajout de tests d’édition réelle du catalogue sans repricing et d’événement étranger.
CI source finale entièrement verte sur `58e8f7cf32c1b2fbfd9568ec2317cc4338ae7642` :
[run 40720967410](https://github.com/ThomasPerez91/Echosphere/actions/runs/40720967410).
101 tests backend réussis (42 unitaires + 59 PostgreSQL), 11 frontend, 5 Chromium, lint/build,
56 documents/liens, migrations/absence de dérive, chargement v0.1 dans l’image et smoke Compose avec
panne/reprise PostgreSQL. Tous les scénarios antérieurs sont conservés. Ce checkpoint documentaire
suit la source validée ; vérifier la CI de sa propre tête avant toute future fusion autorisée.

## Limites et reprise

1. PR #5 prête pour revue, laissée non fusionnée. Vérifier sa tête documentaire finale et sa CI ;
   le code source 58e8f7c est validé par le run indiqué ci-dessus.
2. Règles v0.1 provisoires, pas de simulation d’équilibrage longue ou charge massive revendiquée.
3. Aucun PostgreSQL/Docker local exploitable ; intégrations, migrations et Compose validés sur GitHub.
   Pas de recette WSL2/Docker Desktop, tactile/lecteur d’écran réel, Safari/Firefox.
4. Politique de remboursement au stockage insuffisant à revoir (Q39). Changement de ruleset/vitesse
   d’univers actif et adoption des anciennes timelines nécessitent un lot explicite.
5. Après revue/intégration, cadrer Q16 avant 5B. Aucune API gameplay (lecture ou mutation), identité
   globale factice ou gameplay cliquable. Pas d’auth complète, multijoueur, invitations, PvP,
   espionnage, combat, défense réelle, flotte, recherche ou colonisation implémentés dans ce lot.

## Historique

Étapes 0–4 : PR #1 bootstrap, #2 fondation SQLAlchemy/Alembic et modèles, #3 scheduler générique
corrigé, #4 shell responsive. Fusion #3 : 4ee81dd, CI 52 backend/3 frontend/Compose ; fusion #4 :
54f928e, source 52 backend/10 frontend/5 Chromium/Compose. develop supprimée par l’utilisateur et absence
vérifiée. master = intégration stable, work/... → PR master → revue/autorisation propre à chaque merge.
