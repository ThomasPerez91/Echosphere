# Echosphere

Jeu de stratégie spatiale persistant dans un navigateur : développer un empire, explorer une galaxie
partiellement inconnue et rencontrer des civilisations IA qui suivent les mêmes règles que les humains.
Une préparation d'environ dix minutes par jour ; des sessions longues pour mieux décider, sans
rendement lié à la présence. Aucun bouton de récolte, aucun pay-to-win.

**État actuel : étape 0 — documentation et bootstrap de développement. Aucun gameplay implémenté.**

## Démarrage ce soir sous WSL2

Prérequis : Git, Docker Desktop démarré avec intégration WSL2 pour votre distribution et
Docker Compose v2 récent. Garder les ports 5173 et 8000 disponibles. Aucun Python/Node hôte requis
pour lancer les trois services.

```bash
mkdir -p ~/projects
cd ~/projects
git clone --branch work/step-0-bootstrap https://github.com/ThomasPerez91/Echosphere.git
cd Echosphere
cp .env.example .env
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Si la branche n'est pas encore publiée, suivre le rapport de livraison avant la commande clone.
Le premier build télécharge les images et dépendances. Attendre les trois statuts healthy ; les
healthchecks conditionnent l'ordre postgres → backend → frontend. Pour attendre automatiquement :
`docker compose up --build -d --wait --wait-timeout 180`.

Depuis Windows :

| URL | Résultat attendu |
| --- | --- |
| http://localhost:5173 | Echosphere, Development build, Backend: connected |
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

| Service | Technologie | Rôle étape 0 |
| --- | --- | --- |
| frontend | React, TypeScript strict, Vite, Node 22 | Placeholder responsive et test de readiness via proxy |
| backend | Python 3.12, FastAPI, psycopg | Liveness et SELECT 1 PostgreSQL ; aucune table métier |
| postgres | PostgreSQL 17 | Source de vérité future, volume persistant local |

Pas de Redis, auth, moteur d'événements, modèles métier ou WebSockets.
SQLAlchemy et Alembic seront introduits avec la fondation/persistance métier.

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
game_data/               Répertoire réservé à l'équilibrage futur
docs/                    Vision, game design, UX, technique, qualité, roadmap et ADR
scripts/                 Vérification documentaire et smoke Compose
.github/workflows/       CI backend, frontend et Compose
```

## Lire et contribuer

- [Documentation et statuts](docs/README.md) · [Vision et non-goals](docs/00-product-vision.md).
- [Architecture](docs/03-technical/architecture.md) · [Modèle temporel futur](docs/03-technical/event-engine.md).
- [Roadmap complète](docs/05-project/roadmap.md) · [Questions ouvertes](docs/05-project/open-questions.md).
- [CONTRIBUTING](CONTRIBUTING.md) · [AGENTS](AGENTS.md) · [Definition of Done](docs/04-quality/definition-of-done.md).

En cas de panne : vérifier `docker version`, `docker compose version` et l'intégration WSL2, puis
les logs/healthchecks. Les changements d'identifiants PostgreSQL ne s'appliquent pas automatiquement
à un volume déjà initialisé. La procédure et les limites sont dans [exécution locale](docs/03-technical/deployment.md).
