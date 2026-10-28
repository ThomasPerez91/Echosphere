# Stratégie de tests

**Statut : bootstrap implémenté ; couverture métier future.**

## Pyramide utile

- Règles pures : production, coûts, prérequis et décisions IA, sans HTTP ni DB.
- Services + PostgreSQL : transactions, contraintes, concurrence, idempotence, reprise après crash.
- API : contrats, autorisations et visibilité ; au bootstrap, les deux sondes seulement.
- UI : comportements perceptibles, erreurs et reprise ; responsive et clavier sur navigateur réel.
- Parcours intégrés : démarrage Compose, API prête, page et proxy ; puis parcours de dix minutes.

## Checks livrés

Backend : Ruff et trois tests pytest pour liveness indépendante de la DB, readiness positive,
readiness 503 sans fuite d'erreur. Le succès de connexion est simulé dans le test unitaire ; cela ne
remplace pas le SELECT 1 réel du smoke Compose.
Frontend : ESLint, TypeScript strict, build Vite, trois tests Vitest (succès, panne/réessai, 503).
Documentation : script vérifiant les liens Markdown locaux et les fichiers obligatoires.
CI : jobs backend, frontend/documentation et smoke Docker avec PostgreSQL réel. Le smoke vérifie
la reprise après arrêt/redémarrage de PostgreSQL et préserve /health pendant l'indisponibilité.

## Commandes sans Docker

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.lock
backend/.venv/bin/pip install --no-deps -e backend
(cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q)
(cd frontend && npm ci && npm run lint && npm test && npm run build)
python3 scripts/check_docs.py
```

Les commandes Docker figurent dans le README. Les fichiers requirements*.lock figent les dépendances
Python directes/transitives ; package-lock.json fige celles de npm. Réviser les mises à jour avec
les checks complets. Les tests de comportement sont prioritaires sur les snapshots de composants.

## Validation future du temps

Horloge injectée, aucun sleep long pour attendre une construction. Tester exécution répétée,
événements simultanés, rattrapage après absence et crash avant/après commit. Les simulations
headless consignent seeds et versions. Définir les seuils de balance avant d'interpréter un résultat.

Voir [Definition of Done](definition-of-done.md), [événements](../03-technical/event-engine.md),
[balance](../01-game-design/balance-philosophy.md).
