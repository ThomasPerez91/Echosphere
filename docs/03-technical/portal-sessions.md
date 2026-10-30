# Connexion, appareils et sessions Portal — C03 de 5C

**Statut : implémenté sur work/step-5c-portal-account-lobby / PR #7, non intégré à master.**
2026-10-30, Codex local ; instruction utilisateur de poursuivre après C02.
[Contrats 5B inchangés](identity-contracts.md) · [Plan 5C](../05-project/step-5c-plan.md) ·
[Inscription C02](portal-registration.md) · [HTTPS local](portal-foundation.md).

## Périmètre et parcours

Connexion email/mot de passe, lecture de sa session et de ses connexions actives, actualisation
volontaire et déconnexion ciblée. Un compte non vérifié peut ouvrir cette session Portal minimale
pour poursuivre la vérification ; aucun accès Game n’est créé. Le lobby reste en préparation.
Aucun MFA, step-up, reset, changement email, logout tous appareils, membership, S2S/handoff ou API
Colony. Ces fonctions restent aux tickets C04–C09 ; aucune route permissive ne les simule.

Le navigateur obtient un challenge de connexion opaque, cookie HttpOnly et preuve CSRF en réponse
JSON no-store. Le POST de connexion exige ces deux éléments liés, Origin exact, JSON et mot de
passe. Le challenge initial dure cinq minutes absolues, usage unique sous verrou PostgreSQL ; son
secret est empreinté en DB. Il ne s’agit pas de la pré-auth Game de C07 et ne donne aucun droit.
Un échec de credentials retourne la même erreur pour compte absent, mot de passe faux ou compte
suspendu. Aucune fusion/remplacement silencieux d’un autre compte déjà connecté dans ce contexte.

## Cookies et CSRF

| Cookie | Usage | Durée navigateur initiale |
| --- | --- | --- |
| __Host-portal-login | Challenge anonyme de connexion | 300 s ; effacé au succès |
| __Host-portal-session | Secret de session Portal | Au plus le reste des sept jours absolus |
| __Host-portal-device | Rattachement opaque du profil navigateur | 365 jours, identifiant technique sans droit de connexion |

Tous : Secure, HttpOnly, SameSite=Strict, Path=/, aucun Domain. Cookies Portal host-only ; le port
n’est pas une frontière de cookie. Game aura ses propres cookies. Secrets de 256 bits générés côté
serveur, SHA-256 seuls en base ; aucune valeur choisie par le client ne devient un nouvel identifiant
valide. Le cookie de profil seul ne permet ni lecture du compte, ni connexion ou commande.

La preuve CSRF est HMAC-SHA-256 du secret de challenge/session sur un contexte fixe versionné ;
le client reçoit uniquement ce dérivé, pas le secret HttpOnly. Le serveur recalcule et compare en
temps constant ; format borné avant comparaison. Changer le secret invalide sa preuve. Preuve par
header X-CSRF-Token, jamais par URL ou seul cookie, uniquement en mémoire JS. Elle n’est pas un
substitut d’authentification : un cookie arbitraire et sa preuve ne correspondent à aucune session.
Chaque mutation vérifie aussi Origin exact et Content-Type JSON ; corps limité à 8 Kio.

Les GET de bootstrap exigent X-Portal-Request: bootstrap, et rejettent un Origin différent s’il
est présent. Un frontend d’une autre origine ne peut ajouter ce header sans préflight, refusé par
la politique CORS par défaut. Aucune allowlist cross-origin introduite, y compris pour Game.
Toutes les réponses de session sont no-store/referrer no-referrer ; aucun secret navigateur stocké
localement, logué ou inclus dans l’URL. Les erreurs ne recopient pas l’entrée privée.

## Délais et classification serveur

Refus dès now >= min(created_at + 7 jours, last_activity_at + 72 heures). UTC serveur uniquement.
Vérification avant mise à jour : aucune résurrection d’une session expirée. Une nouvelle preuve de
mot de passe peut établir une nouvelle session après expiration ; une rotation pendant la validité
de la session existante conserve sa création et son échéance absolue, puis invalide l’ancien secret.
Les onglets du profil partagent le cookie ; une réponse ancienne ne restaure pas un secret invalidé.

| Requête/action | Effet sur l’inactivité |
| --- | --- |
| GET session/sessions, bootstrap automatique, readiness, reload/reconnexion réseau | Aucun |
| POST navigation : bouton volontaire « Actualiser mes connexions » | Date serveur, après CSRF/auth/expiration |
| Connexion prouvée par mot de passe | Nouvelle session ou rotation contrôlée |
| Déconnexion d’une autre connexion du compte | Interaction explicite sur la session appelante |

Pas de listener global de clic ou heartbeat ; aucun polling déclenchant POST navigation.
Timestamp/flag d’activité en query/body ne change pas la classification. Le serveur connaît la
sémantique de cette action explicite ; cela ne prouve pas qu’un appelant ne soit pas automatisé.
Le reload automatique du composant fait uniquement une lecture ; les futures navigations/actions
seront classées dans leurs propres routes, sans élargir arbitrairement la surface de keep-alive.
GameAccess.valid_until et ses limites ne sont pas implémentés/modifiés dans C03.

## Profil navigateur et concurrence

BrowserProfile représente le profil par un secret de cookie, pas par IP/empreinte matérielle.
AccountDevice lie ce profil à un compte ; aucune FK inter-bases. Dix appareils actifs par compte
par défaut, paramètre PORTAL_CONNECTED_DEVICE_LIMIT, pas invariant produit ni limite de memberships.
Une session Portal active par compte/profil réalise le partage entre onglets. Le comptage C03
porte sur Portal seulement, aucune GameSession n’existant encore ; C06/C07 devront aussi prendre
en compte les accès/sessions Game encore valides pour respecter le plafond global d’appareils.

Toutes les mutations de sessions d’un compte prennent le verrou User, puis le challenge/profil et
les sessions concernées ; relecture des secrets après verrou. Un index unique partiel interdit deux
sessions non révoquées par appareil. Avant comptage, les sessions expirées sont retirées du compte
actif ; elles restent en historique serveur. Plafond atteint : 409 device_limit_reached et demande
de fermer explicitement une connexion depuis un appareil déjà connecté, sans éviction silencieuse.
Effacer les cookies crée un nouveau rattachement à la prochaine connexion ; l’ancienne session
serveur reste visible et révocable tant qu’elle est active. Aucune activité liée à la simple présence.

## Déconnexion et intention durable

Logout courant : invalidation de la PortalSession courante et intention de révoquer toutes les
GameSessions de ce compte sur ce profil, pas les autres appareils. La gestion des connexions permet
la même fermeture ciblée sur une autre connexion de son propre compte ; identifiant étranger refusé.
Logout global distinct avec step-up : C04/C05, aucun bouton « tous appareils » dans C03.

Dans une transaction Accounts : session révoquée, epoch d’appareil incrémenté, demande logout_requests
persistée avec compte/appareil/session/epoch, audit minimal. Répéter la fermeture du même identifiant
ne crée ni nouvelle demande ni nouvelle génération. Les FK composites empêchent une intention
associée à la session d’un autre compte/appareil. Un échec d’écriture annule aussi la révocation.

L’epoch est la borne d’invalidation des anciennes sessions de l’appareil ; C06/C07 devront porter
cette génération dans leurs accès/messages et refuser les anciennes générations sans couper celles
créées après. C03 persiste seulement l’intention : **aucun transport/acquittement Game n’existe encore**.
Réponse/UI : Portal déconnecté, déconnexion des parties en attente, jamais déconnexion distante
instantanée affirmée. Les demandes restent pending pour le consommateur C06 ; la présence d’un champ
acknowledged ne signifie pas qu’un worker d’acquittement existe. Aucun effet sur univers/workers.

## API sous /api sur l’origine Portal

| Route backend | Protection / effet |
| --- | --- |
| GET /auth/challenge | Bootstrap contrôlé + quota ; challenge anonyme et preuve CSRF |
| POST /auth/login | Credentials + challenge/cookie/CSRF/Origin ; session et profil opaques |
| GET /auth/session | Session courante ; aucune activité |
| GET /auth/sessions | Connexions actives du compte ; aucune activité |
| POST /auth/navigation | Session/CSRF/Origin ; actualisation explicitement classée serveur |
| POST /auth/logout | Session/CSRF/Origin ; session courante et intention appareil |
| POST /auth/sessions/{id}/logout | Même protection + scope compte ; fermeture ciblée |

401 authentication_required/invalid_credentials/login_challenge_expired ; 403 csrf_denied/origin_denied ;
404 session_not_found ; 409 device_limit_reached/account_switch_requires_logout ; 429 rate_limited ;
503 panne DB/saturation. Aucun secret d’authentification dans les réponses, sauf la preuve CSRF dédiée.
Seuils configurables : LOGIN_IP_LIMIT=30/h, LOGIN_ACCOUNT_LIMIT=10/h, BOOTSTRAP_IP_LIMIT=60/h,
préfixés PORTAL_. Compteurs persistants distincts des demandes email C02, sans verrouillage permanent.

## Migration et validation

**p0002_portal_sessions** additive, p0000/p0001 inchangées : browser_profiles, account_devices,
portal_sessions, login_challenges, logout_requests. FK locales, unicités, bornes absolues/activité et
générations contraintes en PostgreSQL. Downgrade peuplé refusé ; tests de roundtrip seulement *_test.
Le worker email nettoie les challenges expirés depuis plus d’un jour ; la purge audit 90 jours ne
supprime ni sessions/générations ni demandes de déconnexion à rejouer. Aucun credential dans Game.

```bash
docker compose up --build -d --wait --wait-timeout 180
docker compose exec -T portal-backend alembic check
python3 scripts/check_docs.py
python3 scripts/smoke_portal_compose.py
```

Tests backend PostgreSQL dédiés : délais exacts, rotation, refus, concurrence, quotas, scopes SQL,
rollback session/intention, génération monotone, cookies/CSRF et non-activité des lectures. Frontend :
bootstrap, login/challenge, actualisation volontaire et déconnexion en attente ; Chromium mobile/
desktop et clavier. Résultats réels et limites dans progress ; UI à API interceptée distincte des
intégrations API/DB et du smoke TLS. Recette complète navigateur HTTPS/handoff : C09, pas revendiquée.

Sources techniques : [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
Ces choix techniques réalisent les contrats 5B validés ; aucune Qxx fermée ou arbitrage produit ajouté.
