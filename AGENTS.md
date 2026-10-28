# Instructions pour les agents — Echosphere

## Mission et état du dépôt

Jeu de stratégie spatiale persistant web responsive. MVP solo avec IA ; parties privées et univers
multijoueurs persistants sont futurs, sans fonctionnalités multijoueurs implémentées.
Étapes 0–4 fusionnées sur master (PR #1–4). Lot courant : étape 5A, domaine Colony/économie/construction, sur instruction de Thomas et brief joint. Lire [context.md](context.md) puis [progress.md](progress.md) au début d'une reprise.
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
`backend/app/colony/` porte les règles validées et commandes internes ; `game_data/` contient les valeurs v0.1 ; `docs/` les références ; `scripts/` les checks ;
`.github/workflows/ci.yml` les jobs qualité. Pas de couche métier générique à créer pour deux probes.

## Invariants obligatoires

- Backend autoritaire : vérifier propriété, prérequis, stocks, routes et échéances côté serveur.
- Aucun calcul métier critique dans le navigateur ; estimations UI uniquement, réconciliées au serveur.
- PostgreSQL conserve états et échéances ; un cache ou timer mémoire n'est jamais l'autorité.
- UTC partout en stockage/calcul ; timestamps avec fuseau, conversion locale à l'affichage.
- Production différée et événements persistants : utiliser app/simulation, pas de scheduler parallèle.
- Prendre le verrou timeline, respecter due_at/séquence et complete=True avant une future dépense.
- Ressources en micro-unités entières, taux horaires et reste persisté ; jamais de float critique.
- Handler sans commit, effet externe ou verrou d’un autre stream ; rollback atomique sur échec.
- Humain et IA utilisent les mêmes commandes et une connaissance limitée.
- Mobile obligatoire ; pas de simple dashboard réduit, pas d'action importante seulement au hover.
- Ne pas ajouter une feature non spécifiée sans documenter sa portée et son statut ; rester dans
  l'étape autorisée. Une documentation prospective n'autorise pas son implémentation immédiate.

## Compatibilité des instances et isolation

Universe est la frontière d'une instance de jeu : données rattachées directement/indirectement,
FK composites conservées et requêtes/commandes à contexte Universe explicite. Ne jamais supposer
un Universe = un User, ni un processus = un Universe. Workers multi-univers, indépendants des connexions.
Le scheduler verrouille EventStream (universe_id) ; ColonyTimeline garde seulement son ancrage
économique et son lien explicite stream/univers. Ne pas remettre colony_id dans ScheduledEvent.
Pas de owner_kind/owner_id sans FK pour modéliser les futurs propriétaires de stream.

Participation future : User/Account ↔ UniverseMembership ↔ éventuellement Empire ↔ rôle/permissions.
Ne pas créer cette table ou Empire.owner_user_id maintenant. Toute future API authentifiée vérifiera
User → Membership → Universe → permissions → Empire/Entity. Pas de règles gameplay en singleton
serveur ; les rulesets/vitesses seront versionnés par instance. Notifications/WebSockets jamais autorité.
Lire [modes](docs/01-game-design/game-modes.md) et [ADR 0006](docs/adr/0006-universe-game-instance.md).

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
(cd frontend && npx playwright install chromium && npm run test:e2e)
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

`master` est la branche d'intégration stable. Toute évolution suit
`work/<feature>` → PR vers master → CI et revue → merge sur autorisation explicite.
Pas de develop permanente ou de branche empilée pour contourner une dépendance non intégrée.
Tags et releases seront créés plus tard sur instruction, sans réserver master aux seules releases.

```bash
git switch master
git pull --ff-only origin master
git switch -c work/nom-du-lot
```

PR #2/#3/#4 fusionnées ; develop supprimée par Thomas.
Lot actuel : work/step-5a-colony-domain depuis master 54f928e, CI master verte avant création ;
PR #5 vers master, non fusionnée. Ne pas supprimer d'autres branches, forcer un push ou réécrire l'historique partagé.
Toute fusion future, tag ou déploiement requiert son autorisation propre.

Avant de déclarer une livraison terminée : vérifier la tête distante et sa CI, mettre à jour
context.md/progress.md et rapporter SHA, tests et limites réelles. Étape 5A limitée au domaine interne
et à la structure UI Colony. Étape 5B attend Q16 et un nouveau lot. Aucun endpoint gameplay,
Combat/Defense actif, flotte, recherche, colonisation ou multijoueur à ajouter ici.

## Économie et défense — règles 5A

Progression économique continue : niveaux 1–5 = early game seulement, jamais un MAX_LEVEL=5.
Niveaux supérieurs tant que ruleset/prérequis et représentation le permettent ; coût/durée/production
et croissance proviennent de game_data/rulesets/v0.1, pas de constantes dans les services.
Fichiers JSON stricts, aucune valeur dangereuse silencieuse. Snapshot validé par univers et ordre.
Vitesses économie/construction rationnelles par instance, ×1 normal ; recherche/flotte futures.
Pas de singleton de vitesse. Toute migration de ruleset d’un univers actif exige un nouveau contrat.

Nouvelles commandes : univers/empire/colonie explicites, verrou EventStream et catch-up complet,
SAVEPOINT par commande, transaction du caller. Prélever et réserver une fois à l’entrée de file ;
trois ordres actif inclus, une construction active ; bonus industriel courant à l’activation.
Annulation 100/80 %, idempotente ; cascade des upgrades dépendants. Refuser atomiquement si le
remboursement exact ne tient pas au stockage (Q39), sans crédit caché ou perte implicite.
Migrations antérieures intactes, 0004 additive ; downgrade peuplé refusé avant toute DDL.

Défense future : réseau stratégique limité et persistant à modules, coût d’opportunité surface/orbite,
dommages/réparation/Flux/renseignement à cadrer. Aucune table de défense ou système de combat ici.
La défense appartient à Colony : Vue d’ensemble / Infrastructures / Orbite / Défense. Pas de huitième
entrée globale ; aucune fixture runtime, valeur ou commande défensive présentée comme réelle.
Lire [Économie v0.1](docs/01-game-design/colony-economy-v0.1.md), [défense](docs/01-game-design/planetary-defense.md)
et [ADR 0007](docs/adr/0007-colony-economy.md). Garder Q30–Q39 ouvertes.
