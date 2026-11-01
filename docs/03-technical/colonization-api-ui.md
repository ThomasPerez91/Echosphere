# Colonisation — persistance, résolution, API et UI

**Contrat technique de l'étape 10.** Q07 est close pour l'étape 10 le 01/11/2026, avec amendements ;
réalisé sur la PR #13.
[Règles produit](../01-game-design/colonization.md), [plan COL00–COL11](../05-project/step-10-plan.md).
Ruleset `v0.5` uniquement ; les univers v0.1–v0.4 restent inchangés, sans aucune migration.

## Ruleset v0.5

- **Base :** `v0.5` = `v0.4`, avec seules les versions changées.
- **`fleets.json` :** ajoute la classe `colonizer`.
- **`colonization.json` :** rassemble les règles d'expansion :
  - `colonizer_class`, quantité 1 par ordre ;
  - incrément du coût progressif `cost_step_bps` (+0,5 par rang) ;
  - 12 colonies maximum, 1 COLONIZE active ;
  - paquet minimum.
- **Schéma inchangé :** le schéma des classes v0.4 ne change pas. Les snapshots v0.4 déjà
  enregistrés et les missions en cours restent donc valides.
- **Validation stricte :** l'absence de `colonization` est refusée en v0.5, sa présence est refusée
  en v0.1–v0.4. Le colonisateur ne peut pas cartographier. Le paquet doit tenir dans son cargo, et
  ce cargo dans le stockage d'une nouvelle colonie.

## Données et migration 0010

DDL figé, sans dérive `alembic check`.

**`fleet_missions` :**
- `kind` accepte `COLONIZE`, et `target_planet_id` est obligatoire si et seulement si `COLONIZE`.
- La planète cible doit être connue de l'Empire (FK `planet_knowledge`) et appartenir au système de
  destination (FK `planets(id, system_id, universe_id)`).
- Seule COLONIZE peut viser son propre système : 0 saut et `travel_arrival_at = started_at`. Toute
  autre mission garde `origin ≠ destination` et un trajet strictement positif.
- Index unique partiel : une COLONIZE `active` par Empire.
- Index de recherche des concurrents : `(universe_id, target_planet_id)`.

**`fleets` :** nouveau statut `SETTLED`, réservé aux flottes opérationnelles. Une flotte vidée par
une fondation n'a plus ni système, ni mission, ni unités, mais son historique est conservé.

**`colonies` :** `founded_at` et `founding_mission_id` (unique, FK vers la mission du même Empire).
Les colonies de départ ont ces deux champs nuls. `uq_colonies_planet` reste le dernier rempart contre
une double propriété.

**Permission `colony.expand` :** le total passe à 13 permissions. Elle est ajoutée au CHECK des
bindings, au DTO Game, au schéma partagé et à Portal, sans aucune attribution automatique.

**Downgrade :** il est refusé tant que des données ou des droits de colonisation existent.

## Production du colonisateur

- **Rang N :** au moment de l'acceptation, N = colonies + colonisateurs existants + ordres de
  colonisateur ouverts de l'Empire.
- **Prix :** coût × `(10000 + step × (N − 1)) / 10000`. Il est figé dans le snapshot de l'ordre
  (`colonizer_rank`, `multiplier_bps`, `cost`), vérifié à l'achèvement, et l'annulation rembourse
  100/80 de ce prix accepté, plafonné par Q39.
- **Sérialisation :** le calcul se fait sous le verrou de la chronologie d'opérations d'Empire.
  Deux colonies qui commandent en même temps obtiennent donc N puis N + 1.
- **Affichage :** la projection Flottes expose le devis courant (`colonization.colonizer_quote`),
  seulement avec `colony.read` et `fleet.build`.

## Mission COLONIZE

Elle utilise le moteur Flottes existant (chemin, snapshot, carburant, worker, idempotence,
rapports), sans second moteur de déplacement.

- **Composition :** exactement 1 colonisateur, la cible étant `target_planet_id` (planète connue).
- **Mission distante :**
  - chemin `known_path` vers un système MAPPED ou mieux ;
  - carburant `sauts × 20 Flux`, payé par la colonie d'attache ;
  - `due_at = travel_arrival_at`, sans phase d'établissement ;
  - rappel possible tant que `now < travel_arrival_at`.
- **Mission locale (autre planète du système courant) :**
  - chemin vide, 0 saut, 0 trajet, 0 carburant, `due_at = started_at` ;
  - mission persistée et résolue par le worker, sans rappel possible ;
  - `verified_path(local=True)` n'accepte l'absence de legs que pour ce cas.
- **Contrôles au lancement :** ils ne portent que sur la connaissance de l'Empire. L'occupation
  étrangère n'est jamais vérifiée ni révélée.
  - Monde déjà colonisé par l'Empire : `target_owned` avec `colony.read`, sinon
    `target_unavailable` générique.
  - Autres refus : `colonization_active`, `colony_limit` (colonies + COLONIZE actives < 12),
    `package_insufficient`, `colonize_units`, `planet_not_found` (404, monde inconnu ou système
    seulement DETECTED).
- **Snapshot :** les clés v0.4, plus `target_planet_id`, les règles d'expansion acceptées et le rang
  `(due_at, started_at, mission_id)`. Le worker reconstruit le snapshot et le compare exactement ;
  toute dérive bloque la mission sans effet partiel.

## Résolution déterministe

L'ordre des verrous est fixe : le stream d'opérations de l'Empire (tenu par le worker ou la
commande), puis la ligne de la planète cible `FOR UPDATE`. Ce n'est jamais un second stream, et
jamais une planète puis un autre stream.

- **Victoire :** la mission fonde sa colonie si la planète n'a aucune colonie **et** si aucune autre
  COLONIZE vers elle n'est à la fois `active`, non rappelée et mieux classée.
- **Fil `completed`, `returning` ou rappelé :** il ne bloque jamais. Une mission restée `active`
  derrière un événement `blocked` continue de bloquer : c'est un incident opérateur.
- **Ordre des workers sans effet :** toute mission mieux classée a un `due_at` inférieur ou égal,
  donc sa fenêtre de rappel est déjà close. Le résultat ne dépend pas de l'ordre de traitement.
- **Rappel :** il prend le même verrou planète, ce qui le sérialise avec la lecture concurrente.
  Rappel et arrivée sont aussi sérialisés par le stream de l'Empire. On n'obtient jamais une colonie
  créée et un rappel accepté à la fois, ni deux rapports.
- **Succès :** `found_colony` est un initialiseur distinct de la colonie de départ, qui reste
  inchangée.
  - capacités réelles de la planète ;
  - aucune infrastructure ;
  - stocks = **tout** le cargo engagé ;
  - production 0 ;
  - stockage de base ;
  - timeline et stream neufs, ancrés à `due_at`.

  Le colonisateur est consommé, la flotte passe `SETTLED`, et le rapport indique
  `outcome: founded`. Ensuite, `refresh_monitoring` ne fait passer MONITORED que par la présence
  propre, sans `map_system` ni révélation.
- **Échec :** rapport `outcome: failed, reason: target_unavailable`, sans cause détaillée ni
  identité. La flotte reste stationnée dans le système cible, avec son colonisateur et son cargo ; le
  carburant n'est pas remboursé.
- **Invariant de l'étape 9 amendé (A23) :** un handler Flottes ne modifie jamais une colonie
  **existante**. Seule la victoire COLONIZE crée une colonie neuve, dans sa transaction.

## API

L'API Flottes existante est étendue : `POST .../missions/preview` et `.../missions` acceptent
`kind = COLONIZE` avec `target_planet_id`. Le devis renvoie `hops`, le carburant, l'arrivée,
`target_planet_id` et `package_minimum`, sans aucune information d'occupation.

| Action | Droits |
| --- | --- |
| Devis et lancement COLONIZE | `fleet.command` + `galaxy.read` + `colony.expand` |
| `colony.read` | N'est pas exigé ; ne sert qu'à nommer ses propres colonies |
| `colony.construct` | N'est jamais exigé |

Évolutions de la projection :
- `colonies_here` par flotte, filtré par `colony.read` : CHARGER et DÉCHARGER nomment toujours la
  colonie ;
- `target_planet` sur les missions ;
- `colony_id` des rapports masqué sans `colony.read` ;
- planètes connues des systèmes MAPPED ou mieux, avec `colony_id` propre seulement sous
  `colony.read` ;
- bloc `colonization` (règles, devis du colonisateur) ;
- les flottes `SETTLED` sont exclues, comme `MERGED`.

La System View expose seulement `colonization: true|false` (le ruleset propose COLONIZE ou non), et
transmet `colony.expand`.

## UI

**Écran Flottes :**
- COLONIZE n'est proposé que si le ruleset, les droits et un colonisateur à bord le permettent ;
- le monde se choisit parmi la connaissance de l'Empire. Une colonie propre n'est exclue que si
  `colony.read` la nomme ;
- l'occupation est affichée « inconnue », jamais « Libre » ;
- le paquet minimum est affiché, avec le devis serveur (0 saut : aucun carburant, aucun rappel) ;
- l'ordre de colonisateur affiche le prix serveur courant, pour 1 unité ;
- CHARGER et DÉCHARGER exigent le choix explicite d'une colonie dès qu'il y en a plusieurs.

**System View :** bouton « Coloniser… » sur chaque monde sans colonie propre. Il ouvre le même
dialogue Flottes (`fleets/colonize/{empire}/{système}/{planète}`).

**Écran Colonie :** chaque lecture relit aussi la liste des colonies. Une colonie fondée rejoint
donc le sélecteur existant à l'actualisation suivante, sans nouvelle entrée de navigation.

Mobile de 320 à 1440 px, cibles de 44 px, clavier et focus. Un `select` à libellé long ne déborde
jamais d'un dialogue.

## Recette

`scripts/smoke_colonization_compose.py` : projet, bases et volumes `*_test` jetables, durées de test
seulement.
1. Colonisateur commandé dans l'interface, au prix serveur.
2. Paquet chargé dans l'interface.
3. « Coloniser… » depuis la System View, puis fondation par le worker, prouvée en base (stocks =
   paquet, production 0, capacité réelle).
4. La nouvelle colonie apparaît dans le sélecteur.
5. Avec Portal coupé, un Empire rival de test et deux COLONIZE lancées au même instant, résolues par
   deux workers : un seul propriétaire, le meilleur rang, le perdant stationné, aucune identité
   révélée.
6. Expiration de session : réponses 401.

Résultats et CI dans [progress](../../progress.md).
