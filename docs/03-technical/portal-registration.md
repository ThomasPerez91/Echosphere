# Comptes et vérification email — C02 de 5C

**Statut : implémenté sur work/step-5c-portal-account-lobby / PR #7, non intégré à master.**
2026-10-29, Codex local, instruction utilisateur « enchaine » après C01.
[Plan 5C](../05-project/step-5c-plan.md) · [Socle/réseaux/HTTPS](portal-foundation.md) ·
[Contrats 5B inchangés](identity-contracts.md).

État courant : [C03 sessions Portal/CSRF](portal-sessions.md) est livré sur PR #7 ; les exclusions
de sessions de ce document décrivent le périmètre historique de cet incrément.

État courant : [C04 opérations sensibles sans MFA](portal-account-security.md) livré sur PR #7.
Les exclusions d’opérations sensibles ci-dessous décrivent le périmètre historique de cet incrément.

## Périmètre

Inscription email/mot de passe, renvoi et confirmation de l’adresse initiale, formulaires Portal,
livraison email durable vers un récepteur local. Aucune connexion/session, MFA, récupération,
changement email, membership, accès Game ou API Colony. Confirmer son adresse ne connecte pas.
Le compte et ses preuves résident uniquement dans Accounts DB ; aucun changement Game.

User.id est le global_user_id UUID aléatoire stable, indépendant de l’adresse et du credential.
email-validator valide sans consultation DNS ; domaine IDNA ASCII, adresse conservée pour livraison,
clé de recherche casefoldée et unique. Aucun retrait des points ou suffixes + de fournisseurs.
Une inscription dupliquée ne remplace jamais le mot de passe ou les preuves du compte existant.

### Mot de passe

15–128 caractères, espaces autorisés, sans composition imposée ni transformation/troncature.
argon2-cffi 25.1.0 : Argon2id v19, 64 MiB, trois passes, parallélisme un, sel aléatoire 16 octets,
empreinte 32 octets. Deux calculs/vérifications simultanés maximum par instance ; saturation : 503.
Ces paramètres initiaux sont mesurés localement dans progress, pas un benchmark production.

Le service public gratuit Pwned Passwords est interrogé à la soumission d’un nouveau mot de passe :
HTTPS, cinq caractères du SHA-1, Add-Padding, comparaison des suffixes en mémoire uniquement.
Ni mot de passe, email, SHA-1 complet ou suffixe recherché ne sont envoyés ; aucun secret/API key.
Le SHA-1 sert uniquement à cette recherche, jamais au stockage du credential. Timeout trois secondes,
réponse bornée/validée ; panne ou réponse invalide : 503, aucun compte partiellement créé.
Aucun contournement runtime du contrôle. Les tests substituent le transport, pas le code production.
Cette dépendance réseau et le refus temporaire d’inscription en panne sont une limite explicite.

## API même origine

Les chemins suivants sont servis sous /api par le proxy de l’origine Portal HTTPS.
POST JSON uniquement, Origin exact obligatoire, corps limité à 8 Kio avant parsing, champs inconnus
refusés. Les erreurs de validation ne recopient jamais l’entrée (notamment le mot de passe).
Réponses Cache-Control: no-store ; aucun cookie/token de connexion émis. CORS credentials reste refusé.

| Route backend | Corps | Réponse |
| --- | --- | --- |
| POST /accounts/register | email, password | 202 request_received, même réponse pour adresse existante |
| POST /accounts/email/resend | email, password | 202 request_received même si compte absent, mot de passe faux ou adresse déjà confirmée |
| POST /accounts/email/verify | token, password | 200 verified ; preuve erronée, expirée ou consommée : 400 invalid_verification |

Autres refus : 400 invalid_request/password_rejected, 403 origin_denied, 413 corps trop grand,
415 format non JSON, 422 validation générique, 429 rate_limited, 503 temporarily_unavailable.
Une réponse 202 ne prouve ni existence du compte ni envoi effectif d’un email.

Confirmation et renvoi demandent le mot de passe choisi à l’inscription, vérifié côté serveur :
mesure technique contre l’activation d’un compte préinscrit par un tiers avec l’email de la victime.
Un lien seul ne confirme pas le compte ; aucun parcours de récupération inventé pour le contourner.
La connexion et les opérations sensibles suivantes restent à leurs tickets respectifs.

Jeton initial : 256 bits aléatoires, empreinte SHA-256 unique en DB, purpose email_verification,
échéance absolue de 24 h à l’émission, vérifiée serveur avec UTC aware. Renvoi valide : révocation
des anciennes preuves et annulation/effacement de leurs emails encore en attente, même transaction.
Consommation sous verrou User : une seule réussite ; aucun mélange de générations ni délai glissant.
Le client reçoit le jeton par fragment de lien, le retire immédiatement de l’URL au bootstrap ou
hashchange et le garde uniquement en mémoire jusqu’à soumission. Pas de localStorage/sessionStorage,
jeton ou mot de passe dans les réponses/API logs. Un rechargement exige de rouvrir le lien email.

## Schéma et atomicité

Migration Accounts additive **p0001_accounts_registration**, après p0000 inchangée :

| Table | Rôle / contraintes |
| --- | --- |
| users | UUID global, email_key unique, état active/suspended, dates création/vérification |
| password_credentials | FK User unique, hash Argon2id et date de modification |
| account_tokens | FK User, digest unique, purpose, échéance ≤24 h, cohérence des états ; index unique partiel sur preuve active compte/purpose |
| email_outbox | FK User/token, token unique, payload chiffré, état/échéance/retry/tentatives et Message-ID stable |
| abuse_counters | Clé pseudonymisée opération/IP ou sujet + fenêtre horaire, incrément concurrent atomique |
| security_events | Événements minimaux compte/date/type, aucune donnée de credential ou contenu email |

Création User/credential/preuve/email/audit atomique ; l’email ne précède jamais le commit.
Unicité PostgreSQL gère les inscriptions concurrentes. Verrou User commun à renvoi, confirmation
et livraison, ordre User puis preuve/outbox ; les workers utilisent SKIP LOCKED pour d’autres comptes.
Les quotas sont committés séparément, y compris lors d’un refus ultérieur. Aucun accès Game DB.
Downgrade refusé si tables peuplées ; roundtrip autorisé uniquement dans les tests *_test.

Seuils initiaux configurables via PORTAL_REGISTRATION_IP_LIMIT (20/h), EMAIL_REQUEST_LIMIT (5/h),
VERIFICATION_IP_LIMIT (30/h), VERIFICATION_TOKEN_LIMIT (10/h). Les deux premières limites sont
partagées entre inscription et renvoi ; confirmation est une opération distincte. Fenêtres fixes
UTC, pas de verrouillage permanent du compte. Adresse réseau du pair par défaut ; X-Forwarded-For
accepté uniquement si le pair correspond au proxy explicitement configuré (local-edge en Compose),
une seule IP valide. Les clients directs ne choisissent pas leur identité réseau par un header.

## Livraison locale durable

portal-secrets-init crée une clé Fernet privée 0600, une seule fois dans portal_secrets ; API et worker
la lisent en montage read-only. Elle ne quitte pas Docker, n’est ni en DB, Git, logs ou frontend.
L’initialisation est idempotente ; ne pas supprimer ce volume : les emails en attente deviendraient
illisibles. Rotation/restauration des secrets de production à préparer avant déploiement.

Fernet protège le payload temporaire (destinataire/jeton) ; le worker revalide les bindings
outbox/User/token, digest et adresse courante avant envoi. Payload effacé après acceptation SMTP,
annulation ou expiration. Pas de payload ou exception SMTP privée journalisés.
Retry exponentiel borné à 300 s, sans repousser l’expiration. Le worker redémarre après panne Accounts ;
la file est PostgreSQL, pas en mémoire. Audit purgé après 90 jours ; compteurs anciens purgés ;
preuves de jetons conservées séparément, jamais supprimées par la purge de l’audit.

Le transport C02 autorise seulement smtp_local ou disabled. Compose emploie **Mailpit**, récepteur
de développement sans relais externe, réseau portal_mail interne ; SMTP non publié sur l’hôte.
La recherche automatique de nouvelles versions est désactivée sur ce réseau isolé.
Son interface contient les messages et leurs liens sensibles : http://127.0.0.1:8025, loopback seulement via local-edge (Host explicite 127.0.0.1).
Mailpit reste uniquement sur le réseau interne ; aucun port direct Mailpit publié.
Les messages de test sont gardés dans portal_mail_data (maximum 500) ; aucun fournisseur de production
n’est sélectionné. Ne pas employer de vrais credentials de production dans cette stack.

Acquittement SMTP ≠ remise finale au destinataire. Un crash après acceptation SMTP et avant commit
peut provoquer un doublon ; Message-ID stable, livraison au moins une fois, pas exactement une fois.
Les doublons ne rendent jamais un jeton consommable deux fois et ne prolongent pas sa durée.

```bash
docker compose up --build -d --wait --wait-timeout 180
docker compose exec -T portal-backend alembic check
docker compose ps -a
python3 scripts/smoke_portal_compose.py
```

Les deux migrate et portal-secrets-init sortent avec code 0 ; worker email running, Mailpit/API/DB
actifs. Recette backend : Ruff/pytest depuis portal/backend avec son propre lock ; intégrations
uniquement RUN_DB_TESTS=1 et PORTAL_POSTGRES_* vers une base dédiée *_test. Frontend : npm ci,
lint/test/build/test:e2e dans portal/frontend. Scénarios, résultats effectifs et limites dans progress.

C03 est la suite : appareils, connexion/session Portal et CSRF. C04/C05 porteront opérations sensibles
et MFA ; C06/C07 memberships/S2S/handoff ; C08/C09 complétion UI et recette. 5D non commencé.
Q48/Q49/Q55 conservent leurs reports ; aucune décision 5B n’a été modifiée.

Sources primaires : [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/parameters.html),
[Pwned Passwords](https://haveibeenpwned.com/API/v3#PwnedPasswords),
[Fernet](https://cryptography.io/en/latest/fernet/),
[email-validator](https://github.com/JoshData/python-email-validator),
[Mailpit Docker](https://mailpit.axllent.org/docs/install/docker/).
