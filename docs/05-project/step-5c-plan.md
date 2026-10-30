# Étape 5C — cadrage Portal Account/Lobby foundation

**Statut : découpage présenté ; C01–C08 implémentés sur PR #7, C09 recette de clôture.** Mise à jour 2026-10-30.
Autorisation utilisateur : poursuivre 5C après un premier checkpoint documentaire commit/push.
Contrats de référence **validés, inchangés** : [identity-contracts](../03-technical/identity-contracts.md),
[ADR 0008](../adr/0008-control-plane-game-data-plane.md), [registre Q40–Q56](open-questions.md).
Ce plan n’ajoute aucune décision produit. [Socle C01 livré](../03-technical/portal-foundation.md) ;
[C02 comptes/vérification](../03-technical/portal-registration.md) livré ; [C03 sessions/CSRF](../03-technical/portal-sessions.md) livré ; autres contrats futurs.

## 1. Point de départ vérifié et premier commit

PR #6 fusionnée sur instruction, merge master **63bb7d1c902e9c0fbae3497d4a36c107a80eb611**.
Fetch, master fast-forward et arbre propre vérifiés avant création de
**work/step-5c-portal-account-lobby**. Aucun empilement sur la branche 5B ni suppression de branche.
Premier commit **1c2749773c3bb3cf7eedf9a0f4013b9ce7c8f98a**, publié avant ce cadrage : synchronisation
seule de 18 Markdown, décisions Qxx et sections métier 5B inchangées, docs/liens/diff valides.
CI master [40929141873](https://github.com/ThomasPerez91/Echosphere/actions/runs/40929141873) et
checkpoint [40929423582](https://github.com/ThomasPerez91/Echosphere/actions/runs/40929423582)
observées completed/success, backend/frontend/compose-smoke réussis. Aucun code 5C à ce stade.

Réalité du dépôt : backend/app = monolithe Game FastAPI ; migrations Game 0001–0004 ; frontend =
shell React/Vite Game ; docker-compose.yml comporte cinq services Game. Aucun compte, MFA, lobby,
GameAccess ou GameSession. Les services 5A ne génèrent pas une partie complète : initialize_colony
requiert une Colony existante ; aucun générateur de galaxie avant son lot. Ne pas combler cela par
une fixture runtime, un compte factice, une identité human/ai ou un accès public implicite.

## 2. Résultat visé et limite du lot

Parcours cible 5C : inscription → vérification email → connexion/session Portal → paramètres et
sécurité du compte → lobby de participations réelles → handoff sécurisé vers un contexte Game.
L’entrée Game peut établir/afficher son contexte d’accès et permettre logout/retour lobby ; aucun
stock, bâtiment, file, lecture ou mutation économique n’est exposé avant 5D.

Le lobby est vide s’il n’existe aucune participation réelle. Le périmètre proposé couvre la liste,
les états pending/applied/suspended et l’entrée dans une participation provisionnée par le circuit
interne autorisé. Il ne crée pas de catalogue public, d’invitations ni de join privé/persistant.
Le provisionnement technique d’Universe et d’accès passe par Game ; les tests créent leurs données
uniquement dans les bases dédiées. Aucun univers de démonstration au démarrage.

La création autonome d’une **partie jouable** avec Empire, monde initial et IA n’est pas incluse dans
cette fondation d’identité. Son parcours et ses règles de démarrage doivent être cadrés avant son
endpoint utilisateur : ce point est une limite de périmètre, pas une réouverture des contrats 5B.
L’architecture garde ProvisionUniverse, sans générer une galaxie ou des droits gameplay implicites.

## 3. Sous-tickets proposés, dans l’ordre

Les identifiants Cxx sont des repères de travail locaux, pas des issues GitHub déjà créées.

| Ticket | Contenu | Preuve de sortie |
| --- | --- | --- |
| C00 | Synchronisation post-merge | Réalisé par 1c27497, docs/Qxx/diff et CI vérifiés |
| C01 | **Implémenté sur PR #7** : configuration, FastAPI, Accounts PostgreSQL, Alembic indépendant, frontend React/Vite, sondes et HTTPS local | Deux bases/processus/credentials/pools distincts ; Game existant intact ; migrations avant démarrage, aucun secret Git/VITE |
| C02 | **Implémenté sur PR #7** : comptes : User stable, credential Argon2id, inscription, vérification email 24 h, envoi durable et non-énumération | Concurrence d’inscription/vérification/réémission, aucune adresse non vérifiée autorisée à entrer Game |
| C03 | **Implémenté sur PR #7** : sessions Portal/appareils : opaque serveur, CSRF, rotation, activité explicite, gestion des connexions et caps configurables | Frontières 7 j/72 h, trafic automatique sans prolongation, profils/onglets, quota concurrent et logout local |
| C04 | **Implémenté sur PR #7 sans MFA** : compte sensible : step-up par action, reset/changement mot de passe et changement email avec preuves et notifications | Jetons uniques/dernière demande, échéances 30 min/1 h, invalidations croisées et intentions de révocation atomiques, sans auto-login |
| C05 | **Implémenté sur PR #7** : MFA joueur TOTP/WebAuthn, secours, récupération limitée, protection des privilèges | Un TOTP/cinq WebAuthn, dix secours uniques, step-up 5 min, récupération 15 min, effets MFA ciblés et audit/notifications ; aucune procédure support inventée |
| C06 | **Implémenté sur PR #7** : Memberships/lobby et interface interne privée mTLS : outbox, état effectif Game, révisions, idempotence, révocations ciblées et réconciliation | Pending distinct d’applied, doublons/désordre/timeout sans double effet ni résurrection, refus du service non autorisé |
| C07 | **Implémenté sur PR #7** : Handoff réel et sessions Game : pré-auth navigateur, signature asymétrique, consommation atomique, clés locales, appareil/scopes et logout | Ticket 60 s unique, clés inconnues refusées, droits 8 h non glissants, session 8 h/2 h, révocations concurrentes et UI en attente fidèle ; aucune API Colony |
| C08 | **Implémenté sur PR #7** : Parcours frontend compte/lobby/sécurité et adaptation minimale du shell Game | Mobile/clavier, erreurs/chargements, aucun secret localStorage, API même origine et CORS refusé par défaut ; écrans branchés aux vrais services |
| C09 | **Recette réalisée sur PR #7** : Recette de clôture et passation de l’incrément | Tests ciblés/concurrence PostgreSQL des deux plans, Chromium HTTPS, migration/absence de dérive, reprise workers/livraison, CI et docs de tête ; limites restantes explicites |

Les tests accompagnent chaque ticket ; C09 n’est pas une attente avant de vérifier la sécurité.
C01 est le premier incrément de code après présentation de ce plan, désormais réalisé ; C02 comptes/vérification est réalisé, C03 sessions est réalisé ; C04, C05 MFA et C06 lobby/mTLS sont réalisés ; C07 et C08 sont réalisés ; C09 porte la recette et la passation de clôture. Les dépendances C04/C05 sont
itératives : aucun endpoint sensible utilisable sans ses preuves requises, aucune route MFA simulée.
C06/C07 concernent les fondations d’accès, pas les commandes gameplay réservées à 5D.
Une protection prévue mais absente ne sera jamais annoncée comme livrée dans un checkpoint partiel.

## 4. Structure envisagée

Conserver les chemins Game existants et ajouter deux applications Portal séparées :

```text
portal/
  backend/
    portal_app/
      api/
      core/
      persistence/
      accounts/
      sessions/
      mfa/
      lobby/
      delivery/
    migrations/
    tests/
  frontend/
    src/
      account/
      security/
      lobby/
    e2e/
backend/app/                 # Game existant ; futur module access et interface interne
backend/migrations/          # Historique Game, inchangé jusqu’à sa migration d’accès additive
frontend/                    # Game existant, adaptation du contexte d’accès seulement
contracts/portal-game/       # Schémas de messages purs versionnés, sans ORM ni credential partagé
```

Noms de modules et schémas restent des détails techniques délégués. Pas de déplacement/refonte du
monolithe Game ni de base ORM partagée. Portal conserve les mêmes technologies Python/FastAPI,
SQLAlchemy/Alembic/PostgreSQL et React/TypeScript/Vite ; configurations, packages, processus et pools
propres. Réutiliser le langage visuel sans fusionner les sessions ni introduire un kit UI tiers inutile.

Compose est étendu dans C01/C02 et le sera dans C06/C07 : Accounts DB/Portal/migration/worker de livraison séparés,
origines HTTPS Portal et Game contrôlées, interface interne mTLS sans exposition publique. Les
services Game et leur volume sont préservés. Certificats/secrets de développement hors Git ; aucune
installation silencieuse d’une CA dans Windows ou d’un service externe. Chaque origine sert son
frontend et relaie sa propre API ; l’interface interne n’est pas le proxy des commandes gameplay.

## 5. Tables et migrations Portal envisagées

**Schéma cible ; C02–C06 créés (six/cinq/cinq/six/trois tables Accounts), accès Game 0005 ajouté.** Les noms exacts peuvent être affinés avec les contrats
SQL/API avant implémentation, sans modifier les règles 5B. UTC aware ; FK locales, contraintes et
transactions PostgreSQL ; aucune FK ou connexion SQL vers Game DB depuis Portal.

| Groupe | Tables envisagées | Contraintes principales |
| --- | --- | --- |
| Compte | users, password_credentials | global_user_id stable, email validé/normalisé de manière documentée et unique ; un credential mot de passe actif, hash Argon2id ; aucune fusion d’identité basée sur l’email |
| Preuves email | account_tokens, email_change_requests | Empreintes et purpose ; unique parcours actif par type/compte, consommation atomique ; changement email unique et preuves de la même demande, échéance commune |
| Appareils/sessions | account_devices, portal_sessions | Profil navigateur opaque rattaché au compte ; secret de session empreinté, création/activité/expiration/révocation ; limites configurables comptées sous transaction |
| MFA | totp_credentials, webauthn_credentials, mfa_backup_codes | TOTP actif unique chiffré avec clé séparée ; credential WebAuthn unique/nommable, limite cinq ; secours non réversibles et consommables une fois |
| Preuves temporaires | authentication_challenges, step_up_grants, mfa_recovery_sessions | Challenges liés au parcours ; step-up lié session/action/paramètres, 5 min et usage unique ; récupération 15 min avec droits restreints |
| Lobby | universe_references, universe_memberships | Références d’univers confirmées par Game, pas de monde en Accounts ; unicité compte/univers ; intention et révision séparées de l’acquittement Game |
| Livraison | control_outbox, email_outbox | Intention de sécurité et livraison dans la transaction Accounts ; identifiants stables, retry/acquittement ; confirmations sensibles chiffrées si matérialisées dans la file, jamais journalisées |
| Protection/audit | abuse_counters, security_events | Seuils configurables par opération/compte/IP ; audit sans secrets, rétention 90 j distincte de la protection anti-rejeu |

Migration Accounts C01 livrée : p0000_portal_baseline, historique seul, aucune table métier.
Migrations des tickets suivants envisagées :

- P0001 livrée C02 : users/password_credentials/account_tokens/email_outbox/abuse_counters/security_events ;
- P0002 livrée C03 : browser_profiles/account_devices/portal_sessions/login_challenges/logout_requests ;
- P0003 livrée C04 : step-up/reset/changement email, révocations compte et livraison sécurité ;
- P0004 livrée C05 : facteurs TOTP/WebAuthn, secours, challenges/récupération et cooldown ;
- P0005 livrée C06 : références univers/memberships/outbox interne ;
- Révisions ultérieures : handoff et accès de session. Numérotation précisée au ticket, sans modifier p0001 publiée.

Chaîne Alembic et table de version dans **Accounts DB**, indépendantes de Game 0001–0005. Révisions
immutables une fois publiées ; migration d’un sous-ticket dépendant uniquement des tables déjà livrées.
Les tests de roundtrip utilisent Accounts *_test. Aucun downgrade sur les données à conserver.

### Complément Game strictement nécessaire à 5C

Migration additive Game 0005 livrée pour droits/bindings/ledger/epochs ; compléments C07, dans sa propre chaîne : accès locaux/memberships effectifs,
bindings d’Empire scopés, générations/révocations ciblées, résultats d’opérations internes,
pré-auths/handoffs consommés et GameSessions. Contraintes composites et verrous C06 livrés ;
compléments session livrés par [C07](../03-technical/game-handoff.md), migration 0006_game_sessions. Aucun email, mot de passe, secret MFA ou accès Accounts DB dans le code Game.
Ce complément rend l’entrée sécurisée testable ; aucun endpoint de lecture/commande Colony.

## 6. Frontière explicite 5C / 5D / reports

| Domaine | 5C proposé | Hors 5C |
| --- | --- | --- |
| Comptes | Inscription, connexion, vérification, sessions et paramètres sensibles, MFA/step-up/secours | OIDC, fournisseur production imposé, récupération support après perte totale |
| Lobby | Liste réelle, état d’application d’accès, entrée/handoff, retour et logout | Catalogue public, invitations, règles privées/persistantes, partage d’Empire |
| Game | Accès local, session, contexte minimal d’entrée et interface interne sécurisée | API Colony, projections économiques, construire/annuler, UI stocks/files : **5D** |
| Univers | Références et provisionnement interne contrôlé | Génération de galaxie, démarrage d’une partie complète/IA, règles join/leave/late join non arbitrées |
| Résilience | Tests auth/handoff/livraison et continuité du worker existant | Recette de commandes Colony en panne Portal et charge gameplay 5D, industrialisation étape 17 |
| Administration | Refus de privilèges sans protection WebAuthn requise | Console d’administration et procédure de récupération privilégiée non décidées |

Livraison email locale via récepteur de test explicitement configuré, sans provider production ni
exposition publique. Un email en attente n’est pas annoncé envoyé ; aucune vérification bypassée.
Clés de chiffrement/signature et secrets d’envoi par environnement, jamais en DB ou frontend en clair.

## 7. Arbitrages et entrées encore nécessaires

Aucun arbitrage 5B à rouvrir pour commencer C01. Bibliothèques, paramètres Argon2id mesurés,
crypto/signature, stockage, URLs/schémas, RP de développement, verrous/retry et seuils initiaux relèvent
de la délégation validée ; leur choix exige sources primaires, tests et justification avant usage.

Reports inchangés : Q48 support renforcé joueur/privilégié, Q49 fournisseur/domaines/configuration
avant production, Q55 règles des modes. Ils ne bloquent pas le socle local ; ils bloquent leurs
parcours ou déploiement concernés. Aucun secret demandé dans le chat.

Si l’on veut inclure un bouton utilisateur créant une **partie jouable** dans ce lot, il faudra cadrer
ensemble le démarrage minimal (Empire/monde, IA absente avant son lot, configuration et état de partie)
et sa place dans la roadmap, sans inventer Q14/Q19–Q29. Le périmètre minimal proposé ne dépend pas
de cet arbitrage : pas de bouton trompeur ni de fixture runtime en attendant.

C01 a reçu l’instruction utilisateur de démarrer après cette présentation. Les tickets futurs
ne sont pas déclarés implémentés par le code du socle ; aucun nouveau choix produit validé par implication. Aucun nouveau merge autorisé ; 5D non commencé.
