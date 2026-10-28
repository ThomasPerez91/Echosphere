# Stratégie de tests

**Statut : fondation et premières contraintes persistantes testées ; gameplay futur.**

## Pyramide utile

- Règles pures : production, coûts, prérequis et décisions IA, sans HTTP ni DB.
- Services + PostgreSQL : transactions, contraintes, concurrence, idempotence, reprise après crash.
- API : contrats, autorisations et visibilité ; au bootstrap, les deux sondes seulement.
- UI : comportements perceptibles, erreurs et reprise ; responsive et clavier sur navigateur réel.
- Parcours intégrés : démarrage Compose, API prête, page et proxy ; puis parcours de dix minutes.

## Checks livrés

Backend : Ruff et 21 tests unitaires pour sondes, configuration et production exacte. Le succès de connexion est simulé dans le test unitaire ; cela ne
remplace pas le SELECT 1 réel du smoke Compose.
Frontend : ESLint, TypeScript strict, build Vite, trois tests Vitest (succès, panne/réessai, 503).
Documentation : script vérifiant les liens Markdown locaux et les fichiers obligatoires.
CI : jobs backend, frontend/documentation et smoke Docker avec PostgreSQL réel. Le smoke vérifie
la reprise après arrêt/redémarrage de PostgreSQL et préserve /health pendant l'indisponibilité.

## Intégrations PostgreSQL (étapes 1–2)

Le job backend utilise PostgreSQL 17 et une base `echosphere_test` jetable. Les tests vérifient
migrations aller/retour/aller, `alembic check`, liens inter-univers interdits, capacité négative,
double occupation, contrôleur invalide, dates UTC et rollback complet de transaction.
Sans `RUN_DB_TESTS=1`, ces tests sont explicitement ignorés, jamais présentés comme passés.
L'exécution est refusée si POSTGRES_DB ne finit pas par `_test` car un downgrade détruit les tables.

Pour les lancer en local, créer d'abord une base PostgreSQL dédiée, exporter POSTGRES_HOST/PORT,
POSTGRES_DB (suffixe `_test`), POSTGRES_USER et POSTGRES_PASSWORD, puis depuis backend :
`RUN_DB_TESTS=1 .venv/bin/pytest -q`. Ne jamais pointer ce test vers une base de jeu à conserver.
Le job Compose vérifie aussi les migrations dans l'image runtime et la reprise des connexions du pool.

## Temps et concurrence

Les tests de stream générique sans colonie, de scope inter-univers, de FK composites et de
backfill 0002 → 0003 → 0002 → 0003 complètent les scénarios précédents. Les downgrades non
représentables sont refusés sans perte de données.

Les intégrations temporelles utilisent des transactions réellement committées et des sessions
indépendantes. Elles effacent seulement les fixtures qu'elles créent dans la base *_test. Deux workers
sont coordonnés par des signaux threading, pas des sleeps de gameplay : pas de double exécution sur
la même colonie, progression d'une seconde colonie sous verrou de la première. Une BaseException
simule une perte du processeur avant commit ; on recrée le moteur avant/après commit pour vérifier
rejeu et absence de doublon. Cela ne remplace pas encore une campagne de fault injection OS.

L'horloge figée vérifie les taux segmentés à l'heure logique, événements enfants simultanés,
backoff, blocage/reprise, idempotence et rattrapage incomplet. Les tests purs comparent mille petites
lectures à une longue durée, vérifient microsecondes, capacité, overflow et refus de temps naïf/inversé.
Le job Compose applique 0002, vérifie l'absence de dérive et exécute aussi le CLI du worker.

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
