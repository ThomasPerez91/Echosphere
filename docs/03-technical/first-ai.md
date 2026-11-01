# Première IA — contrôleurs, orchestrateur, politique et recette

**Contrat technique de l'étape 11.** Q11 est close avec amendements le 01/11/2026 ; ce document
décrit ce qui est réalisé sur la PR #14.
[Contrat produit faisant foi](../01-game-design/artificial-intelligence.md#q11--validation-avec-amendements-01112026),
[architecture et audit AI01](ai-engine.md), [plan AI00–AI11](../05-project/step-11-plan.md).
Le ruleset `v0.6` est réservé aux nouveaux univers explicitement démarrés. Les univers v0.1–v0.5
restent inchangés : aucune migration de données, aucune adoption, aucun contrôleur implicite.

## Ruleset v0.6

- **Base :** `v0.6` = `v0.5`, plus `ai.json` strict (extras refusés, versions figées).
- **Contenu de `ai.json` :**
  - deux profils, `economic_cautious` et `expansionist`, avec des poids entiers par objectif
    (économie, recherche, exploration, expansion, logistique), dont la somme vaut 100 ;
  - cadence de 600 s ;
  - budgets : 128 candidats, pages de flottes de 64, une page bornée par famille ;
  - objectifs de production, références des producteurs et de l'industrie ;
  - seuil de stockage, durée maximale d'un projet ;
  - rétention de 100 traces, 256 KiB par observation, 64 KiB par trace.
- **Validation croisée :** toute infrastructure citée doit exister au catalogue. `ai` est
  obligatoire en v0.6 et refusé en v0.1–v0.5.
- **Épinglage :** comme les autres règles, les données sont épinglées dans
  `UniverseEconomy.ruleset_data`. Le contrôleur fige aussi `policy_version` et `policy_digest`,
  et toute dérive refuse le tour.

## Persistance (migration 0011)

- **`ai_controllers` :**
  - une ligne par Empire IA, liée à l'Univers et à l'Empire ;
  - profil, version et empreinte de politique ;
  - état `enabled`, `paused` ou `blocked` ;
  - `started_at`, `next_decision_at`, `sequence`, mémoire JSON minimale ;
  - compteur d'essais techniques, `retry_at`, code d'erreur ;
  - index des rendez-vous `(state, next_decision_at)`.
- **`ai_decisions` :** une trace par `(controller_id, sequence)`, contenant :
  - l'observation canonique ;
  - les candidats évalués, avec scores et raisons ;
  - la règle de départage ;
  - la clé d'intention et le résultat ;
  - la mémoire avant et après.

  Les traces sont privées (aucune API) et seules les 100 dernières sont conservées par contrôleur.
- **`ai_bootstraps` :** requête et résultat du démarrage d'un univers v0.6. Un rejeu identique
  renvoie le même résultat ; une requête différente est refusée.
- **Aucune identité factice :** aucune table d'inventaire IA, aucun User, Account, Membership,
  session ni binding pour une IA. Le downgrade est refusé tant que des données IA existent.

## Racine de confiance et exclusivité

- **Racine de confiance :** l'`AIController` persistant, pas `controller_type`, qui reste
  descriptif.
- **`authorize` :** à chaque tour, revérifie l'état, l'Univers et l'Empire, `controller_type = 'ai'`,
  le profil et l'empreinte de politique, ainsi que l'absence de binding humain.
- **Exclusivité :** l'activation et l'attribution humaine par le plan de contrôle prennent d'abord
  le même verrou de ligne sur l'Empire. L'une des deux échoue toujours :
  - `human_binding_present` ;
  - `empire_ai_controlled` (409).
- **Capabilities du dispatcher, fixes :** lecture et construction Colony, Research lecture et
  démarrage, lecture Galaxy, Fleet lecture, production et commande, `colony.expand`. Aucune
  annulation ni rappel automatique.

## Bootstrap opérateur

`python -m app.ai.worker --bootstrap <universe> --name … --seed … [--profiles …] [--at …]`
(fonction `app.ai.bootstrap.bootstrap`), en une seule transaction sous verrou consultatif de
l'Univers :

1. Univers vide : aucune économie configurée, aucun Empire.
2. Configuration v0.6 et génération du monde.
3. Sites pris dans l'ordre canonique du générateur (`GalaxySystem.ordinal`), sans jamais
   consulter leur qualité ni le profil.
4. Un Empire humain, puis 0 à 3 IA, tous créés avec le même `initialize_colony` et le même
   `initialize_empire` à la même date.
5. Contrôleurs activés explicitement, premier rendez-vous à départ + 600 s.

Faute de sites suffisants, c'est un refus, jamais une génération compensatoire. Aucune flotte
n'est offerte et aucune fixture `*_test` n'est importée.

`--at` fixe une date de départ explicite, utilisée par la recette pour son horloge de test.

## Orchestrateur

Le processus est `python -m app.ai.worker` (même image que le backend Game). Le service Compose
`ai-worker` ne démarre qu'avec `--profile ai` et dispose de ressources bornées (0,5 CPU,
512 Mio). L'orchestrateur est hors de tout handler TimeEngine, et aucun type d'événement
`AI_TURN` n'existe.

1. Sélectionner un contrôleur dû par `(next_decision_at, empire_id)`, `FOR UPDATE SKIP LOCKED`,
   avec un délai de verrou et de requête borné. Un contrôleur par transaction.
2. Prendre les verrous dans l'ordre stream d'opérations d'Empire → Research → colonies propres
   triées. Aucun stream étranger n'est pris.
3. Capturer l'heure après les verrous, puis rattraper opérations, Research et colonies jusqu'à
   cette date. Une colonie fondée pendant ce rattrapage est relue et réglée avant l'observation.
4. Collecter l'observation, décider, puis exécuter **au plus une** commande via le dispatcher et
   les services communs : `enqueue`, `research.start`, `order_ships`, `split`, `load`, `unload`,
   `launch`.
5. Dans la même transaction, enregistrer l'effet ou WAIT ou refus métier, la trace, la mémoire,
   `sequence + 1` et le prochain créneau. Ce créneau est le premier point strictement futur de la
   grille de 600 s ancrée au départ : après une panne, un seul tour sur l'état courant, sans
   rattrapage stratégique.
6. **Clé d'idempotence :** `ai:<controller>:<sequence>:<operation>`, identique sur retry.
   - Crash avant commit : aucun effet, la séquence n'est pas consommée.
   - Après commit : aucune seconde commande.
7. **Refus et erreurs :**
   - refus métier (`ColonyError` et dérivées) : tracé une fois, puis le créneau suivant ;
   - erreur technique ou dépassement de budget : rollback intégral, retry borné, puis `blocked`
     (`--blocked`, `--resume`).
   - `--pause` arrête les nouveaux tours, jamais les achèvements déjà acceptés.

## Perception et politique

- **Collecteur (`observation.collect`) :**
  - seule frontière vers la base ;
  - lit uniquement les colonies, flottes et rapports propres, et la Knowledge de l'Empire
    (≤ 12 colonies, ≤ 50 systèmes, ≤ 250 mondes, ≤ 100 routes) ;
  - les bornes sont vérifiées avant matérialisation ; un dépassement est refusé, sans troncature ;
  - jamais de produit flottes × planètes ;
  - devis issus des mêmes fonctions que les services ; un devis n'est jamais une réservation.
- **Familles paginées :** économie, recherche, exploration, expansion, logistique.
  - ordre canonique explicite ;
  - curseur persistant dans la mémoire, parcours circulaire : une référence toujours éligible est
    examinée en au plus `ceil(M/P)` visites.
- **Mémoire d'échec COLONIZE :** limitée à `planet_id`, `observed_at` et `target_unavailable`, issus
  des rapports propres. Aucune occupation étrangère n'est consultée.
- **Politique (`policy.choose`) :**
  - pure, sur JSON uniquement (sérialisation canonique : ni ORM, ni float, ni NaN) ;
  - score = poids × utilité entière de 0 à 1000 ;
  - départage par coût lexical (Alliages, Flux, Données), puis durée, puis clé stable ;
  - à observation, mémoire, profil et politique identiques, la décision est identique.
- **Projets multi-tours :** une commande par tour, revalidés à chaque tour, abandonnés au bout de
  `project_turn_limit` tours, sans réservation. Exemple d'expansion : commander un colonisateur →
  attendre → détacher → CHARGER le paquet → COLONIZE.
- **Bootstrap d'une colonie fondée :** Alliages, puis Flux, puis Données, dans cet ordre explicite
  (`BOOTSTRAP_ORDER`), jamais dans l'ordre d'un objet JSONB épinglé. La réserve n'est que
  décisionnelle. Faute de moyens, l'IA attend ou fait un transport légitime de ravitaillement.
- **Unités :** CHARGER reçoit des unités entières, comme l'API humaine. Les devis, écarts et
  stocks restent en micro-unités. Le test autonome vérifie la chaîne : décision → cargo → snapshot
  COLONIZE → stock initial.

## Preuves

Tests PostgreSQL `tests/integration/test_ai.py` et tests purs `test_ai_policy.py`/`test_ai_rules.py` :
- démarrages égaux, rejeu et conflit de bootstrap, sites insuffisants atomiques ;
- course activation IA contre attribution humaine ;
- migration sans dérive et downgrade peuplé refusé ;
- tour atomique et rejeu pur de la trace ;
- deux orchestrateurs, crash avant et après commit, refus métier unique ;
- panne de 3 h coalescée, pause sans arrêt des événements acceptés ;
- données cachées modifiées (colonie, stock, flotte, monde, système UNKNOWN) sans effet sur
  l'observation ni sur la décision ;
- budget dépassé, puis retry et `blocked` ;
- profils divergents sur une même observation réelle par les seuls poids ;
- curseur de recherche au-delà de la première page ;
- chaîne autonome de 72 h pour les deux profils.

Recette `scripts/smoke_ai_compose.py` (CI compose-smoke) : projet, bases et volumes `*_test`
jetables, ruleset v0.6 inchangé.
1. **Départ :**
   - compte humain de test et univers provisionnés par Portal ;
   - bootstrap par la CLI opérateur (rejeu identique), départs égaux, aucune flotte ;
   - binding humain seul.
2. **Humain absent :** l'humain entre par le handoff réel, sa page est fermée, Portal est arrêté.
3. **Horizon long :** une horloge de test injectée avance par pas de 600 s à travers les vraies
   classes `TimeEngine` et `Orchestrator`, jamais au-delà de l'heure réelle. Aucune écriture d'aide.
4. **Preuve en base :**
   - constructions, Research, sonde puis SURVEY ;
   - colonisateur, paquet exact, COLONIZE ;
   - colonie fondée dont les trois premiers ordres sont les producteurs dans l'ordre, et qui produit ;
   - clés `ai:` seulement ;
   - un seul principal Game, humain.
5. **Processus réels :** `worker` et deux `ai-worker` sur l'horloge système, Portal toujours
   arrêté.
   - exactement un tour coalescé par contrôleur ;
   - prochain créneau futur sur la grille ;
   - redémarrage sans tour en double.
6. **Fin de session :** la session humaine reste valide sans Portal, puis expire avec un 401.

## Limites

L'équilibrage est provisoire et non démontré (exemple : nombre de fondations en 72 h). Les budgets
et délais techniques sont ajustables sur mesure. La charge de 500 Empires (Q17) n'est pas démontrée
par 1 humain + 2 IA. Pas de Combat, de relations ni d'interface IA. Résultats et CI dans
[progress](../../progress.md).
