# Protocole de collaboration — ChatGPT Work, Codex et Claude Code

**Statut : règle de travail validée par l’utilisateur le 2026-10-30.** Remplace la procédure à deux
agents Work ↔ Codex du 28/10 (exemples PR #5 désormais historiques). Le nom du fichier est conservé
pour les liens existants. Consignes de base : [AGENTS](../../AGENTS.md) ; checkpoint courant :
[progress](../../progress.md) ; recette : [Definition of Done](../04-quality/definition-of-done.md).

## Agents et environnements

| Agent | Environnement | Capacités habituelles | Limite à consigner |
| --- | --- | --- | --- |
| ChatGPT Work | GitHub (connecteur) | Lire PR/diff/commits/CI, commenter, publier des commits documentaires ou de code sur une branche | Pas de Docker ni de shell local attesté : ses validations sont la CI observée, jamais des « tests locaux » |
| Codex local | Ubuntu WSL2 + VS Code, filesystem Linux (~/projects) | Git, Docker Compose, tests natifs ou en conteneur, gh | Recette graphique Windows non attestée sauf preuve |
| Claude Code local | Même WSL2/VS Code, même machine que Codex possible | Idem Codex ; lit AGENTS.md via [CLAUDE.md](../../CLAUDE.md) | Même disque que Codex : voir règles de travail parallèle |

Les trois agents appliquent les mêmes règles de développement, spécifications, invariants et DoD.
Aucun agent ne partage la mémoire conversationnelle d’un autre : le contexte passe **uniquement** par
les documents versionnés, les commits, les PR (description, commentaires, revues) et la CI GitHub.
Une décision prise en conversation n’existe pour les autres qu’après transcription synthétisée,
avec statut et provenance, dans sa référence canonique. Ne pas inventer l’identité d’un agent.

## Prendre le relais

1. **État GitHub réel** : PR, base/head/SHA, branches, CI et commentaires de revue non résolus.
   Une branche locale ne prouve ni publication ni merge.

```bash
gh pr list --repo ThomasPerez91/Echosphere --state open
gh pr view <n> --repo ThomasPerez91/Echosphere \
  --json state,isDraft,baseRefName,headRefName,headRefOid,statusCheckRollup
gh run list --repo ThomasPerez91/Echosphere --commit <sha>
```

2. **État local** (Codex/Claude) : `git status --short --branch`, `git fetch origin`, puis
   `git pull --ff-only` sur la branche du lot. Travail non committé, divergence ou worktree d’un autre
   agent : préserver et examiner ; jamais de reset, stash automatique, force-push ou suppression.
3. **Lecture** : AGENTS → context → progress (bloc « Reprise rapide » d’abord) → passation →
   roadmap → open-questions → documents métier et ADR du lot.
4. **Périmètre** : la dernière instruction utilisateur consignée dans progress fait foi. Une
   documentation future, une PR ouverte ou un audit n’autorisent ni implémentation ni fusion.

## Checkpoint de reprise

progress.md est le checkpoint principal ; les documents métier restent les références durables.
Pas de fichier de suivi supplémentaire : les anomalies de revue vivent dans la PR, leur synthèse dans
progress. Le bloc **Reprise rapide** en tête de progress est réécrit par chaque agent qui publie :

| Champ | Contenu attendu |
| --- | --- |
| Branche / PR / base | Nom, numéro, SHA de base |
| Tête et CI | SHA publié ; runs CI observés (id, event, conclusion) ou « non observée » |
| Dernier agent | ChatGPT Work, Codex local ou Claude Code local, si connu ; sinon « inconnu » |
| Travail réalisé | Ticket/lot et résultat en une ou deux lignes |
| Décisions | Liens vers les références canoniques modifiées, statut ; aucune décision inventée |
| Fichiers modifiés | Zones ou fichiers principaux du dernier incrément |
| Tests réellement exécutés | Commandes et résultats ; checks non exécutés listés comme tels |
| Anomalies / corrections restantes | Constats de revue ouverts (lien PR), risques, Qxx touchées |
| Prochaines tâches | Prochaine action autorisée, puis séquence prévue |

Le SHA d’un commit ne peut pas figurer dans ce même commit : noter « tête = commit portant ce
checkpoint », puis consigner SHA et CI dans un commentaire de PR ou au checkpoint suivant.

## Revue croisée

Cycles possibles, sur la même branche de PR :

- Codex développe → Claude Code audite → Codex corrige → Claude Code valide.
- Claude Code développe → Codex audite → Claude Code corrige → Codex valide.
- ChatGPT Work peut tenir l’un ou l’autre rôle depuis GitHub, ou reprendre le travail de l’un ou de
  l’autre, dans les limites de ses capacités.

### Règles du relecteur

1. Commence en **lecture seule** : aucun commit, push, modification de fichier ni commentaire
   « approuvé » avant d’avoir terminé l’examen. Il note le SHA exact relu.
2. Examine le diff Git (`git diff <base>...<sha>`), le code, les tests, les migrations et les
   spécifications canoniques du lot (contrats, ADR, DoD), plus la CI de ce SHA.
3. Chaque anomalie est **justifiée par des éléments vérifiables** : fichier:ligne au SHA relu,
   référence de spécification, commande et sortie, scénario d’échec concret. Une intuition sans
   preuve est notée « question », pas « anomalie ».
4. Chaque anomalie reçoit une criticité :

| Criticité | Exemples | Effet |
| --- | --- | --- |
| Bloquante | Faille de sécurité, perte/corruption de données, violation d’un invariant ou contrat validé, migration destructive, CI rouge | Pas de validation tant que non corrigée ou réfutée |
| Majeure | Comportement incorrect, cas de concurrence/reprise non couvert, test manquant sur un risque réel, écart de spécification | Correction attendue dans le lot |
| Mineure | Lisibilité, nommage, documentation imprécise, test fragile | Correction ou report justifié |
| Remarque | Suggestion, question, piste hors lot | Aucune obligation ; hors lot → known-gaps ou Qxx |

5. Rapport publié dans la PR (revue ou commentaire), avec SHA relu, tests réellement exécutés par le
   relecteur ou CI vérifiée, liste numérotée des anomalies (R1, R2…) et criticité. Le relecteur
   précise ce qu’il n’a pas examiné. **L’absence d’anomalie détectée n’est pas une garantie de qualité.**

### Règles du développeur

1. Reproduit ou vérifie chaque anomalie, puis répond par numéro : **confirmée**, **contestée**
   (avec preuve contraire : test, spécification, trace) ou **hors lot** (renvoyée en known-gaps/Qxx).
   Un constat erroné ou non démontré peut être contesté ; l’utilisateur arbitre un désaccord persistant.
2. Corrige les anomalies confirmées dans des commits identifiables (`fix(review): R2 …`), sans
   élargir le périmètre.
3. **Relance les tests concernés** après correction, puis la suite complète du lot selon la DoD ;
   publie et vérifie la CI du nouveau SHA.

### Validation

Le relecteur relit le nouveau SHA (diff depuis le SHA audité), vérifie chaque correction et chaque
contestation, puis conclut : validé, validé avec réserves listées, ou nouvelles anomalies. Une
validation n’est pas une autorisation de fusion : la fusion reste une instruction utilisateur.

**Règle commune** : aucun agent ne déclare un test réussi sans l’avoir réellement exécuté ou sans
avoir vérifié son exécution dans la CI du SHA concerné. Une CI configurée n’est pas une CI exécutée ;
un test ignoré (RUN_DB_TESTS absent, par exemple) n’est pas réussi.

## Travail parallèle, branches et worktrees

- **Un seul agent écrit dans un répertoire de travail donné à un instant donné.** Deux agents ne
  modifient jamais simultanément les mêmes fichiers dans le même répertoire.
- **Un seul agent écrit sur une branche à la fois.** Le rôle d’écriture se transmet par un commit
  publié et un commentaire de PR ; le suivant fait fetch/ff-only avant d’écrire.
- Lots parallèles : une branche courte `work/...` par lot depuis master synchronisée, chacune dans
  son propre worktree, sans branche empilée ni fichiers partagés modifiés en concurrence.
- Relecture pendant que le développeur travaille : worktree détaché sur le SHA publié.

```bash
# Relecture isolée d’un SHA publié (lecture seule)
git fetch origin
git worktree add --detach ../Echosphere-review <sha>
# Lot parallèle autorisé, nouvelle branche depuis master
git worktree add -b work/<lot> ../Echosphere-<lot> origin/master
git worktree list
# Fin : uniquement si le worktree est propre et son travail publié
git worktree remove ../Echosphere-review
```

Un worktree ne contient pas le `.env` non versionné : en créer un depuis `.env.example`, sans copier
de secret réel. Compose dérive le nom de projet du dossier : un autre worktree a donc ses propres
volumes (bases vides), mais les ports hôtes (8443, 5173, 8000, 8025) sont fixes — une seule pile
Compose à la fois. Ne jamais lancer `down -v` sur la pile d’un autre agent.

## Démarrage local frais (Codex / Claude Code)

Cible : Windows 11 → Ubuntu WSL2 → VS Code → Docker Desktop avec intégration WSL2. Pas d’installation
Python/Node hôte nécessaire pour Compose. master ne contient pas le Portal tant que PR #7 n’est pas
fusionnée : choisir la branche de la PR à tester.

```bash
git clone https://github.com/ThomasPerez91/Echosphere.git && cd Echosphere
git switch work/step-5c-portal-account-lobby   # ou master, selon le lot
cp .env.example .env                           # jamais sur un .env existant
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 180
docker compose ps -a
docker compose exec -T backend alembic check
docker compose exec -T portal-backend alembic check
python3 scripts/smoke_compose.py
python3 scripts/smoke_portal_compose.py
python3 scripts/smoke_control_compose.py
docker compose down                            # conserve les volumes
```

Attendu : bases, APIs, frontends et Mailpit healthy ; workers et listener running ; migrations/init
Exited(0). Portal https://portal.echosphere.localhost:8443, Game https://game.echosphere.localhost:8443
(CA locale à approuver explicitement, résolution .localhost selon l’environnement), diagnostic Game
http://localhost:5173 et :8000. Détails : [recette C01](../03-technical/portal-foundation.md),
[C02](../03-technical/portal-registration.md), [C06](../03-technical/portal-game-control.md),
[déploiement](../03-technical/deployment.md). Les smokes arrêtent temporairement des bases : environnement
local de test seulement. `down -v` détruit les données et ne fait pas partie d’un relais.

## Vérifications identiques

```bash
python3 scripts/check_docs.py
# venv Python 3.12 par backend : pip install -r requirements-dev.lock puis pip install --no-deps -e .
(cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q)
(cd portal/backend && .venv/bin/ruff check . && .venv/bin/pytest -q)
# Frontends ; npx playwright install chromium avant le premier test:e2e
(cd frontend && npm ci && npm run lint && npm test && npm run build && npm run test:e2e)
(cd portal/frontend && npm ci && npm run lint && npm test && npm run build && npm run test:e2e)
```

Intégrations PostgreSQL : `RUN_DB_TESTS=1` vers une base dédiée dont le nom finit par `_test`,
jamais les données à conserver (les suites de migration font des downgrades). Variantes en conteneur :
[README](../../README.md) et [stratégie de tests](../04-quality/testing-strategy.md). La CI GitHub
exécute ces jobs et les smokes Compose ; son résultat se lit sur le SHA, pas dans le workflow.
Mission documentaire : check docs, liens et diff de périmètre ; CI existante observée après push.

## Publier avant de céder la main

1. Mettre à jour progress (bloc Reprise rapide + entrée datée) et les références canoniques.
2. Relire diff, périmètre et confidentialité ; commits cohérents, push sur la branche du lot ;
   pas de nouvelle PR si la PR du lot existe.
3. Relire SHA distant et CI effective ; consigner le résultat dans la PR.
4. Aucune fusion, tag, release, déploiement, modification de master ou suppression de branche sans
   instruction explicite de l’utilisateur.

Confidentialité : aucune conversation brute, .env, credential, clé, identifiant privé ou donnée
personnelle dans Git, les PR ou les commentaires de revue.

## Historique

Avant le 2026-10-30, la procédure ne couvrait que Work ↔ Codex et prenait la PR #5 comme exemple
(reprise de work/step-5a-colony-domain avant sa fusion). PR #5 et PR #6 sont fusionnées ; ces
consignes sont historiques et ne doivent plus guider une reprise.
