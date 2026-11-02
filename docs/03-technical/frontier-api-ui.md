# Présence frontalière — contrat technique (13B, ruleset v0.9)

**Statut : implémenté sur la PR #17 (B00–B07 + correctifs C01–C05, Draft), non validé à l'exécution (PostgreSQL,
Compose, Chromium à faire sur poste local) ; non fusionné.** Règles : [premier contact](../01-game-design/first-contact.md),
décisions [D1–D7](../01-game-design/first-contact.md#décisions-d1d7--02112026), plan et écarts :
[étape 13B](../05-project/step-13b-plan.md). Dépend de la PR #16 (étape 13, non fusionnée).

## Ruleset v0.9

Copie complète de v0.8 + `frontier.json` : `protocols` (les quatre, ordre canonique) et
`ambush_hostility_seconds` (72 h, D4). Aucun niveau de détection ni technologie (Q58 ouverte :
niveau 0 pour tous). v0.1–v0.8 et leurs digests inchangés ; aucun univers existant adopté.

## Données (migration 0014, non intégrée)

| Table / colonne | Rôle |
| --- | --- |
| `fleet_mission_passages` | Chaque système réellement traversé, à son instant logique ; état `pending`/`resolved`/`cancelled`/`blocked` (+ tentatives, erreur) ; `cancelled_at` si jamais atteint ; ligne `local` (séquence 0) pour une ATTACK de 0 saut |
| `fleets.protocol` | Protocole courant d'une flotte TASK stationnée (CHECK) |
| `fleet_protocol_periods` | Historique daté des protocoles (`started_at <= t < ended_at`) : base de toute évaluation |
| `frontier_detections` | Faits de détection uniques par (passage, flotte surveillante, rôle) ; identité interne, projetée seulement si identifiée |
| `frontier_encounters` | `engagement` (AMBUSH/INTERCEPTION) créé et résolu avec son entrée ; `retreat` (FRIENDLY_CONTACT) planifié puis résolu ; état, issue, résultat |
| `relation_contacts.first_source` | Ajout de `frontier` (présentation FRIENDLY_CONTACT) |
| `fleet_operations.kind` | Ajout de `protocol` (registre d'idempotence) |

## Chronologie et verrous (C01/C02, 02/11/2026)

- **Passages** : calculés par `app/frontier/transit.py` (pur) dans la transaction qui décide le
  mouvement, sous le verrou du stream d'opérations de l'Empire qui bouge. Le k-ième de n systèmes
  est atteint à `started_at + ceil(travel × k / n)` ; le retour est le miroir de l'aller. Chaque
  passage pose une fence `frontier-passage:<mission>:<n>` à `entered_at − 1 µs` sur ce **seul**
  stream (le sien) : l'Empire en mouvement ne dépasse jamais une entrée non résolue. Plus aucun
  événement ni handler de passage.
- **Résolution d'une entrée** (`FrontierOrchestrator`, processus `combat-worker`) : verrouille, triés
  par UUID et avec `lock_timeout`, le stream de l'Empire en mouvement et celui de chaque Empire
  pouvant tenir un protocole dans le système (flotte présente, mission en route vers lui ou de
  retour), puis la ligne de passage ; refuse tant qu'une entrée mieux classée du même système ou
  d'un de ces Empires est en attente ; amène chaque stream exactement à `entered_at − 1 µs` (ou
  constate qu'il l'a dépassé : rien d'antérieur ne peut plus y être daté) ; écrit détections puis
  engagements ; libère la fence ; une transaction.
- **Pourquoi aucune entrée n'est perdue (C02)** : toute modification de période se fait sous le
  verrou du stream de son Empire. Commande validée avant : vue. Commande en cours : la résolution
  attend son verrou puis la voit. Commande datée avant `t` mais exécutée après la résolution (elle
  attendait le verrou) : refusée (`fleet_busy`, `check_not_behind`) ou en échec de rattrapage
  arrière, jamais enregistrée derrière une entrée résolue. Une commande postérieure est datée ≥ `t`
  et, par la règle de couverture `started_at < t <= ended_at`, ne change rien à `t`.
- **Flotte du surveillant figée (C01)** : tant qu'une entrée étrangère échue couverte par sa période
  AMBUSH/INTERCEPTION n'est pas résolue, scission, fusion (source ou cible) et départ de cette flotte
  sont refusés (`combat_pending`, `guard_fleet_change`) ; une bataille planétaire du système attend
  aussi (bloqueur Combat). L'engagement voit donc la composition à `t` quel que soit le retard.
- **Déterminisme de D2** : l'évaluation ne dépend que de faits datés (périodes, passages, contacts,
  actes hostiles, pactes) et d'états figés à `t − 1 µs` ; l'ordre des workers et des commandes ne
  peut changer ni l'ensemble des périodes couvrantes ni les compositions engagées. D2 est respecté
  sans écrire dans le stream du détecteur : le stream de l'Empire en mouvement sert de point d'arrêt,
  les streams des surveillants sont verrouillés et réglés à l'instant.
- **Replis (D7)** : seules réactions planifiées. Au lancement d'une ATTACK (la fence de bataille tient
  déjà le stream du défenseur `FOR KEY SHARE`), ou à l'activation de FRIENDLY_CONTACT (stream propre
  `FOR UPDATE`) : les deux ordres de validation sont sérialisés sur ce même verrou. Fences
  `frontier:<id>` à l'instant de l'acte hostile sur le stream d'opérations du surveillant et la
  Colony d'attache de la flotte. Le curseur est relu sous `FOR KEY SHARE` avant la pose.
- **Verrous inter-Empires** : aucun verrou `FOR UPDATE` sur le stream d'un autre Empire hors des
  orchestrateurs (ordre UUID + `lock_timeout`, comme Combat v0.7). Seule attente croisée côté
  commandes : la pose de fences de bataille/repli sur le stream du défenseur au lancement d'une
  ATTACK, déjà présente en v0.7 ; deux lancements croisés simultanés restent résolus par la
  détection d'interblocage PostgreSQL (une commande échoue, l'intention est rejouable).
- Contacts `frontier` matérialisés aux points de lecture (Galaxie, System View, Relations) et après
  la commande du tour IA, jamais dans une résolution (ordre global paire → contact).

## Départage temporel (C04)

| Même instant `t` | Ordre |
| --- | --- |
| Entrées entre elles | `(entered_at, mission_id, sequence)` ; surveillants d'une entrée par `fleet_id` |
| Entrée / bataille planétaire | Entrée d'abord (état strictement avant `t`), bataille ensuite (inclusive, Q02 inchangé) |
| Entrée / repli qu'elle déclenche | Entrée (présentation) puis repli à `t` |
| Repli / bataille à `t` | Repli d'abord : la flotte amicale est partie |
| Protocole activé / arrêté à `t` | Non couvrant / encore couvrant |

## Retard du worker et reprise (C05)

- Indisponibilité : les entrées échues attendent ; à la reprise, résolution dans l'ordre du rang,
  sur les mêmes faits datés (tests de redémarrage et de crash avant commit).
- Retards de plusieurs sauts : chaque entrée suivante est figée derrière la précédente ; plus aucune
  décision tardive ne dépend du curseur d'un autre Empire (les retours après bataille, rappels et
  replis ne posent des fences que sur le stream de l'Empire qui bouge ou sur des instants futurs).
- Famine : une entrée bloquée ne retient que les entrées du même système ou du même Empire ; les
  autres pages avancent. Limite : l'Empire en mouvement reste figé (commandes `combat_pending`)
  jusqu'à la résolution ; un blocage opérateur prolongé le gèle (jamais d'omission).
- Diagnostics : `--blocked` (engagements, réactions, entrées), `--retry-passage <mission>:<n>`,
  `--lag` (plus ancienne entrée/réaction échue, alerte au-delà de 300 s), avertissement journalisé
  par le worker à chaque boucle en retard.
- Évolution distincte non faite : résolution partielle par Empire (débloquer les commandes sans
  rapport avec la flotte en mouvement) — demanderait des fences par flotte, hors 13B.

## API Game

| Méthode | Route | Droits |
| --- | --- | --- |
| POST | `/game/{universe}/fleets/{empire}/{fleet}/protocol` `{idempotency_key, protocol \| null}` | `fleet.read` + `fleet.command`, CSRF |
| GET | `/game/{universe}/fleets/{empire}` → `fleets[].protocol`, `frontier.{protocols, detections, encounters}` | `fleet.read` |

Codes : `frontier_unavailable` (ruleset < v0.9), `protocol_unavailable`, `protocol_task` (409),
`combat_pending` (409, entrée ou repli échu non encore résolu), `fleet_busy` (503, commande datée
derrière une entrée déjà résolue, ou stream du défenseur avancé pendant une ATTACK locale : rejouer). Détection : `{id, system, detected_at,
role, friendly, empire|null}`. Rapport d'engagement : rôle, protocole (côté surveillant seulement),
issue selon la perspective, adversaire, forces militaires engagées/pertes/survivants, rounds.
Rapport de repli : issue, raison, destination. Le client refuse toute projection plus riche.

## Interface

Flottes : protocole courant et sélecteur des quatre modes (explication de chacun) sur les flottes
opérationnelles stationnées, section « Frontière » (détections, rencontres, replis), rapport de
mission « détruite par une interception en route ». Mêmes règles de commande que les autres ordres.

## IA (B08)

Policy `utility-goals-v4` (v0.9 seulement, `AIRulesV4`, section `frontier` de `ai.json`).
`app/ai/observation.py` : `protocol_fleets` (flottes TASK stationnées dans un système de colonie
propre, hors logistique pure, bornées à 64) ajoutées après les colonies à la page circulaire
`military` (même budget de 16) ; `protocol_posture` calcule la posture voulue (AMBUSH → FRIENDLY →
SURVEILLANCE) depuis contacts, paires, alertes et détections propres ; candidat `protocol`
seulement si elle diffère du protocole courant ; observation `frontier` (flotte, système, courant,
voulu, base) pour l'explication. `app/ai/dispatcher.py` : opération `protocol` →
`fleet.set_protocol` (même service que l'API), refus `ai_protocol_denied` hors liste du profil
(jamais INTERCEPTION, jamais AMBUSH prudent). Tests : `tests/test_frontier_rules.py` (pur),
`tests/integration/test_frontier_ai.py` (PostgreSQL, non exécuté).

## Opérateur

`python -m app.combat.worker --blocked` liste aussi réactions et entrées bloquées ;
`--retry-frontier <id>` remet en file un repli réparé, `--retry-passage <mission>:<n>` une entrée ;
`--lag` mesure le retard frontalier (alerte > 300 s).

## Validation

| Niveau | Contenu | État |
| --- | --- | --- |
| Pur (Fast CI) | `test_frontier_transit.py`, `test_frontier_rules.py`, `test_frontier_encounter.py` | Exécuté |
| Frontend (Fast CI) | Vitest Flottes (protocole, panneau Frontière, validateur), lint, build | Exécuté en CI |
| PostgreSQL | `tests/integration/test_frontier.py` (passages et fences, protocoles, détection, couverture à `t`, présentation, interceptions, embuscade, pacte, civils, rang, bataille après entrée, repli distant et local, ciblage ; concurrence C02 dans les deux ordres, rejeu, crash/redémarrage) | **À exécuter** |
| Migration | Alembic 0014 upgrade/check/downgrade sur base jetable | **À exécuter** |
| Compose / Chromium | Aucune recette 13B dédiée encore | **À écrire et exécuter (B09)** |
