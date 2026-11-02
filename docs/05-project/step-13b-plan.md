# Étape 13B — Présence frontalière & Premier contact

**État courant : B00–B09 et correctifs C01–C05 implémentés sur `work/step-13b-first-contact`
(PR #17, Draft) ; PostgreSQL, Alembic 0014, Chromium et recette Compose exécutés et réussis sur
poste local (WSL2 + Docker) le 02/11/2026 ; revue indépendante et Full CI à venir.
Démarrage anticipé autorisé le 02/11/2026 ; aucune fusion, aucune validation de l'étape 13
impliquée.** [Contrat technique](../03-technical/frontier-api-ui.md). Règles canoniques : [premier contact](../01-game-design/first-contact.md),
Q57/Q58 au [registre](open-questions.md).

## Dépendance de branche (exception au workflow)

Branche créée depuis `a434e06`, tête publiée de `work/step-13-ai-relations` (PR #16, Draft, non
fusionnée), dans un worktree séparé. La PR 13B cible **`work/step-13-ai-relations`**, pas master,
tant que #16 n'est pas fusionnée ; sa base sera réévaluée ensuite. Aucun fichier de 13B n'est
écrit sur la branche de #16. Migration 0014 au-dessus de 0013 (non intégrée) : si 0013 change
encore, 0014 se rebase sans transformation de données.

## B00 — audit technique ciblé (code `a434e06`)

- **Durées :** `FleetRules.mission_quote` facture des sauts entiers de la classe la plus lente
  (`travel = ceil(hops × hop × vitesse)`), sans position. Tous les sauts d'une mission ont donc la
  même durée : l'entrée dans le k-ième système vaut `started_at + ceil(travel × k / n)`, exacte en
  entiers, dernière entrée = `travel_arrival_at`. Aucune règle nouvelle n'est nécessaire.
- **Chemins :** `fleet_mission_legs` (routes connues, ordinal) existe ; `verified_path` reconstruit
  la chaîne origine → destination. Aucun événement par saut : seuls `FLEET_ARRIVAL`/`FLEET_RETURN`
  (et la résolution Combat pour ATTACK) existent.
- **Retours :** rappel symétrique `return_at = rappel + (rappel − départ)` ; ATTACK rappelée après
  arrivée ou après bataille : `+ travel`. Le chemin du retour est le miroir de l'aller : ré-entrée
  de chaque système déjà franchi à `départ_retour + (progression − entrée)`.
- **Invariants préservés :** décisions sous le verrou du stream d'opérations de l'Empire, handlers
  mono-stream, snapshots v0.4–v0.8 inchangés (`verify_mission_snapshot` intact), ordre global
  paire → contact (étape 13), pas d'ordre de workers comme règle.
- **Statut de flotte :** STATIONED/MOVING/MERGED/SETTLED/DESTROYED ; trois transitions quittent
  STATIONED pour une flotte TASK (départ, fusion, destruction défensive).

## Plan et état

| Lot | Contenu | État (02/11/2026, fin d'après-midi) |
| --- | --- | --- |
| B00 | Audit ci-dessus, plan, arbitrages | Fait |
| B01 | Ruleset v0.9, `fleet_mission_passages` (migration 0014), passages aller/retour miroir, entrées non atteintes annulées | Code + tests |
| B02 | `fleets.protocol`, périodes de protocole datées, commande `POST …/{fleet}/protocol` (droit `fleet.command`), fin au départ/fusion/destruction | Code + tests |
| B03 | Détection déterministe à `entered_at` (niveau 0 pour tous, mutuelle), faits uniques, signatures anonymes | Code + tests |
| B04 | FRIENDLY_CONTACT : présentation volontaire, contacts réciproques source `frontier` | Code + tests |
| B05 | AMBUSH, INTERCEPTION : `frontier_encounters`, résolution hors handler par le worker Combat, résolveur Combat réutilisé | Code + tests |
| B06 | Repli amical (D7), carburant normal débité à l'instant logique | Code + tests |
| B07 | UI Flottes : protocole, quatre modes, détections, rapports d'interception et de repli | Code + tests Vitest |
| B08 | IA : policy v4 (v0.9), protocoles dans la famille militaire, dispatcher borné par profil | Code + tests ; PostgreSQL 10/10 exécuté localement |
| B09 | Recette Compose `smoke_frontier_compose.py` + `frontier_game_fixture.py`, Chromium `e2e/frontier.spec.ts`, test migration 0014 ; puis exécution locale, revue indépendante, Ready | **Exécutés localement et réussis** (02/11/2026, défauts de tests/fixture corrigés, aucun bug produit) ; recette dans la Full CI ; revue indépendante, Ready à venir |

« Code + tests » : tests purs en Fast CI ; scénarios PostgreSQL (`test_frontier.py` 36,
`test_frontier_ai.py` 10) exécutés localement le 02/11/2026. Validation fonctionnelle finale :
revue indépendante (Codex) puis décision de l'utilisateur.

## Décisions D1–D7 — validées le 02/11/2026

Provenance : instruction utilisateur explicite (PR #17). Transcription canonique :
[premier contact](../01-game-design/first-contact.md#décisions-d1d7--02112026).

## Implémentation : verrous, fences et dates logiques (révisée C01–C05)

Détail : [contrat technique](../03-technical/frontier-api-ui.md#chronologie-et-verrous-c01c02-02112026).

- **Entrées** : chaque passage fige le stream de l'Empire en mouvement à `entered_at − 1 µs` (fence
  sur son propre stream). `FrontierOrchestrator` résout l'entrée hors handler : streams du mobile et
  de tous les Empires pouvant tenir un protocole dans le système, triés et verrouillés, réglés à
  `entered_at − 1 µs` ; détections puis engagements ; une transaction ; retry puis `blocked`.
- **Engagements** décidés à la résolution de l'entrée (plus de planification ni de fence chez le
  surveillant) ; flotte surveillante figée par `guard_fleet_change` et bloqueur Combat.
- **Replis** seuls planifiés (ATTACK distante à l'arrivée, ATTACK locale au lancement), fences sur le
  stream d'opérations et la Colony d'attache du surveillant, sérialisés avec la commande de protocole
  par le verrou du stream du défenseur.
- **Commandes datées derrière une entrée résolue** : refusées (`fleet_busy`), jamais réécrites.
- **Ordre global** : entrées (état avant `t`) → replis à `t` → bataille planétaire à `t`.

## Correctifs C01–C05 (02/11/2026)

| Point | Défaut démontré (79d25c8) | Correction |
| --- | --- | --- |
| C01 | Détection par handler sur le stream du mobile : déterministe seulement si aucune période n'était en cours de validation ; une fin de période rétroactive (destruction en bataille) pouvait suivre une détection déjà écrite | Plus de handler : résolution sous verrous de tous les surveillants possibles, chaque stream réglé à `t − 1 µs` ; bataille avant une entrée postérieure du même défenseur garantie par ses fences |
| C02 | (a) commande de protocole datée avant `t`, validée après le handler : détection perdue ; (b) lancement et commande concurrents : rencontre jamais planifiée ; (c) vérification du curseur avant pose de fence non protégée | (a) attente du verrou ou refus `check_not_behind` ; (b) engagements non planifiés, replis sérialisés ; (c) `FOR KEY SHARE` puis lecture du curseur |
| C03 | ATTACK de 0 saut sans repli | Ligne `local` et repli à l'instant du lancement, Q02 intact |
| C04 | Couverture `[début, fin)` côté détection, `]début, fin[` côté engagement ; bataille à `t` pouvant précéder une entrée à `t` | Couverture unique `]début, fin]` ; bloqueur Combat ; ordre documenté |
| C05 | Décision tardive (retour après bataille, repli) posant des fences chez un tiers : `TimelineError` puis blocage dès un retard d'un saut | Plus aucune fence tierce tardive ; diagnostics `--lag`, `--retry-passage` ; limite restante : mobile figé jusqu'à résolution |

## Écarts et points ouverts

| Sujet | État |
| --- | --- |
| D2 — stream d'évaluation | Conservé côté mobile comme point d'arrêt, avec verrouillage des surveillants (C01, démonstration ci-dessus) ; à valider en revue |
| Règles de départage C04 | **Validées par l'utilisateur le 02/11/2026** ([premier contact](../01-game-design/first-contact.md#arbitrages-c01c05--02112026)) ; tests PostgreSQL exécutés |
| Gel du mobile (C05) | Toute flotte d'un Empire en mouvement attend la résolution de chaque entrée (≈ intervalle du worker Combat) ; évolution par flotte hors 13B |
| Interblocage de deux lancements ATTACK croisés | Préexistant v0.7, détecté par PostgreSQL ; commande rejouable |
| B08 — lecture des termes | « Pertinente », « intérêt », « risque acceptable » **validés par l'utilisateur le 02/11/2026** ([B08](../01-game-design/first-contact.md#b08--politique-ia-validée-le-02112026)) |
