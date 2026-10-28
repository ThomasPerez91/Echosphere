# Instructions pour les agents — Echosphere

## Mission et état du dépôt

Jeu de stratégie spatiale persistant, web responsive, solo cible et coopération post-MVP.
Étape 0 fusionnée sur master (PR #1). Lot courant : étape 3, moteur temporel pour une colonie, après la fondation des étapes 1–2. Lire [context.md](context.md) puis [progress.md](progress.md) au début d'une reprise.
Mettre progress.md à jour avant chaque livraison avec périmètre, tests, limites et prochaine action.
Ne pas implémenter de nouvelle étape sans périmètre explicite. Le socle temporel est implémenté ; auth complète,
IA, combat, Redis, WebSocket, paiement et administration ne sont pas encore livrés.

## Sources de vérité à lire

1. [Vision/non-goals](docs/00-product-vision.md) et [statuts](docs/README.md).
2. [Questions ouvertes](docs/05-project/open-questions.md), [roadmap](docs/05-project/roadmap.md).
3. [Architecture](docs/03-technical/architecture.md), [temps](docs/03-technical/event-engine.md),
   [calcul des ressources](docs/03-technical/resource-calculation.md), [sécurité](docs/03-technical/security.md).
4. Documentation du domaine modifié et [ADR](docs/adr/README.md).
5. [Definition of Done](docs/04-quality/definition-of-done.md).

Ne pas relire une conversation pour inventer une règle absente : identifier une question ouverte.
Les assets/mockups ne sont pas des spécifications métier. Trois ressources principales seulement :
Alliages, Flux, Données (noms de travail). IA sans LLM et sans triche, mêmes services que l'humain.
Préparation quotidienne autour de dix minutes, aucun bouton de récolte, pas de pay-to-win.

## Architecture et structure

Monolithe modulaire, aucun microservice. Frontend React/TypeScript/Vite ; backend Python/FastAPI ;
PostgreSQL source de vérité. SQLAlchemy 2 et Alembic sont utilisés pour la persistance versionnée.
`backend/app/api/` contient HTTP, `core/` la configuration, `persistence/` les modèles et sessions ;
`backend/app/simulation/` porte le temps et le worker ; `backend/migrations/` porte les migrations, `backend/tests/` les tests ; `frontend/src/` les vues et tests ;
`game_data/` réservera les valeurs d'équilibrage ; `docs/` les références ; `scripts/` les checks ;
`.github/workflows/ci.yml` les jobs qualité. Pas de couche métier générique à créer pour deux probes.

## Invariants obligatoires

- Backend autoritaire : vérifier propriété, prérequis, stocks, routes et échéances côté serveur.
- Aucun calcul métier critique dans le navigateur ; estimations UI uniquement, réconciliées au serveur.
- PostgreSQL conserve états et échéances ; un cache ou timer mémoire n'est jamais l'autorité.
- UTC partout en stockage/calcul ; timestamps avec fuseau, conversion locale à l'affichage.
- Production différée et événements persistants : utiliser app/simulation, pas de scheduler parallèle.
- Prendre le verrou timeline, respecter due_at/séquence et complete=True avant une future dépense.
- Ressources en micro-unités entières, taux horaires et reste persisté ; jamais de float critique.
- Handler sans commit, effet externe ou verrou d’une autre colonie ; rollback atomique sur échec.
- Humain et IA utilisent les mêmes commandes et une connaissance limitée.
- Mobile obligatoire ; pas de simple dashboard réduit, pas d'action importante seulement au hover.
- Ne pas ajouter une feature non spécifiée sans documenter sa portée et son statut ; rester dans
  l'étape autorisée. Une documentation prospective n'autorise pas son implémentation immédiate.

## Conventions

Code et identifiants anglais, documentation principale en français, noms de fichiers kebab-case.
Python snake_case, annotations publiques, Ruff ; React composants PascalCase et TypeScript strict.
Petites fonctions et frontières explicites. Valeurs d'équilibrage futures séparées du moteur.
Secrets via environnement, jamais dans Git ni variables frontend exposées. Lockfiles committés.
Chaque décision métier modifiée entraîne mise à jour du document de référence, du registre et des
tests ; ADR pour décision structurelle. Signaler hypothèses, ne pas fermer silencieusement une Qxx.

## Commandes principales

```bash
cp .env.example .env
docker compose up --build -d --wait --wait-timeout 180
docker compose ps
docker compose exec backend alembic upgrade head
docker compose exec backend alembic check
python3 scripts/smoke_compose.py
docker compose down
python3 scripts/check_docs.py
(cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q)
(cd frontend && npm ci && npm run lint && npm test && npm run build)
```

Installation native et commandes Docker de test : [README](README.md) et
[stratégie de tests](docs/04-quality/testing-strategy.md). Ne pas lancer `down -v` sur des données
à conserver. Pas de port PostgreSQL hôte dans Compose.

## Tests et recette

Tests obligatoires pour le comportement ajouté/modifié. Couvrir refus métier et erreurs, puis
concurrence, idempotence et reprise selon le domaine. Horloge injectée pour le futur moteur ; pas
de sleeps de durée gameplay. Tester l'accessibilité et responsive pour les vues touchées.
Exécuter lint/tests/build et check docs. Docker modifié : smoke Compose avec DB réelle si disponible.
Rapporter toute vérification impossible, sans affirmer qu'une CI simplement configurée a réussi.
Appliquer la Definition of Done avant de déclarer une étape terminée.

## Git et livraison

`develop` est la branche d'intégration de référence. Toute nouvelle branche part du dernier develop ;
les PR de développement ciblent develop. Si une dépendance validée en CI attend sa revue, une branche
créée depuis develop peut intégrer ses commits sans fusionner sa PR ; noter la dépendance explicitement
sur la nouvelle PR. Ne pas contourner l'examen en fusionnant develop ou master sans instruction. `master` contient les versions destinées aux releases.
Une promotion develop → master, un tag ou une publication requiert une instruction de release.
L'autorisation de fusionner PR #1 était ponctuelle ; ne pas en déduire une autorisation permanente.

```bash
git switch develop
git pull --ff-only origin develop
git switch -c work/nom-du-lot
```

Commits cohérents, pas de force push, de réécriture partagée, de secrets ou de fichiers générés.
Lire l'état distant avant toute mutation et préserver le travail existant. Décrire les tests réels
sur la PR, vérifier la CI avant d'annoncer le lot validé ; laisser la PR à examiner sauf instruction
de fusion. Mettre à jour contexte/progression sans y copier secrets, logs complets ou hypothèses
présentées comme décisions. Ne jamais annoncer un push ou une PR qui n'existe pas.
