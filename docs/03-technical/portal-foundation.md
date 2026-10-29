# Socle Portal — C01 de l’étape 5C

**Statut : implémenté sur work/step-5c-portal-account-lobby / PR #7, non intégré à master.**
2026-10-29. Autorisation : poursuivre C01 après le cadrage présenté, instruction utilisateur « alors go ».
[Plan 5C](../05-project/step-5c-plan.md) · [Contrats 5B](identity-contracts.md) ·
[ADR 0008](../adr/0008-control-plane-game-data-plane.md).

## Périmètre livré

Backend Portal FastAPI/Python 3.12 séparé dans portal/backend/portal_app, configuration PORTAL_*,
engine/pool SQLAlchemy propres ; frontend Portal React/TypeScript/Vite dans portal/frontend.
Accounts PostgreSQL indépendant, rôle/secret/volume/réseau propres. Aucun import du domaine Game,
aucune connexion Portal à Game DB. Les services Game, leur volume et leurs migrations 0001–0004
restent à leur périmètre existant. Le proxy local est commun, pas une preuve d’isolation de charge.

Les seules routes Portal sont les sondes et la documentation FastAPI. Pas d’inscription, connexion,
MFA, session, handoff, membership, fixture ou commande gameplay. L’écran indique que comptes/lobby
sont en préparation ; readiness ne signifie pas compte connecté ou partie active. C02 est la suite.

| Route Portal via son origine | Réponse |
| --- | --- |
| GET /api/health | 200, status ok et service portal, sans accès DB |
| GET /api/ready | 200, status ready et service portal après SELECT 1 Accounts ; 503 générique si indisponible |
| GET /api/docs | Documentation locale des sondes, pas une API d’authentification |

### Migrations indépendantes

portal/backend/alembic.ini et migrations constituent une nouvelle chaîne dans Accounts DB.
**p0000_portal_baseline** initialise uniquement portal_alembic_version : aucun schéma de compte
anticipé. P0001 portera les entités C02 selon le cadrage ; aucune révision Game modifiée.
`alembic check` compare uniquement la metadata Accounts, indépendante et encore vide à C01.
Migrations avant démarrage de l’API, jamais au démarrage de chaque processus applicatif.
Roundtrip/downgrade uniquement sur base de test dédiée dont le nom finit par _test.

## Démarrage local

Les valeurs PORTAL_POSTGRES_DB/USER/PASSWORD de [.env.example](../../.env.example) sont publiques et
réservées au développement. Les valeurs par défaut Compose permettent un .env Game préexistant ;
ne pas l’écraser. Modifier un secret de configuration ne change pas un rôle dans un volume existant.

```bash
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose ps -a
docker compose exec -T portal-backend alembic current
docker compose exec -T portal-backend alembic check
docker compose exec -T backend alembic check
```

Services Portal ajoutés : portal-postgres, portal-migrate, portal-backend, portal-frontend et
local-edge. Les deux migrate sortent avec code 0 ; bases/APIs/frontends healthy ; Game worker running.
Aucun port Accounts/API/frontend Portal n’est publié directement. local-edge écoute seulement
127.0.0.1:8443 ; les anciens ports Game 8000/5173 restent disponibles pour diagnostic local.

- Portal : https://portal.echosphere.localhost:8443 ; /api/* relayé uniquement vers Portal.
- Game : https://game.echosphere.localhost:8443 ; frontend Game et son proxy /api existant.

Le parent echosphere.localhost commun permet deux origines distinctes du même site navigateur,
nécessaire au contrat 5B. Un test Chromium sur serveur HTTP local réel vérifie Sec-Fetch-Site: same-site entre ces hôtes
sous un même schéma ; le smoke vérifie séparément les deux origines HTTPS effectives.

Certains résolveurs WSL2 ne résolvent pas les sous-domaines .localhost. Les tests ouvrent la connexion
sur 127.0.0.1 en vérifiant le certificat pour le nom attendu. Pour curl, utiliser --resolve.
Les hôtes navigateur peuvent nécessiter une résolution locale explicite selon l’environnement ;
aucune modification de hosts ou de magasin de certificats hôte n’est effectuée automatiquement.

### Certificat de développement

Caddy utilise `tls internal`, admin désactivée et `skip_install_trust`. Sa CA et ses clés sont dans
les volumes Docker local_tls_data/local_tls_config ; aucune clé n’est exportée ou committée.
Il n’y a aucun appel ACME public. Le navigateur doit faire confiance explicitement à cette CA pour
une connexion sans avertissement ; le projet ne modifie pas le magasin Windows/WSL2.
Exporter **seulement le certificat public** pour un client de test :

```bash
mkdir -p .local
docker compose cp local-edge:/data/caddy/pki/authorities/local/root.crt .local/portal-root.crt
curl --noproxy '*' --cacert .local/portal-root.crt \
  --resolve portal.echosphere.localhost:8443:127.0.0.1 https://portal.echosphere.localhost:8443/api/ready
```

.local est ignoré par Git et les builds Game. Ne pas utiliser -k ou désactiver globalement la
vérification TLS. Cette CA locale n’est pas une configuration de production. Les origines locales
préparent les cookies host-only et WebAuthn futurs sans prétendre les implémenter.

## Frontières de réseau et configuration

portal-postgres est uniquement sur portal_db (interne) ; portal-backend sur portal_db/portal_web ;
portal-frontend sur portal_web. local-edge rejoint portal_web et le réseau Game existant pour les
deux origines web. Il n’est pas l’interface interne mTLS Portal→Game, réservée à C06.
Les paramètres POSTGRES_* de Game ne configurent pas Portal : seul PORTAL_POSTGRES_* est lu.
Pool Portal initial 3 connexions, max_overflow 0, timeout de pool 3 s ; paramètres bornés,
connexion 3 s et statement timeout 3000 ms par défaut. Secrets masqués par SecretStr/URL structurée
et hide_parameters. Pas de SQLAlchemy Base partagée.

Chaque frontend appelle sa propre API même origine. Aucun middleware CORS permissif ; CORS du
serveur Vite Portal désactivé. Aucun credential, cookie de session ou secret localStorage dans C01.
Les protections CSRF/session de 5B seront livrées avec leurs routes dépendantes, pas simulées ici.

## Validation et maintenance

```bash
python3 scripts/check_docs.py
python3 scripts/smoke_portal_compose.py
python3 scripts/smoke_compose.py
```

Les deux smoke arrêtent/redémarrent temporairement des bases ; les lancer sur environnement local
de recette. Le smoke Portal vérifie TLS avec la CA publique chargée en mémoire, noms de certificats,
routage, réponses CORS, historiques distincts et panne/reprise Accounts puis Game. Pas de suppression
de données/volumes. Il doit être exécuté avant C02 : son assertion « Accounts sans tables métier »
sera alors adaptée au schéma réellement livré.

Backend Portal natif : mêmes commandes Ruff/pytest que Game, depuis portal/backend avec sa propre
venv et requirements-dev.lock. Tests DB activés par RUN_DB_TESTS=1 et PORTAL_POSTGRES_* vers une
base Accounts dédiée *_test ; le roundtrip ne doit jamais cibler echosphere_accounts à conserver.
Frontend Portal : npm ci, npm run lint, npm test, npm run build, puis installation Chromium et
npm run test:e2e depuis portal/frontend. Les captures sont des artefacts ignorés, pas des fixtures runtime.

Pins Python initiaux dérivés du même jeu de dépendances validé que Game, maintenus dans deux locks
Portal autonomes. Aucun nouvel outil d’auth C01. Lock npm Portal indépendant, Vitest 4.1.12 au premier
checkpoint ; npm 12 a généré le lock après erreur interne du résolveur npm 10, npm ci de l’image Node 22
l’a ensuite consommé avec succès. Versions et résultats exacts dans progress ; pas de changement du
lock Game ni correction implicite de ses avis de sécurité historiques.

CI : jobs portal-backend (PostgreSQL test dédié) et portal-frontend ; compose-smoke étendu avec
migrations Portal et smoke HTTPS croisé. Jobs Game conservés. Les résultats effectifs de la tête
publiée sont à lire dans la PR, pas déduits de la présence du workflow.

## Limites

C01 n’est ni un Portal de production ni 5C terminé. Pas de compte, hash Argon2id, jeton email,
session, CSRF métier, MFA, outbox, mTLS S2S, accès Game ou API Colony. Pas de catalogue/join public,
partie générée ou identité factice. Aucune décision Qxx changée.
Tests Chromium C01 : UI avec sondes interceptées sur Vite HTTP ; TLS/routage/pannes sont testés
séparément et réellement par le smoke HTTPS. Pas de recette graphique Windows, confiance navigateur
hôte, tactile/lecteur d’écran, charge ou isolation CPU/RAM démontrée. Comptes et parcours HTTPS
complets seront testés avec leurs implémentations, sans ignorer les erreurs TLS en production.

Sources primaires consultées pour les choix techniques :
[Caddy TLS](https://caddyserver.com/docs/caddyfile/directives/tls),
[options Caddy](https://caddyserver.com/docs/caddyfile/options),
[réseaux Compose](https://docs.docker.com/compose/how-tos/networking/),
[pool SQLAlchemy](https://docs.sqlalchemy.org/en/20/core/pooling.html),
[Alembic](https://alembic.sqlalchemy.org/en/latest/cookbook.html),
[Vite](https://vite.dev/config/server-options.html), [Vitest](https://vitest.dev/guide/) et
[Sec-Fetch-Site](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Site).
