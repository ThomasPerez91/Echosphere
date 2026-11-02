# Étape 13B — Présence frontalière & Premier contact

**État courant : B00–B07 implémentés sur `work/step-13b-first-contact` (PR #17, Draft), code et
tests écrits, Fast CI seule ; validations PostgreSQL/Compose/Chromium à faire sur poste local.
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
| B08 | IA : aucune capacité ajoutée ; points d'intégration documentés | Arbitrage requis (voir plus bas) |
| B09 | Recette runtime, revue indépendante, Ready | À faire sur poste local |

« Code + tests » : tests purs exécutés ici et en Fast CI ; scénarios PostgreSQL écrits
(`tests/integration/test_frontier.py`) **non exécutés** (pas de PostgreSQL/Docker dans
l'environnement cloud). Aucun lot n'est fonctionnellement validé.

## Décisions D1–D7 — validées le 02/11/2026

Provenance : instruction utilisateur explicite (PR #17). Transcription canonique :
[premier contact](../01-game-design/first-contact.md#décisions-d1d7--02112026).

## Implémentation : verrous, fences et dates logiques

- **Planification** des réactions (B05/B06) au moment où les deux faits sont connus *avant*
  l'instant d'entrée : décision de mouvement (lancement, rappel, retour après bataille) ou
  commande de protocole. Une ligne `frontier_encounters` par (passage, flotte surveillante, type).
- **Engagement** : streams d'opérations des deux Empires figés à `entered_at − 1 µs` (état
  strictement antérieur à l'entrée ; une arrivée au même instant ne peut pas installer la flotte
  avant la rencontre). **Repli** : stream du surveillant et Colony d'attache figés à `entered_at`
  (inclus), pour débiter le carburant normal à cet instant exact quel que soit le retard du worker.
- **Résolution** hors handler par `FrontierOrchestrator`, exécuté dans le processus
  `combat-worker` : streams triés → ligne de rencontre → paire relationnelle → contacts ; rang
  `(instant, type, mission, passage, flotte)`, engagements avant replis au même instant ;
  rattrapage exact jusqu'aux fences ; une transaction ; retry puis `blocked` opérateur
  (`python -m app.combat.worker --blocked`, `--retry-frontier <id>`).
- **Fin anticipée** : changement de protocole, départ, fusion ou destruction annulent les réactions
  futures de la période ; un rappel ou une destruction annulent celles des passages non atteints.
- **Décision tardive d'un orchestrateur** (retour après bataille, trajet d'un repli) : si le stream
  d'un tiers a déjà dépassé une entrée, la création lève `TimelineError` (retry puis `blocked`),
  jamais une réaction silencieusement omise. Limite opérationnelle : retard du worker supérieur à
  la durée d'un saut (≥ 10 min dans le catalogue actuel).

## Écarts et points ouverts à arbitrer

| Sujet | État |
| --- | --- |
| **D2 — stream d'évaluation** | Implémenté sur le stream de l'Empire **en mouvement** (le passage lui appartient ; la détection est mutuelle à niveaux égaux, chaque camp est détecteur ; le handler ne lit que des périodes datées et n'écrit que des faits). Résultat identique à une évaluation sur le stream du surveillant, sans écriture dans le stream d'un autre Empire. **À confirmer** |
| Fenêtre de course D2 | Une commande de protocole lancée juste avant `entered_at` mais validée après le traitement du passage peut ne pas être vue (fenêtre = latence de la commande). À fermer si nécessaire par une fence courte à l'activation |
| Déclencheur du repli (FC6) | « Action hostile » interprétée comme : une mission ATTACK entre dans son système cible contre l'Empire du surveillant amical. Une ATTACK locale (0 saut) n'a pas de passage et ne déclenche pas de repli. **À confirmer** |
| Événements au même instant | Une rencontre voit l'état strictement avant l'entrée : une production terminée exactement à `entered_at` n'y participe pas (Combat ATTACK l'inclut) |
| B08 — IA | Les IA subissent les mêmes détections/rencontres ; leur dispatcher n'a **aucune** capacité de protocole. Choisir une politique (FC13 non validée) est un arbitrage produit |
