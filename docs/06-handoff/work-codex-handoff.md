# Reprise et relais Work ↔ Codex local

**Statut : procédure commune validée ; environnement Windows/WSL2 non testé dans cette mission.**
Les agents partagent GitHub, pas leur mémoire ni nécessairement un disque, des processus ou secrets.
La qualité attendue est identique dans les deux environnements.

## Prendre le relais sans perdre le travail

1. Lire GitHub réel : PR, base/head/SHA, branches, CI et éventuels commentaires de revue. La présence
   d’une branche locale ne prouve ni publication ni merge. Exemple CLI si gh est disponible :
   `gh pr view 5 --repo ThomasPerez91/Echosphere --json state,baseRefName,headRefName,headRefOid,mergeable,statusCheckRollup`.
   Sinon consulter la PR sur GitHub ou via la connexion Work ; ne pas demander de token dans le chat.
2. Avant synchronisation, `git status --short --branch` puis `git fetch origin`. Travail non committé,
   tête divergente ou modification de l’autre environnement : préserver et examiner le diff ; ne
   pas reset/force-push/stash automatique ou démarrer deux modifications concurrentes du même lot.
3. PR #5 encore ouverte et mission sur cette branche : reprendre la branche existante, **pas de PR #6**.
   Pour un clone neuf de la PR :

```bash
git clone --branch work/step-5a-colony-domain https://github.com/ThomasPerez91/Echosphere.git
cd Echosphere
git status --short --branch
git fetch origin
git pull --ff-only origin work/step-5a-colony-domain
```

4. Lire AGENTS → context → progress → docs/06-handoff/README → roadmap → open-questions → docs du lot.
   Identifier le dernier commit publié et ce qu’il a réellement vérifié, quel que soit l’agent.
5. Après fusion future de #5, un **nouveau lot autorisé** repart de master synchronisée sur une
   branche work/... dédiée. Aucun merge, suppression de branche ou changement de base implicite.

## Démarrage frais après fusion future de PR #5

Cible : Windows 11 → Ubuntu WSL2 → VS Code → Docker Desktop avec intégration de la distribution →
Codex local ; ChatGPT Desktop éventuellement. Utiliser le filesystem Linux de WSL2, par exemple
~/projects. Préparer Git, Docker/Compose v2 et les ports 5173/8000 ; aucune installation Python/Node
hôte n’est nécessaire au lancement Compose. Le projet ne fournit pas d’installeur de ces outils.

```bash
git clone https://github.com/ThomasPerez91/Echosphere.git
cd Echosphere
cp .env.example .env
docker compose up --build -d --wait --wait-timeout 180
docker compose ps
```

Ces commandes sur master ne donnent 5A/passation **qu’après leur fusion effective**. Avant cela,
utiliser la branche #5 ci-dessus. Ne pas écraser un .env existant lors d’un relais. Les identifiants
de développement sont publics, ne pas les réutiliser pour une exposition distante.

Ouvrir http://localhost:5173, /health et /ready sur http://localhost:8000, documentation locale
http://localhost:8000/docs. Attendu : shell sans partie active, « Services disponibles » si ready ;
postgres/backend/frontend healthy, worker running et migrate exited(0) avec `docker compose ps -a`.
Aucun univers, stock ou bâtiment n’est injecté automatiquement. Pas de Portal/Accounts DB dans Compose.

```bash
python3 scripts/check_docs.py
docker compose exec backend alembic check
python3 scripts/smoke_compose.py
docker compose down
```

Le smoke arrête/redémarre temporairement PostgreSQL pour tester panne/reprise ; l’exécuter sur
l’environnement local de test. `down` conserve le volume ; `down -v` détruit les données et ne fait
pas partie du relais normal. Migrations/diagnostic : [déploiement](../03-technical/deployment.md).

## Vérifications identiques Work / Codex

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.lock
backend/.venv/bin/pip install --no-deps -e backend
(cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q)
(cd frontend && npm ci && npm run lint && npm test && npm run build)
(cd frontend && npx playwright install chromium && npm run test:e2e)
python3 scripts/check_docs.py
```

Cette exécution backend native ignore les intégrations sans RUN_DB_TESTS=1. Pour les activer,
exporter les variables POSTGRES_* vers une **base dédiée dont le nom finit par _test**, puis lancer
`RUN_DB_TESTS=1 .venv/bin/pytest -q` depuis backend. Ne pas pointer la suite de migrations vers les
données de partie : elle effectue des downgrades. La CI réalise cela avec PostgreSQL 17 jetable.
Des commandes de test Docker existent au [README](../../README.md) et dans la
[stratégie](../04-quality/testing-strategy.md). Aucun test ignoré n’est déclaré réussi.

Mission documentaire seule : check docs, liens/index et diff de périmètre suffisent en local ; la CI
existante reste à observer. Ne pas modifier code/tests/Compose pour faciliter la passation. Si Work
ne dispose pas de Docker, consigner cette limite et utiliser les résultats GitHub sans les appeler
« tests locaux ». Pour une modification fonctionnelle future, appliquer toute la DoD concernée.

## Work → Codex, puis Codex → Work

| Avant de céder la main | Work vers local | Local vers Work |
| --- | --- | --- |
| Écrire le checkpoint | progress : objectif, fichiers, décisions/statuts, tests/limites, questions, prochaine action | Même contenu et mêmes références canoniques |
| Publier | Commits cohérents puis push/connexion GitHub ; mettre à jour la PR existante | Commit/push de la branche, PR existante ou nouvelle seulement selon le lot |
| Vérifier | Relire SHA distant et CI de cette tête | Même vérification, pas seulement le succès de git push |
| Reprendre | Codex fetch/pull --ff-only de la branche puis relit les docs | Work vérifie GitHub puis lit la nouvelle tête et les docs |

Le dernier checkpoint durable est le commit publié dont la CI est identifiée dans progress, pas
la dernière réponse du chat. Nommer l’environnement de travail si connu ; ne pas inventer le nom
de l’autre agent. Autorisations limitées au lot ; publier une PR n’autorise pas à la fusionner.
Confidentialité : aucune conversation brute, .env, credential, identifiant privé ou donnée personnelle
à committer. Une nouvelle décision utilisateur est synthétisée et qualifiée, jamais collée en bloc.
