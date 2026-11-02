# Étape 13B — Présence frontalière & Premier contact

**État courant : B00 réalisé, B01–B02 implémentés sur `work/step-13b-first-contact` (code et tests
écrits, Fast CI seule). Démarrage anticipé autorisé le 02/11/2026 ; aucune fusion, aucune
validation de l'étape 13 impliquée.** Règles canoniques : [premier contact](../01-game-design/first-contact.md),
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

| Lot | Contenu | État |
| --- | --- | --- |
| B00 | Audit ci-dessus, plan, arbitrages | Fait |
| B01 | Ruleset v0.9 (= v0.8 + `frontier.json`), `fleet_mission_passages` (migration 0014), passages aller au lancement, retour miroir au rappel et après bataille, entrées non atteintes marquées `cancelled_at` ; v0.4–v0.8 n'en écrivent aucun | Code + tests (purs exécutés, PostgreSQL à exécuter) |
| B02 | `fleets.protocol` (CHECK : flotte TASK stationnée seulement), commande `POST …/{fleet}/protocol` (droit `fleet.command`, idempotente), effacement au départ, à la fusion, à la destruction ; projection `protocol` et `frontier.protocols` | Code + tests (idem) |
| B03 | Détection à l'entrée (passages × flottes stationnées en SURVEILLANCE/FRIENDLY_CONTACT), alertes « signature étrangère » | Après arbitrage D1–D3 |
| B04 | FRIENDLY_CONTACT : contact réciproque (Empire, système, date) | Après D1–D3 |
| B05 | AMBUSH, INTERCEPTION (engagements Combat) | Après D4–D6 |
| B06 | Repli amical | Après D7 |
| B07 | UI : choix du protocole, flottes stationnées, alertes de frontière | Après B03 |
| B08 | IA | Après politique validée (FC13) |
| B09 | Recette, revue, PR | — |

`frontier.json` v0.9 n'active que `SURVEILLANCE` et `FRIENDLY_CONTACT` : AMBUSH/INTERCEPTION sont
refusés (`protocol_unavailable`) tant que leur runtime n'existe pas. Aucun paramètre numérique.

## Arbitrages demandés (propositions, non validées)

| ID | Question | Proposition motivée |
| --- | --- | --- |
| D1 | Niveau de détection avant toute technologie (Q58 ouverte) | Niveau 0 pour tous : égalité → détection mutuelle, conforme à FC7, sans inventer de technologie |
| D2 | Quand détecter | À chaque passage enregistré (entrée réelle, non annulée) dans un système où stationne une flotte en protocole, à l'instant `entered_at`, évalué par un événement planifié sur le stream du **détecteur** (pas de verrou étranger) |
| D3 | Ce qu'une détection révèle | Signature datée (système, instant, sens aller/retour) ; identité seulement si l'Empire est déjà un contact du détecteur ; jamais composition, cargo, origine ni destination |
| D4 | « Ennemi connu » pour AMBUSH | Contact existant, aucun pacte couvrant l'instant, et acte hostile de cet Empire contre le détecteur depuis 72 h (même fenêtre que le grief IA Q18) |
| D5 | Engagement automatique | Un engagement Combat existant, `battle_at` = instant de passage (pas de délai de 24 h : la flotte adverse est présente) — **rouvre Q02** (24 h minimum avant toute bataille) : à trancher explicitement |
| D6 | Effet sur la mission interceptée | Proposition : la mission continue si l'attaquant intercepté survit ; sinon flotte détruite. À confirmer |
| D7 | Repli amical : destination et échec | Système précédent de la route du détecteur… or une flotte stationnée n'a pas de route : proposition = retour vers la colonie d'attache par chemin connu, carburant payé comme un RETURN ; échec (fonds insuffisants) = reste stationnée, rapport |

Le point D5 est bloquant pour B05 : Q02 impose 24 h minimum avant toute bataille, incompatible avec
une interception instantanée au passage.
