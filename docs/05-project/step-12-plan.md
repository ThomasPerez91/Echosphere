# Étape 12 — Combat MVP

**État courant : COM00 checkpoint post-merge ; COM01 audit en cours.**
Base master `f79d9f6d0c3ebd9d230344b5a0c2aeaef9f4ce6b` : étape 11 Première IA intégrée via PR #14,
CI post-merge 41358533969 success 5/5 vérifiée le 02/11/2026, Q11 close. Branche unique
`work/step-12-combat`, une PR Draft vers master. Claude Code seul écrivain du lot. Aucun merge
autorisé ; étape 13 Relations non commencée.

Sortie roadmap : résolution et rapports militaires simples ; Q02/Q10 arbitrées, simulation et rejeu
des résultats. **Q02 et Q10 sont closes pour le Combat MVP v0.7 seulement** par validation
utilisateur explicite du 02/11/2026 : [décisions transcrites](../01-game-design/combat.md#q02q10--décisions-combat-mvp-v07-02112026).
COM01 n'est pas un gate produit : seule une contradiction structurelle arrêterait le lot.

| Ticket | Travail et preuve attendue |
| --- | --- |
| COM00 | Synchro post-merge, branche, PR Draft, statuts canoniques, transcription Q02/Q10, ce plan |
| COM01 | Audit du code intégré, réponse prouvée à la question de la fence temporelle |
| COM02 | Ruleset v0.7 (copie v0.6, classes militaires, `combat.json`) et résolveur pur déterministe |
| COM03 | Migration 0012, persistance des engagements/alertes/rapports, `combat.read`/`combat.attack` (15) |
| COM04 | Mission ATTACK (lancement sans fuite, défenseur lié, 0 saut, carburant aller-retour), alerte, rappel |
| COM05 | Fence temporelle et orchestrateur Combat `app.combat.worker` hors handler |
| COM06 | Pertes (plus fort reste), DESTROYED, rapports datés, retour |
| COM07 | API et UI (Flottes, System View « Attaquer… », alertes Colony), responsive |
| COM08 | IA v0.7 : objectif défensif `military`, sans offensive |
| COM09 | Concurrence, Fog, rejeu, régressions et compatibilité v0.1–v0.6 |
| COM10 | Recette Compose réelle Combat |
| COM11 | Revue indépendante, CI, docs, passation ; Ready ; aucun merge |

Hors périmètre : étape 13, relations, diplomatie, commerce, conquête, occupation, siège,
bombardement, butin, modules de défense, espionnage, moral, designer, XP, réparation, entretien,
conditions de victoire. Q03, Q04 global, Q14, Q18 et Q25 restent ouvertes ou futures.

## COM01 — audit du code intégré (master `f79d9f6`)

Lecture des documents produit exigés (vision, Combat, Flottes, Fog, sessions, modes, défense,
IA, Colonisation, économie) et du code intégré. Seul le code fait preuve d'implémentation.

### Constats prouvés

- **Ordre strict par stream :** le Scheduler ne traite d'un stream que son premier événement non
  terminé, dans l'ordre `(due_at, sequence)`. Un premier événement en attente bloque ses
  successeurs, pour le worker (`app/simulation/scheduler.py:180`) comme pour le rattrapage
  (`catch_up_stream`, `:218`, qui renvoie `complete=False` dès qu'il s'arrête). Aucun stream ne
  dépasse l'heure réelle (`:231`) ; `schedule` refuse toute échéance antérieure au curseur (`:105`).
- **État militaire d'un Empire = un seul stream :** l'achèvement de production
  `SHIP_ORDER_COMPLETE` (`app/fleet/service.py:194`), les arrivées `FLEET_ARRIVAL` (`:830`) et les
  retours `FLEET_RETURN` (`:1190`) vivent tous sur le stream d'opérations de l'Empire. Toute
  commande Flottes (production, détachement, fusion, cargo, lancement, rappel) passe d'abord par
  `operations()` (`:48`), qui verrouille ce stream et le rattrape jusqu'à l'heure de la commande ;
  un rattrapage incomplet refuse la commande. Les streams Colony et Research ne portent aucun état
  militaire. Les GET Flottes ne rattrapent pas ce stream.
- **Ordre de verrous existant :** stream d'opérations de l'Empire, puis ligne Planet
  (`lock_target`, `:1074`, COLONIZE). Aucun handler ne prend deux streams. L'orchestrateur IA prend
  opérations → Research → colonies (`app/ai/orchestrator.py:68`, `:83`) ; un rattrapage
  d'opérations incomplet y est aujourd'hui une erreur technique (retry puis `blocked`, `:164`).
- **Contraintes de base :** les CHECK de `fleet_missions` ne connaissent que DEPLOY, SURVEY,
  RETURN et COLONIZE.
  - route et durée : seul COLONIZE peut rester sur place ;
  - échéance égale à l'arrivée, sauf SURVEY ;
  - rappel symétrique seulement avant l'arrivée ;
  - `returning` exige un rappel.

  Le statut `fleets` ne connaît ni ATTACK ni `DESTROYED` : il faut une migration 0012 additive
  avec des branches ATTACK explicites, sans modifier les anciennes migrations.
- **Snapshots v0.4/v0.5 :** clés exactes vérifiées par le worker (`verify_mission_snapshot`). Les
  stats Combat vont donc dans `combat.json`, et le format `fleets.json` (`ShipClass`) ne change pas.
- **Permissions :** 13 droits partout ; l'IA a un jeu de capabilities fixe, sans `combat.attack`.

### Contradictions

Aucune contradiction structurelle avec Q02/Q10. Deux adaptations techniques sont nécessaires,
dans le périmètre :
1. un mécanisme de fence de stream que le Scheduler générique respecte ;
2. un traitement « attendre » (et non une erreur technique) du `combat_pending` dans
   l'orchestrateur IA.

### Question de la fence temporelle — réponse prouvée

> Comment une production ou une arrivée de 10:05 ne participe-t-elle jamais à une bataille due à
> 10:00 si le worker Combat ne passe qu'à 10:10 ?

**Mécanisme.** Une table générique `stream_fences` contient `(stream, fence_at, owner,
released_at)`, sans dépendance au Combat dans le Scheduler.
- Au lancement d'ATTACK, une fence est posée sur le stream d'opérations de l'attaquant (déjà
  verrouillé par la commande) et, si un défenseur est lié, sur celui du défenseur, avec
  `fence_at = battle_at`.
- La fence du défenseur est posée **sans verrouiller son stream** : son curseur est au plus l'heure
  réelle (`scheduler.py:231`), et `battle_at ≥ maintenant + 24 h`. Aucune transaction du défenseur
  ne peut avoir dépassé `battle_at`, et aucun ordre de verrous inter-Empires n'est créé dans une
  commande.

**Règle du Scheduler (worker et rattrapage).** Tant qu'une fence non levée existe sur un stream :
- un événement `due_at > fence_at` n'est jamais appliqué ;
- le curseur ne dépasse jamais `fence_at` ;
- un rattrapage vers une cible postérieure renvoie `complete=False, fenced=True`.

La sémantique est inclusive et sans dépendance à l'ordre de création : la bataille voit **tous**
les événements `due_at ≤ battle_at`, et aucun après.

**Conséquences pour l'exemple de 10:05 :**
- **Worker :** il ne choisit jamais le stream du défenseur pour l'événement de 10:05 (filtre SQL
  sur la fence non levée) ;
- **Commandes du défenseur :** une commande à 10:07 rattrape vers 10:07, s'arrête à 10:00 et est
  refusée avec `combat_pending` (temporaire) ;
- **IA :** son tour est reporté sans erreur ni consommation de séquence ;
- **Commandes antérieures :** une commande antérieure à 10:00 n'a d'effet immédiat qu'à son heure
  (≤ 10:00), et ses effets futurs sont des événements bloqués par la fence ;
- **Orchestrateur Combat à 10:10 :**
  1. verrouille les streams d'opérations impliqués dans l'ordre de leurs UUID ;
  2. les rattrape exactement jusqu'à 10:00 ;
  3. vérifie que ce rattrapage est complet ;
  4. prend le snapshot, résout, applique les pertes et planifie le retour ;
  5. lève les fences dans la même transaction.

  L'événement de 10:05 ne s'applique qu'ensuite, sur l'état d'après bataille.
- **Crash avant commit :** aucune perte, fence maintenue.
- **Après commit :** la bataille est `resolved`, sans seconde résolution.

**Preuves prévues (COM05/COM09)** :
- tests PostgreSQL production/renfort à `battle_at − ε`, `= battle_at` et `+ 5 min`, avec un worker
  Combat volontairement retardé ;
- commande du défenseur refusée `combat_pending` ;
- tour IA reporté ;
- deux orchestrateurs, crash avant et après commit.

**Rappels et cas limites :**
- un rappel (avant `battle_at`) annule l'engagement et lève les fences ;
- une attaque sans défenseur lié pose sa seule fence attaquant, ce qui garde le retour planifiable
  après `battle_at` ;
- plusieurs attaques se départagent au rang `(battle_at, started_at, engagement_id)` ; une fence
  antérieure non levée empêche par construction un rattrapage plus lointain.

### Architecture retenue

- **v0.7 :** ruleset = v0.6, plus les classes militaires de `fleets.json` (format inchangé), plus
  `combat.json` (stats, matchups, fenêtre de 24 h, version), plus `ai.json` v0.7
  (`utility-goals-v2`, objectif `military`).
- **Résolveur `app.combat.resolver` :** pur, JSON versionné, entiers, rounds simultanés.
- **Migration 0012 :**
  - tables `stream_fences`, `combat_engagements` (défenseur interne, rang, état, snapshot,
    résultat) et `combat_reports` (un rapport par camp, après bataille) ;
  - mission `ATTACK`, flotte `DESTROYED` ;
  - 15 permissions ;
  - downgrade refusé avec données.
- **Lancement d'ATTACK :** dans le service Flottes. Ordre des verrous : stream de l'attaquant, puis
  ligne Planet (partagée avec COLONIZE). Pas de `FLEET_ARRIVAL`.
- **Orchestrateur `app.combat.worker` :**
  - même image, hors handler ;
  - engagement dû choisi par rang ;
  - streams triés par UUID, puis l'engagement `FOR UPDATE` ;
  - rattrapage exact à la fence, puis blocage par une attaque mieux classée (même système ou même
    Empire) ;
  - snapshot, résolution, pertes (plus fort reste), rapports, retour, levée des fences.
- **Retour :** `FLEET_RETURN` sur le stream de l'attaquant, avec une branche ATTACK (après bataille
  ou rappel en approche).
