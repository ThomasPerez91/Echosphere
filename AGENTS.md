# Instructions pour les agents — Echosphere

## Mission et état du dépôt

Jeu de stratégie spatiale persistant, web responsive, solo cible et coopération post-MVP.
Étape 0 : documentation, probes, placeholder et Docker seulement. Ne pas anticiper une étape sans
instruction. Ni auth complète, modèles métier, moteur temporel, IA, combat, WebSocket, Redis,
paiement ou administration dans ce bootstrap.

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
PostgreSQL source de vérité. SQLAlchemy/Alembic prévus quand les modèles seront introduits.
`backend/app/` contient le serveur, `backend/tests/` les tests ; `frontend/src/` les vues et tests ;
`game_data/` réservera les valeurs d'équilibrage ; `docs/` les références ; `scripts/` les checks ;
`.github/workflows/ci.yml` les jobs qualité. Pas de couche métier générique à créer pour deux probes.

## Invariants obligatoires

- Backend autoritaire : vérifier propriété, prérequis, stocks, routes et échéances côté serveur.
- Aucun calcul métier critique dans le navigateur ; estimations UI uniquement, réconciliées au serveur.
- PostgreSQL conserve états et échéances ; un cache ou timer mémoire n'est jamais l'autorité.
- UTC partout en stockage/calcul ; timestamps avec fuseau, conversion locale à l'affichage.
- Production différée et événements transactionnels, idempotents, récupérables ; moteur futur seulement.
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

Branche dédiée, commits cohérents, PR vers master. Ne pas merger automatiquement, réécrire
l'historique partagé, forcer un push ou inclure des fichiers générés/secrets.
Avant toute modification distante, lire l'état réel et préserver le travail existant.
Si le dépôt est vide, un commit minimal sur master est autorisé pour initialiser, puis branche
`work/step-0-bootstrap`. Si l'accès GitHub refuse l'écriture, terminer les travaux locaux,
les vérifier et expliquer le blocage : ne jamais inventer une URL de PR ou prétendre avoir publié.
