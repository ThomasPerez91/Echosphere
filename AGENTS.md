# Procédure commune des agents — Echosphere

**Statut : règle de travail Work / Codex local.** GitHub est la source commune du code, décisions,
architecture et progression. Ne jamais supposer que la mémoire du chat suffit. Lire les statuts de
[docs/README](docs/README.md) ; une proposition d’assistant ne vaut pas validation utilisateur.

## Début de chaque session

1. Vérifier GitHub réel avant modification : branche stable, PR/base/head/SHA, branches et CI.
2. Contrôler l’état local, fetch puis synchronisation ff-only appropriée ; préserver toute divergence
   ou modification non publiée. Aucun reset/force-push, suppression ou merge implicite.
3. Lire AGENTS.md → [context.md](context.md) → [progress.md](progress.md).
4. Lire [passation](docs/06-handoff/README.md), [roadmap](docs/05-project/roadmap.md),
   [questions](docs/05-project/open-questions.md), documents métier et ADR du lot.
5. Identifier le dernier travail publié Work ou Codex, sa CI et ses limites. Ne pas démarrer deux
   modifications concurrentes sur la même branche ni inventer l’identité de l’agent précédent.
6. Définir le périmètre autorisé : une documentation future n’autorise pas son implémentation.

## Fin de chaque session

1. Documenter résultat et décisions dans leurs références canoniques, avec statut/provenance.
2. Mettre progress.md à jour : objectif, branche/base/tête, fichiers, validations réellement faites,
   checks non exécutés, limites, risques/Qxx, prochaine action et environnement si connu.
3. Actualiser context.md si le cadre stable change ; ne pas recopier les ADR en doublon.
4. Vérifier diff, qualité et confidentialité ; commits cohérents, push sur la bonne branche,
   ouvrir/actualiser la PR selon le lot. Relire SHA distant et CI effective après publication.
5. Aucune fusion/tag/release/déploiement ou suppression de branche sans instruction propre.

Même DoD dans Work et Codex. Pas de résultat CI configuré présenté comme exécuté ; pas de WSL2
annoncé testé sans recette réelle attestée. Procédure concrète :
[Work ↔ Codex](docs/06-handoff/work-codex-handoff.md), [DoD](docs/04-quality/definition-of-done.md).

## Mission documentaire historique et reprise Git

master = intégration stable ; work/... → PR master → CI/revue → merge sur autorisation explicite.
Le workflow historique develop/release est superseded, aucune develop permanente. Pour un nouveau
lot après intégration de sa fondation : master synchronisée puis branche courte, sans empilement.

Checkpoint du 28/10/2026 : la passation documentaire a été portée par
**work/step-5a-colony-domain / PR #5**, ouverte et non fusionnée au départ sur 5be00da.
L’état GitHub réel prévaut toujours sur les consignes contextuelles d’un ancien checkpoint.

- Si PR #5 est encore ouverte et que la mission porte dessus, reprendre sa branche existante ;
  ne pas créer de nouvelle branche ni PR #6 pour ce lot, ni merger sans autorisation explicite.
- Si PR #5 est fusionnée, cette consigne est historique : ne pas reprendre sa branche pour un
  nouveau lot. Tout nouveau lot autorisé repart de master synchronisée sur une nouvelle branche
  courte work/..., selon son périmètre. Ne pas recréer la branche de PR #5.

Le périmètre de la passation était **documents uniquement**, plus scripts/check_docs.py si nécessaire
aux nouveaux documents. Services, gameplay, migrations/SQL, game_data (même son README), dépendances,
Compose/Docker et tests fonctionnels étaient exclus. Toute anomalie de code observée dans cette
mission va dans [audit](docs/06-handoff/pr-5-audit.md)/[risques](docs/06-handoff/known-gaps.md), sans
correctif dans ce lot. Une nouvelle instruction et progress déterminent le prochain lot ; aucun
force-push ou suppression de branche implicite.

## Produit et données

Stratégie spatiale web asynchrone/persistante. Solo humain+IA MVP, privé et persistant multijoueurs
futurs ; dix minutes quotidiennes, sessions longues pour mieux décider. Aucune récolte manuelle,
production liée à la présence, quatrième ressource principale ou pay-to-win. Alliages/Flux/Données.
Pas de clone OGame/Stellaris lourd, RTS, city-builder/population ou logistique physique complexes.
Les mockups ne sont jamais des spécifications métier. Humain/IA utilisent les mêmes règles/services,
IA sans LLM stratégique ni spawn gratuit, perception limitée et déterministe/testable.

12 secteurs/2 orbitaux = **départ de référence v0.1 seulement**, pas toutes les planètes. Secteur
identifiable par infrastructure, upgrade sans nouvelle place, capacités variables futures.
Niveaux continus ; 1–5 seulement early game, pas de plafond 5. Paramètres/facteurs/arrondis dans
game_data validé et versionné ; valeurs de balance provisoires, jamais copiées en constantes métier.

## Architecture actuelle et cible

Actuel : backend Game FastAPI modulaire, worker du même code, PostgreSQL, SQLAlchemy/Alembic,
frontend React/TypeScript/Vite. backend/app/persistence, simulation et colony portent les domaines ;
backend/migrations les révisions, game_data les rulesets, frontend/src les vues. Pas d’API gameplay.

**Décision validée future** : [ADR 0008](docs/adr/0008-control-plane-game-data-plane.md), deux backends
isolables chacun monolithe modulaire : Portal Accounts/Auth/Lobby → Accounts DB ; Game gameplay →
Game DB. CPU/RAM/pools/scaling/bases/réseau séparables ; ne pas créer 10–20 microservices.
Portal ne fait jamais de SQL direct Game DB ; interface interne Game contrôlée, authentifiée,
idempotente. Le client gameplay appelle Game directement ; pas de dépendance Portal par commande.
Ticket signé court/unique puis GameSession opaque autonome : contrats 5B validés dans
[identity-contracts](docs/03-technical/identity-contracts.md), détails techniques délégués à 5C/5D.
Aucun credential Accounts en Game DB. Portal indisponible ne doit pas arrêter univers/worker ou
sessions Game établies dans les limites du contrat 5B validé. Socle C01 sur PR #7 : Portal FastAPI,
Accounts PostgreSQL/Alembic et frontend séparés, HTTPS local. C02 ajoute inscription/Argon2id/vérification email et outbox locale durable ;
C03 ajoute connexion, profils/sessions Portal, CSRF et intentions de logout durables.
C04 ajoute opérations sensibles sans MFA, step-up et révocations globales persistées.
C05 ajoute MFA TOTP/WebAuthn, secours/récupération limitée et preuves renforcées C04 ;
lobby/S2S/handoff restent futurs. [Recette C05](docs/03-technical/portal-mfa.md).
[Recette C04](docs/03-technical/portal-account-security.md). [Recette C03](docs/03-technical/portal-sessions.md). [Recette C02](docs/03-technical/portal-registration.md).
[Recette C01](docs/03-technical/portal-foundation.md).

Compte global, plusieurs parties : User → UniverseMembership → Universe → éventuellement Empire/
rôle/permissions. Ne pas réduire à Empire.owner_user_id ; empire partagé Q21 reste ouvert.
Universe n’est ni User ni processus. Pas de compte global factice ou accès implicite pour une démo.
Q16 a son cadrage 5B couvert ; détails délégués et reports Q48/Q49/Q55 au registre.
5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`), contrats seulement partiellement implémentés sur PR #7 par C02–C05.
Lot courant autorisé : 5C compte/lobby. Checkpoint et cadrage effectués ; C01 implémenté sur PR #7,
C02/C03 comptes/vérification/sessions, C04 opérations sensibles et C05 MFA implémentés ; C06 lobby/S2S est la suite. Migrations Accounts séparées, pas de SQL Portal→Game.
5D API Colony sécurisée reste hors lot. Ne pas élargir le périmètre sur la seule base de la passation.

## Invariants techniques à préserver

- Backend Game autoritaire, PostgreSQL conserve états/échéances ; cache/UI/notifications non autorités.
- UTC et timestamps aware ; micro-unités entières, taux horaires et reste persisté, pas de float critique.
- EventStream(universe_id) est le scope de lock/ordre/idempotence ; ColonyTimeline garde son ancrage
  économique. Pas de colony_id dans ScheduledEvent ni owner_kind/owner_id sans FK.
- Rattrapage complet sous verrou avant dépense, coûts et ordre dans la transaction du caller.
  Handler sans commit, effet externe ou lock d’un autre stream ; rollback atomique et reprise.
- 5A : trois ordres actif inclus, un actif ; réservation immédiate, snapshots par univers/ordre,
  bonus industriel au démarrage du suivant. Annulation 100/80 idempotente ; Q39 pas définitivement
  arbitrée, refus de saturation actuel à préserver sans en faire une décision produit finale.
- FK et scopes par univers, propriété/permissions et fog côté serveur. controller_type ne prouve
  pas une identité. Futures API : GameSession → accès Universe/Membership → permissions → Entity.
- Défense : réseau limité de modules persistants futur, pas de piles de canons. Colony possède
  Vue d’ensemble/Infrastructures/Orbite/Défense, pas de huitième domaine global. Q30–Q38 ouvertes.
- Mobile/clavier obligatoires, pas de hover seul, aucune fixture runtime ou mutation sans identité.

## Conventions et validation

Code/identifiants anglais, docs françaises, snake_case Python, PascalCase React, TypeScript strict,
Ruff/ESLint. Secrets par environnement, jamais .env/credential/log privé dans Git ou VITE_*.
Ne publier que des décisions Echosphere synthétisées, aucun transcript privé ou élément personnel.
Tests pertinents pour comportement nouveau, refus/concurrence/reprise selon risque ; pas de tests
artificiels qui recopient le code. Mission docs : checks documentaires/diff, CI existante observée.

```bash
python3 scripts/check_docs.py
(cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q)
(cd frontend && npm ci && npm run lint && npm test && npm run build)
(cd frontend && npx playwright install chromium && npm run test:e2e)
```

Intégrations : PostgreSQL dédié *_test et RUN_DB_TESTS=1, jamais les données à conserver.
Compose/migrations/smoke et commandes détaillées dans [reprise](docs/06-handoff/work-codex-handoff.md).
Ne pas lancer down -v ou downgrade sur données à garder. Toujours distinguer passé vérifié,
CI du commit actuel, tests ignorés et limites réelles.
