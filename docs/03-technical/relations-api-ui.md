# Relations — contrat technique (étape 13, ruleset v0.8)

**Statut : implémenté sur la PR #16 (R02–R10), en attente de validation locale PostgreSQL/Compose
et de revue ; non fusionné.** Décisions produit : [Q18](../01-game-design/relations.md#q18--validation-avec-amendements-02112026).
Hors périmètre : [présence frontalière et premier contact (13B)](../01-game-design/first-contact.md).

## Données (migration 0013)

| Table | Rôle | Garanties |
| --- | --- | --- |
| `relation_contacts` | « observateur connaît observé », orienté, durable | PK (observateur, observé), FK Empires/planète par univers, `first_source` ∈ {combat, presence}, dates monotones |
| `relation_pairs` | Une ligne par paire non ordonnée (low < high) : proposition ouverte, délais après refus, dernier acte hostile de chaque camp | CHECK ordre, cohérence et camp de la proposition |
| `relation_pacts` | Acceptation immuable ; un seul préavis (`notice_at`, `ends_at`) | Signataires distincts, préavis cohérent, au plus un pacte sans préavis par paire (index unique partiel) |
| `relation_events` | Journal immuable et registre d'idempotence des négociations | UNIQUE (acteur, clé), FK paire |

Migration métier non destructive, sans transformation des données historiques, avec extension
contrôlée de la contrainte des droits (`ck_empire_bindings_binding_permissions`, 17 droits).
Downgrade refusé tant qu'une table relations ou un droit `relations.*` est peuplé. Aucun grant
humain automatique.

## Règles de date (pures, `app/relations/rules.py`)

- Proposition ouverte tant que `at < proposal_expires_at` (72 h) ; aucune échéance planifiée.
- Pacte couvrant `t` : `accepted_at <= t < ends_at` (`ends_at` NULL = sans préavis).
- Rupture : `ends_at = notice_at + 24 h` ; un préavis donné après un instant déjà écoulé ne
  « découvre » jamais cet instant (fin toujours postérieure).
- Délai après refus : l'auteur refusé ne repropose pas au même Empire avant `cooldown_until`.
- Grief IA : acte hostile plus récent que 72 h au moment de la décision.

## Verrous et Combat

- Une commande de relation verrouille **seulement** la ligne de paire, jamais un stream
  d'opérations, de Research ou de Colony.
- `app.combat.orchestrator` : streams triés → engagement → **paire** (créée si absente). Ordre
  jamais inversé, donc sans interblocage avec les commandes de relation ou l'IA.
- Pacte couvrant `battle_at` : issue `voided_by_pact`, aucune perte, aucun tir, attaquant
  renvoyé (carburant non remboursé), alerte close, rapports datés des deux côtés avec
  `opponent_empire_id` et `pact_id`, **sans** `own`/`opponent`/`rounds`.
- Bataille réellement résolue (issue autre que `target_unavailable`/`voided_by_pact`) : acte
  hostile de l'attaquant daté à `battle_at` et contacts orientés `combat` dans les deux sens.
- ATTACK n'est jamais refusée au lancement pour une raison de relation (non-fuite inchangée).

## Contacts par présence

`galaxy.refresh_monitoring` (GET Galaxie/System View, handlers, tour IA) : en v0.8 seulement, pour
chaque système MONITORED par une colonie propre, toute colonie étrangère existant à la date
d'observation (`founded_at` NULL ou ≤ date) crée ou date le contact (Empire, planète, date).
Aucune autre information n'est lue ni projetée.

## API Game

| Méthode | Route | Droits |
| --- | --- | --- |
| GET | `/game/{universe}/relations` | Session ; liste des Empires avec `relations.read`, `available` selon le ruleset |
| GET | `/game/{universe}/relations/{empire}` | `relations.read` (sinon 404 indiscernable) |
| POST | `/game/{universe}/relations/{empire}/{counterpart}/{propose\|withdraw\|accept\|refuse\|terminate}` | `relations.read` + `relations.negotiate`, CSRF, `idempotency_key` |

Codes : `relations_unavailable` (409, ruleset < v0.8), `relation_not_found` (404, Empire inconnu
**ou** inexistant, indiscernables), `proposal_open`, `proposal_missing`, `proposal_cooldown`,
`pact_active`, `pact_missing`, `notice_pending` (409), `invalid_request` (422),
`idempotency_conflict` (409). La projection ne contient que les contacts et paires de l'Empire ;
sans `relations.negotiate`, aucune action n'est proposée (le client refuse une projection
contraire).

## IA (policy `utility-goals-v3`)

Famille `diplomacy` (poids 5/100 pour les deux profils). Un emplacement répond à la plus ancienne
proposition reçue (candidat prioritaire) ; les autres visitent circulairement les propres contacts
pour une proposition spontanée selon la règle du profil. Le dispatcher n'autorise que `propose`,
`accept`, `refuse` : jamais retrait, rupture ni ATTACK. Capabilities internes `relations.read` /
`relations.negotiate` portées par le dispatcher seul, sans identité humaine.

## Interface

Section `#relations` (React) : civilisations connues (badge d'état), faits datés (contact,
présence, pacte, préavis, expiration, délai, derniers actes hostiles), alertes diplomatiques
(proposition reçue, rupture notifiée par l'autre camp), historique, actions ; confirmation
explicite avant rupture. Mêmes règles de commande que Flottes (une intention, même clé sur
résultat inconnu). Flottes affiche le rapport `voided_by_pact` sans composition.

## Validation

| Niveau | Contenu | État |
| --- | --- | --- |
| Pur (Fast CI) | `tests/test_relations_rules.py` (v0.8, poids, dates), contrats 17 droits Game/Portal | Exécuté |
| Frontend (Fast CI) | `Relations.test.tsx` (7), `Fleet.test.tsx` (`voided_by_pact`), lint, build | Exécuté |
| PostgreSQL | `tests/integration/test_relations.py` (contacts, négociation, dates logiques, concurrence, IA) | **À exécuter** (`RUN_DB_TESTS=1`, base `*_test`) |
| Compose | `scripts/smoke_relations_compose.py` (combat-worker et ai-worker réels, Portal arrêté) | **À exécuter** (Full CI ou poste local) |
