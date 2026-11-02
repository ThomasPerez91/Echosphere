# Présence frontalière — contrat technique (13B, ruleset v0.9)

**Statut : implémenté sur la PR #17 (B00–B07, Draft), non validé à l'exécution (PostgreSQL,
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
| `fleet_mission_passages` | Chaque système réellement traversé, à son instant logique ; `cancelled_at` si jamais atteint (rappel, destruction) |
| `fleets.protocol` | Protocole courant d'une flotte TASK stationnée (CHECK) |
| `fleet_protocol_periods` | Historique daté des protocoles (`started_at <= t < ended_at`) : base de toute évaluation |
| `frontier_detections` | Faits de détection uniques par (passage, flotte surveillante, rôle) ; identité interne, projetée seulement si identifiée |
| `frontier_encounters` | Réactions automatiques planifiées : `engagement` (AMBUSH/INTERCEPTION) ou `retreat` (FRIENDLY_CONTACT), état, issue, résultat |
| `relation_contacts.first_source` | Ajout de `frontier` (présentation FRIENDLY_CONTACT) |
| `fleet_operations.kind` | Ajout de `protocol` (registre d'idempotence) |

## Chronologie et verrous

- Passages : calculés par `app/frontier/transit.py` (pur) dans la transaction qui décide le
  mouvement, sous le verrou du stream d'opérations de l'Empire qui bouge. Le k-ième de n systèmes
  est atteint à `started_at + ceil(travel × k / n)` ; le retour est le miroir de l'aller.
- Détection : événement `FRONTIER_PASSAGE` sur le stream de l'Empire en mouvement, à `entered_at` ;
  le handler lit les périodes couvrant l'instant (`FOR SHARE`) et écrit des faits uniques. Écart
  à D2 (stream du détecteur) documenté dans le plan, à confirmer.
- Contacts `frontier` matérialisés aux points de lecture (Galaxie, System View, Relations) et après
  la commande du tour IA, jamais dans un handler (ordre global paire → contact).
- Réactions : planifiées quand période et passage sont connus avant l'instant ; fences
  (`frontier:<id>`) à `entered_at − 1 µs` sur les deux streams d'opérations (engagement) ou à
  `entered_at` sur le stream du surveillant et sa Colony d'attache (repli). Résolues par
  `app.frontier.orchestrator.FrontierOrchestrator` dans le processus `combat-worker` : streams
  triés → rencontre → paire → contacts, rang `(instant, type, mission, passage, flotte)`.

## Résolution

| Type | Ordre des tests | Effets |
| --- | --- | --- |
| Engagement | validité (passage non annulé, période couvrante, flottes en place) → pacte → ennemi connu (AMBUSH) → unités militaires du surveillant → unités militaires de la flotte en mouvement | Combat via `app.combat.resolver` (surveillant = attaquant) ; pertes militaires seules ; flotte en mouvement vidée : `DESTROYED`, mission terminée à l'instant, arrivée/retour et entrées suivantes annulés, bataille planétaire en attente annulée ; survivants poursuivent ; acte hostile du surveillant, contacts `combat`, rapports des deux côtés |
| Repli | validité → présentation (détection) → destination D7 → lancement Flottes normal à `entered_at` | `retreated` (mission DEPLOY vers le système précédent ou RETURN vers la colonie d'attache), `retreat_failed` (raison, ex. fonds insuffisants), `retreat_impossible` |

Issues sans combat (`pact`, `not_enemy`, `no_force`, `no_military_target`, `void`) : aucune perte,
aucun acte hostile, **aucun rapport** (la raison révélerait la force adverse, D3). La vérification de
snapshot de mission ajoute les pertes d'interception pour retrouver la composition de lancement.

## API Game

| Méthode | Route | Droits |
| --- | --- | --- |
| POST | `/game/{universe}/fleets/{empire}/{fleet}/protocol` `{idempotency_key, protocol \| null}` | `fleet.read` + `fleet.command`, CSRF |
| GET | `/game/{universe}/fleets/{empire}` → `fleets[].protocol`, `frontier.{protocols, detections, encounters}` | `fleet.read` |

Codes : `frontier_unavailable` (ruleset < v0.9), `protocol_unavailable`, `protocol_task` (409),
`combat_pending` (409, rencontre due non encore résolue). Détection : `{id, system, detected_at,
role, friendly, empire|null}`. Rapport d'engagement : rôle, protocole (côté surveillant seulement),
issue selon la perspective, adversaire, forces militaires engagées/pertes/survivants, rounds.
Rapport de repli : issue, raison, destination. Le client refuse toute projection plus riche.

## Interface

Flottes : protocole courant et sélecteur des quatre modes (explication de chacun) sur les flottes
opérationnelles stationnées, section « Frontière » (détections, rencontres, replis), rapport de
mission « détruite par une interception en route ». Mêmes règles de commande que les autres ordres.

## Opérateur

`python -m app.combat.worker --blocked` liste aussi les réactions bloquées ;
`--retry-frontier <id>` remet en file une réaction réparée.

## Validation

| Niveau | Contenu | État |
| --- | --- | --- |
| Pur (Fast CI) | `test_frontier_transit.py`, `test_frontier_rules.py`, `test_frontier_encounter.py` | Exécuté |
| Frontend (Fast CI) | Vitest Flottes (protocole, panneau Frontière, validateur), lint, build | Exécuté en CI |
| PostgreSQL | `tests/integration/test_frontier.py` (passages, protocoles, détection, présentation, interceptions, embuscade, pacte, civils, rang, repli) | **À exécuter** |
| Migration | Alembic 0014 upgrade/check/downgrade sur base jetable | **À exécuter** |
| Compose / Chromium | Aucune recette 13B dédiée encore | **À écrire et exécuter (B09)** |
