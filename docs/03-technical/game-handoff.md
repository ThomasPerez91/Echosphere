# C07 — handoff et sessions Game

**Statut : implémenté et testé sur PR #7 ; non intégré à master.**
Contrats [5B](identity-contracts.md) inchangés ; [C06](portal-game-control.md) fournit droits et epochs.
Pas d’API Colony ni de monde de démonstration. Raffinement des parcours/shell : C08 ; clôture : C09.

## Protocole et autorités

JWT Ed25519 via PyJWT 2.15.1/cryptography, algorithme EdDSA imposé, type
`echosphere-handoff+jwt`, claims stricts [schéma v1](../../contracts/handoff/v1.schema.json).
`iss`/`aud` sont les origines Portal/Game configurées ; `sub`, `device_id`, `membership_id`,
`universe_id`, `pre_auth_id`, `jti` lient identité, profil et scopes. `revision`, `account_epoch`,
`device_epoch`, `access_epoch` empêchent les droits obsolètes. `iat`/`exp` entiers : refus dès
`now >= exp`, durée positive au plus 60 s, émission future refusée sans tolérance ajoutée.
Aucun email, credential ou permission autoritaire dans le ticket.

Les clés publiques sont prédistribuées via `HANDOFF_PUBLIC_KEYS` (mapping kid→fichier local), sans
lookup réseau. Header exactement alg/kid/typ ; URL de découverte, algorithme alternatif, type ou
clé inconnus refusés. Portal possède seul la clé privée `PORTAL_HANDOFF_PRIVATE_KEY`, son kid
`PORTAL_HANDOFF_KEY_ID`. Initialisation dev Ed25519 en volumes séparés portal_handoff/game_handoff :
clé privée 0600, public seul accessible à Game. Clés distinctes de MFA/mail et de la PKI mTLS.
Une clé existante invalide ou un public différent font échouer init, sans régénération silencieuse.

## Navigation entre les origines

1. Le lobby ne propose l’entrée que pour un compte vérifié et sa participation active acquittée,
   non expirée, sans réconciliation pending. Aucune création/join public.
2. `GET Game /game/{universe}/start` crée un UUID et un secret aléatoires serveur, jamais fournis par
   le lien. Empreinte du secret en DB, cookie pré-auth host-only par univers, échéance absolue 5 min.
3. Un formulaire POST navigue vers `Portal /handoff/prepare`, qui vérifie session et origine Game
   exacte, puis présente une confirmation avec CSRF lié à la session Portal. Cette préparation
   ne constitue ni émission ni renouvellement.
4. `POST Portal /handoff/issue` vérifie origine Portal, CSRF, session normale active, email vérifié,
   membership active déjà acquittée et non expirée. La récupération MFA limitée ne satisfait jamais
   la session normale. Le profil est celui de la PortalSession, jamais un device fourni par le client.
5. Le formulaire POST transporte le ticket vers `Game /game/{universe}/exchange`, avec origine
   Portal exacte et cookie pré-auth Game. Pas de fetch cross-origin avec credentials, ni ouverture CORS.
6. Après échange, cookie opaque Game et redirection 303 vers URL propre `/api/game/{universe}/view`.
   Les préfixes `/api` appartiennent aux proxies de même origine ; les routes FastAPI ci-dessus les omettent.

Ticket jamais en query, fragment, localStorage, logs ou ressources tierces. Corps bornés 8 KiB,
champs de formulaires uniques/exacts ; query refusée aux transferts. Pages no-store, CSP sans script
ni ressources distantes, anti-framing et CSS local à nonce. **Referrer-Policy strict-origin** pour
les documents de transfert : seul l’origin peut être transmis ; `no-referrer` pourrait produire un
Origin null sur la navigation POST et ferait échouer le contrôle exact. Aucun refus Origin null
n’est assoupli. Réponses JSON/contexte : no-store, no-referrer. Les formulaires restent utilisables
sans JavaScript ; simplification des étapes et intégration du contexte au shell React en C08.

## Transaction et révocations

Vérification cryptographique locale puis verrou du GamePrincipal **existant** ; absence d’accès ou
principal refusée, jamais créée depuis un ticket. Scope user/univers/membership, état actif, dates,
générations compte/appareil/accès et révision locale au moins celle du ticket sont revérifiés.
Une livraison à droits inchangés ne révoque pas les sessions ; un changement d’access_epoch les invalide.
Pré-auth verrouillée, cookie/échéance/usage contrôlés et dates revérifiées après attente du verrou.
Consommation jti/pré-auth et création/rotation de session sont atomiques. Rejeu ou réponse perdue après
commit : nouveau parcours requis, jamais reprise d’un ticket consommé.

C06 utilise le même verrou principal pour accès et révocations : réception d’une révocation compte/
appareil, suspension ou changement de bindings invalide les anciens tickets/sessions. Réactivation
ne ressuscite pas une session. La portée Game locale révoque seulement la session courante ; son
horodatage persistant interdit aussi une cérémonie de ce même slot commencée avant le logout.
Autres univers/appareils/Portal et simulation conservés. Les générations restent vérifiées à chaque
usage : un acquittement C06 signifie effet local réellement opposable aux sessions.

Les futures commandes 5D devront appeler `GameSessions.locked(session, ...)` **dans leur transaction**,
avant EventStream ; `read()` possède sa transaction et ne doit pas servir de preuve préalable
séparée à une mutation. Aucun handler temporel ne prend ces verrous d’identité.

## Échéances, profils et limites

Une GameSession active par compte/profil/univers, cookie `__Host-game-session-<uuid>`, Secure,
HttpOnly, SameSite Strict, Path=/ et sans Domain ; pré-auth nommée séparément. Empreintes seules
persistées. Onglets d’un profil partagés, cookies par univers sans s’appuyer sur le port.
Plafond configurable `GAME_UNIVERSE_SESSION_LIMIT=10`, compté sous verrou principal en concurrence,
avec refus 409 et aucune éviction silencieuse ; ne limite jamais les memberships.

Session au plus 8 h depuis création, 2 h depuis activité explicite et **borne d’accès capturée** à
l’entrée. L’accès courant peut encore la raccourcir. `GET session/view`, polling et retour lobby ne
comptent pas ; POST navigation explicite protégé par CSRF compte après vérification d’expiration.
Aucun timestamp d’activité client. Réentrée : rotation du secret, session active conservant son
créé/le délai absolu/la borne d’accès capturée ; aucune résurrection expirée.

`POST Portal /lobby/universes/{uuid}/renew` est une action explicite authentifiée/CSRF pour confirmer
à nouveau des droits inchangés : revision suivante et confirmation serveur +8 h dans l’outbox,
access_epoch inchangé. L’entrée attend l’acquittement. Ne réactive jamais un accès suspendu/révoqué,
ne modifie pas une intention pending, ne prolonge pas une session Game existante. Une nouvelle
session après expiration exige un nouveau handoff Portal valide. Panne Portal : pas d’émission ou
renouvellement ; ticket déjà émis consommable sous contrôles locaux, session établie utilisable dans
ses limites. Aucune lecture de la DB Accounts ou requête Portal par usage Game.

Seuils techniques initiaux : pré-auth Game `PRE_AUTH_IP_LIMIT=60` par IP/heure glissante en DB sous
verrou ; `PORTAL_HANDOFF_IP_LIMIT=60` et `PORTAL_HANDOFF_ACCOUNT_LIMIT=30` par fenêtre horaire pour
émission/renouvellement. Configurables, refus 429, aucun verrouillage permanent. Headers d’IP admis
uniquement depuis le proxy explicitement configuré/résolu ; un header navigateur n’est pas une preuve.
Aucun test de charge hostile ou protection DDoS prétendu.

## Persistance et exploitation

Game additive **0006_game_sessions** : game_pre_auths, game_consumed_tickets, game_sessions ;
unicité d’un slot actif et du jti/pré-auth, CHECK des durées/générations et FK composites
membership/compte/univers et appareil/compte. Ajoute l’unicité de scope correspondante sur GameAccess.
Historique 0001–0005 immuable, downgrade peuplé refusé. Pas de nouvelle migration Accounts nécessaire
à une émission sans stockage de ticket. Marqueurs minimaux et preuves anti-rejeu ne sont pas purgés
par la rétention d’audit 90 jours ; politique de nettoyage/archivage et backups à recetter en C09.

Rotation : prédistribuer nouveau public dans le mapping Game avant d’activer sa clé privée/kid Portal,
conserver l’ancien pendant le recouvrement des tickets et des sessions voulues. Retirer un kid du
mapping Game et redémarrer ces processus invalide les sessions signées par ce kid à leur prochain
usage. La procédure de compromission doit aussi traiter les générations compte/appareil pertinentes.
Aucun rechargement automatique ou outil complet de rotation production livré ; recette C09 avant exposition.

## Validation et limites

Commandes de recette : suites PostgreSQL backend et Portal, tests/lint/build/Chromium Portal,
checks Alembic, scripts smoke Game/Portal/contrôle privé et
`python3 scripts/smoke_handoff_compose.py`. Cette dernière crée un projet Compose nommé aléatoirement,
avec DB *_test, aucun port hôte et volumes propres, provisionne un accès via le worker mTLS réel,
puis exerce Chromium sur les deux origines HTTPS à 320/1440. Les certificats locaux sont acceptés
uniquement dans ce contexte Playwright ; aucune confiance CA/hosts de l’hôte n’est modifiée.
Suppression de ses propres ressources seulement, jamais celles de la pile conservée.
Captures sous `/tmp/echosphere-handoff-artifacts`, hors Git. Résultats réellement obtenus : progress.

C08 reste nécessaire pour intégrer le contexte au shell React et affiner login/expiration/erreurs et
suivi après logout Portal ; la vue C07 est une preuve d’accès minimale, pas une partie jouable.
Pas d’administration, création de galaxie/Empire/IA, ni lecture économique ; 5D non commencé.
Q48 support, Q49 fournisseur/configuration production et Q55 modes restent différés. Pas de recette
Safari/Firefox, appareil physique, restauration DB ni charge hostile attestée.

## Sources des mécanismes

[PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html),
[RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html) et
[Fetch — Origin des requêtes](https://fetch.spec.whatwg.org/#append-a-request-origin-header).
Les durées/règles produit proviennent exclusivement des décisions 5B. Choix techniques délégués,
aucun nouvel arbitrage produit.
