# Echosphere

Jeu de stratégie spatiale persistant dans un navigateur : développer un empire, explorer une galaxie
partiellement inconnue et rencontrer des civilisations IA qui suivent les mêmes règles que les humains.
Une préparation d'environ dix minutes par jour ; des sessions longues pour mieux décider, sans
rendement lié à la présence. Aucun bouton de récolte, aucun pay-to-win.

**État actuel : domaine Colony/économie v0.1 et shell Game intégrés ; Portal C01–C08 sur PR #7 : comptes, sessions, opérations sensibles, MFA, lobby, contrôle privé mTLS et handoff/sessions Game,
sans API gameplay ni partie jouable.**

Socle Portal séparé : https://portal.echosphere.localhost:8443 ; Game : https://game.echosphere.localhost:8443.
Certificat local à approuver explicitement et recette : [Portal C01](docs/03-technical/portal-foundation.md).

Lire [AGENTS.md](AGENTS.md), [context.md](context.md), [progress.md](progress.md), puis
[la passation](docs/06-handoff/README.md) pour reprendre sans historique de chat. ChatGPT Work,
Codex et Claude Code suivent le même [protocole de collaboration et de revue croisée](docs/06-handoff/work-codex-handoff.md) ;
[CLAUDE.md](CLAUDE.md) importe seulement AGENTS.md.
`master` est l’intégration stable. Nouvelles branches courtes `work/...` depuis master, PR vers master,
CI/revue et merge sur autorisation ; tags et releases identifiées plus tard.

## Démarrage local sous WSL2

Recette locale réalisée le 29/10/2026 ; preuves et limites dans [progress](progress.md), sans
recette graphique Windows attestée.

Prérequis : Git, Docker Desktop démarré avec intégration WSL2 pour votre distribution et
Docker Compose v2 récent. Garder les ports 5173 et 8000 disponibles, plus 8443 (HTTPS local
Portal/Game) et 8025 (Mailpit) sur la branche de PR #7. Aucun Python/Node hôte requis pour lancer
la pile locale. Démarrage avec Portal, alembic des deux bases et trois smokes :
[protocole de collaboration](docs/06-handoff/work-codex-handoff.md#démarrage-local-frais-codex--claude-code).

```bash
mkdir -p ~/projects
cd ~/projects
git clone --branch master https://github.com/ThomasPerez91/Echosphere.git
cd Echosphere
cp .env.example .env
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose exec backend alembic upgrade head
docker compose exec backend alembic check
```

Ces commandes utilisent master, la base d’intégration stable. Pour tester une PR non fusionnée,
choisir sa branche avant le build ; toutes les nouvelles branches partent de master.
Le premier build télécharge les images et dépendances. Postgres, backend et frontend doivent être healthy ; worker running et migrate terminé avec code 0.
L'ordre est postgres → migrate → API/worker → frontend. Pour attendre automatiquement :
`docker compose up --build -d --wait --wait-timeout 180`.

Depuis Windows :

| URL | Résultat attendu |
| --- | --- |
| http://localhost:5173 | Shell Echosphere sans partie active ; Services disponibles si /ready répond |
| http://localhost:8000/health | 200, `{"status":"ok"}` |
| http://localhost:8000/ready | 200, `{"status":"ready"}` avec PostgreSQL disponible |
| http://localhost:8000/docs | OpenAPI des deux sondes |

```bash
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
docker compose logs --tail=100 backend frontend postgres
# Test intégré, y compris arrêt/reprise temporaire de la DB :
python3 scripts/smoke_compose.py
# Arrêt, données PostgreSQL conservées :
docker compose down
```

Ne pas utiliser `down -v` sauf pour effacer volontairement les données locales.
PostgreSQL n'expose aucun port hôte. Les ports web sont liés à 127.0.0.1. Les valeurs de .env.example
sont publiques et réservées au développement ; ne jamais committer .env ni utiliser ces valeurs
pour un serveur public. Ne pas exposer Vite sur internet.

## Services et commandes de qualité

| Service | Technologie | Rôle actuel |
| --- | --- | --- |
| frontend | React, TypeScript strict, Vite, Node 22 | Navigation responsive, sections en préparation et readiness via proxy |
| backend | Python 3.12, FastAPI, SQLAlchemy, psycopg, Alembic | Sondes, modèles et domaine économique interne, sans endpoint métier |
| postgres | PostgreSQL 17 | Source de vérité et volume persistant local |
| migrate | Même image backend | Alembic upgrade head, puis sortie 0 |
| worker | Même code backend | Streams temporels multi-univers, sans port publié |
| portal-postgres / portal-migrate | Accounts PostgreSQL 17 / Alembic indépendant | Historique p0000–p0005, comptes/preuves email et sessions Portal |
| portal-backend / portal-frontend | FastAPI / React-Vite séparés | Sondes Accounts et écran de préparation |
| local-edge | Caddy, HTTPS local | Origines Portal/Game :8443, CA Docker sans installation hôte |

Le worker est un autre processus du même monolithe : événements SQL idempotents, production exacte
et reprise après redémarrage. Les valeurs v0.1 sont dans game_data, mais aucune colonie/partie n’est injectée au démarrage.
Compose applique les migrations via le service migrate avant API/worker. /ready vérifie la connexion,
pas l'état de progression du worker. Pas de Redis, auth ou WebSockets.

```bash
# Qualité dans les images de développement :
docker compose run --rm --no-deps frontend sh -c 'npm run lint && npm test && npm run build'
# Le backend runtime ne contient pas les outils de test : conteneur éphémère avec extra dev.
docker compose run --rm --no-deps --user root -v "$PWD/backend/tests:/app/tests:ro" backend sh -c 'pip install -r requirements-dev.lock && pytest -q && ruff check app tests'
```

Les commandes natives et les détails CI sont dans la [stratégie de tests](docs/04-quality/testing-strategy.md).
Les dépendances sont figées par package-lock.json et requirements*.lock. La CI vérifie lint/tests/build,
liens documentaires et un vrai démarrage Compose. Son résultat doit être consulté sur la PR.

## Structure

```text
backend/                 FastAPI, probes, tests, Dockerfile et dépendances figées
frontend/                React + TypeScript + Vite, tests et Dockerfile
game_data/               Ruleset économique v0.1 validé et versionné
docs/                    Vision, game design, UX, technique, qualité, roadmap et ADR
scripts/                 Vérification documentaire et smoke Compose
.github/workflows/       CI backend, frontend et Compose
```

## Examiner le temps et les incidents

```bash
docker compose logs --tail=100 worker migrate
docker compose exec worker python -m app.simulation.worker --blocked --limit 50
docker compose exec worker python -m app.simulation.worker --once --limit 50
```

La file est vide tant qu'aucun service métier n'a créé de colonie/ordre : aucun événement ou ressource
n'est injecté pour une démo. Contrats, retries et reprise explicite : [moteur temporel](docs/03-technical/event-engine.md).

## Instances de jeu futures

Universe représente une instance isolée, pas un utilisateur : MVP solo avec IA, puis parties privées
et univers multijoueurs persistants. Seuls les invariants sont documentés ; comptes, memberships,
invitations, modes, équipes et règles multijoueurs ne sont pas implémentés.
Voir [modes de jeu](docs/01-game-design/game-modes.md).

## Lire et contribuer

- [Documentation et statuts](docs/README.md) · [Vision et non-goals](docs/00-product-vision.md).
- [Architecture](docs/03-technical/architecture.md) · [Modèle temporel](docs/03-technical/event-engine.md).
- [Roadmap complète](docs/05-project/roadmap.md) · [Questions ouvertes](docs/05-project/open-questions.md).
- [CONTRIBUTING](CONTRIBUTING.md) · [AGENTS](AGENTS.md) · [Definition of Done](docs/04-quality/definition-of-done.md).

En cas de panne : vérifier `docker version`, `docker compose version` et l'intégration WSL2, puis
les logs/healthchecks. Les changements d'identifiants PostgreSQL ne s'appliquent pas automatiquement
à un volume déjà initialisé. La procédure et les limites sont dans [exécution locale](docs/03-technical/deployment.md).

## Domaine Colony — Étape 5A

Services internes dans backend/app/colony : configure_universe, initialize_colony, enqueue et cancel.
[game_data](game_data/README.md) fournit les valeurs v0.1, [économie](docs/01-game-design/colony-economy-v0.1.md)
les contrats et [ADR 0007](docs/adr/0007-colony-economy.md) la persistance/scheduler. Transaction du
caller et scope univers/empire explicites ; aucune commande ne remplace une authentification HTTP.
Le contexte de build backend est la racine pour embarquer game_data ; utiliser Docker Compose.
Aucun seed/demo runtime : l’UI Colony réserve ses quatre sections et indique l’absence de partie.
[Défense planétaire](docs/01-game-design/planetary-defense.md) documentée, sans effet actif.

## Architecture cible et reprise durable

**Décision validée, réalisation C01–C08 sur PR #7, non intégrée** : [ADR 0008](docs/adr/0008-control-plane-game-data-plane.md)
sépare Portal Control Plane (compte global/lobby, Accounts DB) et Game Data Plane (backend actuel,
Game DB). Plusieurs parties par compte ; interface interne contrôlée, jamais SQL Portal→Game DB.
Handoff court/unique puis GameSession autonome, gameplay direct à Game. Le lot documentaire 5B
n’a livré ni Portal, login, protocole d’auth ni changement Compose ; C01 est décrit séparément.

[Procédure locale et relais](docs/06-handoff/work-codex-handoff.md),
[sources/statuts](docs/06-handoff/source-map.md) et [prochain lot](docs/05-project/roadmap.md) :
5B contrats identité/Portal-Game → 5C compte/lobby selon cadrage → 5D API Colony sécurisée/UI réelle.
PR #5 fusionnée sur master 8214e0b ; recette locale effectuée le 2026-10-29, limites dans progress.
Les [contrats 5B](docs/03-technical/identity-contracts.md) sont validés et consolidés ; C02–C08 en implémentent les premiers sous-ensembles.
5B documentaire terminé et intégré à master via PR #6, merge `63bb7d1`. Contrats toujours non
implémentés. Lot courant : 5C sur `work/step-5c-portal-account-lobby`, checkpoint/cadrage effectués
puis socle C01 implémenté sur PR #7 ; aucune API Colony 5D commencée.
Le [registre Q40–Q56](docs/05-project/open-questions.md) distingue décisions closes, détails techniques
délégués et reports support/email/modes. Aucun nouveau code d’authentification dans 5B. Sur PR #7, C01 ajoute le socle Portal et étend
Compose ; [C02](docs/03-technical/portal-registration.md) ajoute inscription, Argon2id, vérification et livraison locale durable ; [C03](docs/03-technical/portal-sessions.md) ajoute connexion/sessions et CSRF ; [C04](docs/03-technical/portal-account-security.md) ajoute step-up, reset/changements sensibles et logout global sans MFA ; [C05](docs/03-technical/portal-mfa.md) ajoute TOTP/WebAuthn, secours et récupération limitée ; [C06](docs/03-technical/portal-game-control.md) livre lobby, synchronisation et révocations mTLS ; handoff/GameSession C07 livrés sur PR #7. [Recette C01](docs/03-technical/portal-foundation.md).
