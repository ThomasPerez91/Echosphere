# Combat MVP — fence temporelle, engagements, API et UI

**Contrat technique de l'étape 12.** Q02 et Q10 sont closes pour le Combat MVP v0.7 seulement
(02/11/2026) ; ce document décrit ce qui est réalisé sur la PR #15.
[Décisions produit](../01-game-design/combat.md#q02q10--décisions-combat-mvp-v07-02112026),
[plan et audit COM00–COM11](../05-project/step-12-plan.md).
Le ruleset `v0.7` est réservé aux nouveaux univers. Les univers v0.1–v0.6 restent inchangés :
aucune adoption, aucune migration de données.

## Ruleset v0.7

- **Base :** `v0.7` = `v0.6`, plus :
  - les classes `interceptor`, `frigate` et `cruiser` dans `fleets.json`, au format inchangé, avec
    cargo 0 et sans cartographie ;
  - `combat.json`, en version `combat-v1` : coque et attaque, matrice des matchups en bps,
    `min_warning_seconds = 86400`, borne de rounds ;
  - `ai.json` en `utility-goals-v2` : objectif défensif `military`, avec les poids validés.
- **Validation stricte :**
  - `combat` est refusé avant v0.7 ;
  - les classes militaires doivent exister dans Flottes ;
  - l'objectif militaire IA doit viser une classe militaire.
- **Modèle IA séparé :** `AIRulesV2` est un modèle distinct. Les dumps v0.6, et donc les
  empreintes de politique épinglées, ne bougent pas. L'empreinte de bootstrap omet une clé `combat`
  absente.

## Résolveur pur (`app.combat.resolver`)

- **Entrée et sortie :** JSON versionné, entiers seulement, aucune base, horloge ni hasard.
- **Round :**
  1. effectifs vivants figés ;
  2. chaque classe vise la classe ennemie vivante au meilleur matchup (égalité départagée dans
     l'ordre canonique de `classes`) ;
  3. dégâts `effectif × attaque × bps`, accumulés par classe cible ; une unité coûte
     `coque × 10000` ;
  4. pertes simultanées. Le surplus envoyé sur une classe éteinte est perdu.
- **Issues :** `attacker_win`, `defender_win`, `mutual_destruction`, `unopposed`.
  `target_unavailable` est décidé hors résolveur.
- **Rejeu :** `resolve(engagement.snapshot.spec) == engagement.result.combat`, à l'identique.
- **Pertes du défenseur :** réparties par `allocate_losses`, au plus fort reste par classe sur les
  effectifs d'avant Combat, départage par id de flotte.

## Persistance (migration 0012)

- **`stream_fences` :** générique, `(stream, fence_at, owner, released_at)`.
- **`combat_engagements` :**
  - la mission ATTACK (unique), les Empires attaquant et défenseur (ce dernier interne et nullable) ;
  - la planète et le système cibles ;
  - `started_at`, `travel_arrival_at`, `battle_at` ;
  - l'état `pending`, `resolved`, `cancelled` ou `blocked`, les essais, le snapshot, le résultat et
    `processed_at` ;
  - un index de rang `(battle_at, started_at, id)`.
- **`combat_reports` :** un rapport par camp, écrit seulement par la résolution.
- **Missions et flottes :**
  - `fleet_missions.kind` accepte `ATTACK`, avec des CHECK dédiés : cible obligatoire, 0 saut
    possible, `due_at = battle_at`, rappel jusqu'à `battle_at`, retour après bataille ;
  - `fleets.status` accepte `DESTROYED`, réservé aux flottes opérationnelles, ligne conservée.
- **Permissions :** `combat.read` et `combat.attack` portent le total à 15, sans aucune attribution
  automatique.
- **Downgrade :** refusé tant que des données ou des droits Combat existent.

## Fence temporelle

Une fence non levée gèle son stream à `fence_at`, pour le worker comme pour le rattrapage. La règle
est inclusive : tout ce qui est dû au plus tard à `fence_at` est appliqué, rien après.
- Le curseur ne dépasse jamais la fence.
- Un rattrapage vers une cible plus lointaine renvoie `fenced`, et les commandes Flottes sont alors
  refusées temporairement avec `combat_pending` (409).
- L'IA reporte son tour sans erreur ni consommation de séquence.

L'état militaire d'un Empire vit entièrement sur son stream d'opérations : production, arrivées,
retours. Une production ou une arrivée de 10:05 ne participe donc jamais à une bataille de 10:00,
même si le worker Combat ne passe qu'à 10:10. Preuve : test PostgreSQL
`test_production_and_reinforcement_join_only_up_to_battle_at_even_with_a_late_worker`.

## Mission ATTACK

- **Conditions :** planète connue (PlanetKnowledge, système MAPPED ou mieux), chemin connu, classes
  militaires seulement, cargo nul. Les erreurs sont `attack_units`, `attack_cargo`,
  `planet_not_found`, `target_owned` (`target_unavailable` sans `colony.read`) et
  `combat_unavailable`.
- **Coût :** `2 × sauts × Σ(effectif × Flux/saut)`, payé une seule fois au départ par la colonie
  d'attache. 0 saut = 0 Flux.
- **Bataille :** `battle_at = max(travel_arrival_at, started_at + 24 h)`. Aucun `FLEET_ARRIVAL`.
- **Verrous au lancement :** stream d'opérations de l'attaquant, puis ligne Planet (verrou partagé
  avec COLONIZE). L'occupant présent à cet instant est lié en interne comme défenseur. Rien n'est
  renvoyé sur l'occupation ou la défense : le devis et la réponse sont identiques pour une cible
  vide ou occupée.
- **Fences :** posées sur le stream de l'attaquant (déjà verrouillé) et, si un défenseur est lié,
  sur le sien **sans le verrouiller** (son curseur ≤ heure réelle < `battle_at`).
- **Rappel :** possible tant que `now < battle_at`.
  - en transit : rappel symétrique ;
  - arrivé mais avant la bataille : retour = rappel + trajet ;
  - local : stationnement immédiat.

  L'engagement passe `cancelled`, les fences sont levées et l'alerte du défenseur devient
  « annulée ». Après la bataille, un rappel est refusé avec `recall_too_late`.

## Orchestrateur `app.combat.worker`

Le processus utilise la même image ; c'est le service Compose `combat-worker`, présent par défaut et
inactif sans engagement. Il tourne hors de tout handler TimeEngine, sans `COMBAT_BARRIER`.
1. Choisir les engagements dus par rang, en excluant d'emblée ceux qui attendent un engagement
   mieux classé et non résolu (même système ou même Empire). Paginer au-delà de ceux qui ne
   peuvent pas aboutir maintenant (événement bloqué, contention). Ainsi, un blocage local
   n'affame jamais une bataille indépendante.
   Pour chacun, verrouiller les streams d'opérations impliqués dans
   l'ordre de leurs UUID, puis la ligne de l'engagement.
2. Refuser tant qu'un engagement mieux classé reste non résolu (`pending` ou `blocked`) sur le même
   système ou avec le même Empire.
3. Rattraper exactement jusqu'à `battle_at`. Une fence antérieure ou un événement bloqué
   interdisent la bataille sur un état partiel.
4. Vérifier le snapshot de mission, prendre les forces militaires, résoudre, appliquer les pertes
   (civils et cargo intacts, flottes opérationnelles vides `DESTROYED`, garnison vide stationnée),
   écrire les rapports, planifier le retour (`FLEET_RETURN` à `battle_at + trajet`, stationnement
   immédiat en local) et lever les fences. Le tout se fait dans une seule transaction.
5. **Reprise :**
   - crash avant commit : aucun effet ;
   - après commit : jamais de seconde résolution ;
   - erreur technique : retry, puis `blocked`. Les fences restent posées ; l'opérateur utilise
     `--blocked` et `--retry`.

## API et UI

- **Flottes :** `POST .../missions/preview` et `.../missions` acceptent `kind = ATTACK` avec
  `target_planet_id`. Droits exigés : `fleet.command`, `galaxy.read`, `combat.read` et
  `combat.attack`. `colony.read` n'est pas obligatoire.
  - le devis donne `hops`, le carburant aller-retour, l'arrivée, `battle_at` et les unités ;
  - la projection ajoute à chaque mission un `attack` (engagement, `battle_at`, état ; jamais le
    défenseur) ;
  - le bloc `combat` contient les classes, la fenêtre, les `alerts` et les `reports`, ces deux
    derniers seulement avec `combat.read` ;
  - les flottes `DESTROYED` sont exclues.
- **Ordre des alertes :** menaces actives d'abord, bataille la plus proche en tête. L'historique
  des annulations ne remplit que le reste et ne masque jamais une menace.
- **Colonie :** `incoming` liste l'instant et l'état des attaques annoncées sur la planète, avec
  `combat.read`.
- **System View :** expose `combat: true|false` et relaie les droits Combat.
- **UI :**
  - production militaire signalée ;
  - dialogue ATTACK : militaires seulement, texte « Occupation et défense non confirmées. », devis
    complet ;
  - phases « en route », « approche », « résolution », « retour après la bataille » ;
  - rappel jusqu'à la bataille ;
  - « Force hostile en approche » : cible et instant seulement ;
  - rapports de combat datés ;
  - « Attaquer… » dans la System View, alerte sur l'écran Colonie.
- **Validateurs :** ils refusent une alerte ou un état d'attaque qui nommerait l'autre camp, ainsi
  que toute donnée Combat sans `combat.read`. Tests responsive à 320, 390, 768 et 1440 px.

## IA v0.7

- **Objectif `military` :** maintenir `target_per_colony` intercepteurs à chaque colonie
  (stationnés et en commande), produits par le service commun.
- **Alerte :** une alerte propre en attente sur une colonie sous sa cible porte l'utilité à
  `alert_utility` et rend ce candidat **prioritaire**, sur le modèle de la priorité de bootstrap de
  Q11. Les poids validés ne changent pas.
  - la priorité est bornée par la cible ;
  - elle respecte la réserve, et toujours une commande par tour ;
  - les candidats v0.6 n'ont pas de clé `priority`.
- **Aucune offensive :** aucun candidat ATTACK ; le dispatcher refuse un ATTACK forgé. L'IA peut
  être attaquée normalement.

## Recette

`scripts/smoke_combat_compose.py` (CI compose-smoke) utilise des bases et volumes `*_test` jetables
et le ruleset v0.7 inchangé :
1. Bootstrap opérateur v0.7 (humain + IA). L'humain entre par le handoff réel et voit la production
   militaire, puis sa page est fermée et Portal arrêté.
2. Horloge de test sur les vraies classes, sans aucune écriture d'aide. L'humain cartographie par
   SURVEY, produit, puis lance deux ATTACK au même instant sur la colonie IA. L'IA est alertée (cible
   et instant seulement) et produit des intercepteurs.
3. Deux `combat-worker` réels sur l'horloge système :
   - résolution dans l'ordre du rang ; la seconde bataille affronte les survivants de la première ;
   - aucune perte en double, rejeu exact ;
   - colonie IA intacte, fences levées, retours effectués.
4. L'humain voit ses deux rapports datés, puis sa session expire avec un 401.

## Limites

L'équilibrage est provisoire. Il n'y a ni modules de défense (Q30–Q38 reportés), ni butin,
occupation, siège ou bombardement, ni relations (étape 13), ni offensive IA (Q18). Un engagement
`blocked` gèle les streams concernés jusqu'à l'intervention de l'opérateur, choix d'intégrité
documenté. Résultats et CI dans [progress](../../progress.md).

v0.8 (étape 13) : un pacte couvrant `battle_at` annule la bataille (`voided_by_pact`) ; une bataille
résolue date l'acte hostile de l'attaquant et crée les contacts. [Relations](relations-api-ui.md).
