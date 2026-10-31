# Étape 9 — Flottes et missions asynchrones

**F00 réalisé et F01 publié le 31/10/2026 ; arrêt obligatoire avant F02 jusqu’à validation de Q09.**
Base master `e011fd3127c4888db551dd3792b347b1dc31b468`, étape 8 intégrée via PR #11, CI post-merge
41231820338 success (5/5). Branche unique `work/step-9-fleets`, [PR #12](https://github.com/ThomasPerez91/Echosphere/pull/12)
brouillon. Aucun merge autorisé ; étape 10 Colonisation non commencée. Proposition produit :
[Flottes — proposition Q09](../01-game-design/fleets.md). Tout ce qui suit est **proposé**, non validé.

| Ticket | Travail et preuve attendue |
| --- | --- |
| F00 | Réalisé : CI post-merge vérifiée terminée 5/5, master synchronisée ff-only, branche, statuts |
| F01 | Réalisé, en attente de validation : audit ci-dessous et proposition Q09 complète |
| F02 | Ruleset complet v0.4 (`fleets.json`, exploration `fleet-survey-v1`), validation stricte, v0.1–v0.3 intactes |
| F03 | Migration 0009 : tables Fleet, contraintes d’invariant, permissions 12, downgrade sûr ; inventaire de tables |
| F04 | Production (file dédiée, réservation, annulation Q39 explicite), garnisons, division/fusion stationnées |
| F05 | Missions DEPLOY/SURVEY/RETURN, chemins snapshotés, `FLEET_ARRIVAL`, rapports, reprise worker |
| F06 | Cargo CHARGER/DÉCHARGER, rappel `FLEET_RETURN`, idempotence ; transport selon arbitrage A9 |
| F07 | API Game + permissions propagées (DTO, schéma partagé, Portal, CHECK, tests), CSRF/idempotence |
| F08 | UI Flottes réelle ; lien depuis Galaxy/System View vers un envoi prérempli, sans pollution |
| F09 | Concurrence/deadlocks, non-fuite, responsive 320/390/768/1440, accessibilité |
| F10 | Recette réelle Compose jetable (*_test) : production, SURVEY page fermée, worker, Portal coupé, expiration |
| F11 | Revue indépendante, suites complètes, CI finale 5/5, passation, PR Ready sans merge |

## Audit du code existant (F01)

- **Scheduler** : `EventStream`/`ScheduledEvent` génériques, handlers enregistrés dans `TimeEngine`,
  règle « handler sans commit ni second stream ». Ajouter des types d’événement ne demande aucun
  nouveau scheduler ; un type inconnu suit retry/blocked.
- **Stream Exploration** : `EmpireExploration` (un stream par Empire, créé par
  `galaxy.initialize_empire`) est déjà verrouillé par les commandes et lectures Galaxy, en tête de
  l’ordre principal → Exploration → Research → Colony. Les lectures Galaxy rattrapent ce stream ;
  le GET détail System View ne le rattrape pas (étape 8).
- **Missions** : `ExplorationMission` + `MissionLeg` (FK vers `RouteKnowledge` de l’Empire),
  snapshot JSON, rapport immuable `observed_at = due_at`, `known_path` (BFS sur routes connues,
  intermédiaires cartographiés) et `map_system` (fusion monotone) sont réutilisables tels quels.
- **Économie** : débits de commande après `catch_up_owned` sous verrou ; Q39 implémentée par
  `recoverable_refunds` (pur, réutilisable pour l’annulation de production). Capacité de stockage
  finie par ressource. `speeds.fleet` existe déjà (ratio 1/1) dans v0.1–v0.3 sans système associé.
- **Infrastructures** : cinq types économiques, aucun chantier ni infrastructure orbitale ;
  2 slots orbitaux réservés inutilisés (Q04). Aucune technologie de propulsion en Research v0.2/v0.3.
- **Colonies** : aucun parcours produit ne crée une deuxième colonie avant l’étape 10 ; les
  fixtures de recette créent déjà Empire/Colony en base faute de flux produit (précédent G09).
- **Permissions** : exactement 9 droits aujourd’hui, plafond 9 dans DTO Game (`max_length`),
  schéma partagé (`maxItems`), Portal et CHECK SQL du binding : tout ajout doit relever les quatre.
- **Frontend** : entrée « Flottes » déjà présente dans le shell (placeholder « À venir »), patrons
  réutilisables : hook à générations/abort (`useGalaxy`), validateurs stricts, `Countdown`,
  dialogue de confirmation, liste textuelle équivalente. Aucune maquette Fleet dans `visual-reference`.

## Proposition technique (dépend de Q09)

### EventStream : un stream « opérations d’Empire » (A13)

Toutes les flottes et la production d’un Empire utilisent **le stream Exploration existant**.
Raisons : la mission SURVEY écrit la connaissance, déjà sous l’autorité de ce stream ; aucun
handler ne prend donc de second stream ; pas de nouveau niveau dans l’ordre des verrous ; aucune
commande multi-flottes (fusion) à trier entre streams. Coût : les flottes d’un même Empire sont
sérialisées entre elles, sans effet visible à l’échelle MVP (quelques flottes par Empire).
Écarté : un stream par Fleet (SURVEY et fusion deviendraient multi-streams ou exigeraient des
écritures croisées de connaissance).

Événements, tous sur ce stream : `SHIP_ORDER_COMPLETE` (unités ajoutées à la garnison, activation
de l’ordre suivant déjà payé), `FLEET_ARRIVAL` (DEPLOY/RETURN/SURVEY ; SURVEY inclut l’étude et
la cartographie), `FLEET_RETURN` (fin d’un rappel). Aucun handler n’écrit dans une colonie.

### Ordre des verrous

`principal Game → stream opérations d’Empire → Research → Colonies (triées par UUID)`.
Commandes : production/annulation (opérations → Research → colonie source) ; mission (opérations →
Research → colonie payeuse) ; CHARGER/DÉCHARGER (opérations → Research → colonie du système) ;
rappel, division, fusion (opérations seul). Chaque commande rattrape complètement les streams
pris avant toute dépense. Les handlers Colony/Research ne prennent jamais le stream opérations,
d’où l’absence de cycle. Crédit à l’arrivée exclu : il exigerait le stream Colony dans un handler
Fleet ; le déchargement est donc une commande (A8).

### Modèle persistant proposé (migration 0009, après validation)

| Table | Rôle et contraintes clés |
| --- | --- |
| `ship_orders` | File par colonie : classe, quantité ≥ 1, statut queued/active/completed/cancelled, position, snapshot (coût, durée, règles), dates, clé d’idempotence par membership ; index unique partiel « un actif par colonie » ; FK composites colonie/Empire/Universe |
| `fleets` | Empire, colonie d’attache, `kind` GARRISON/TASK, `status` STATIONED/MOVING, `system_id` (FK vers la Knowledge de l’Empire : jamais stationnée hors de ses connaissances), `active_mission_id` unique ; CHECK stationnée ⇔ système présent ⇔ pas de mission ; garnison toujours stationnée ; unique garnison par colonie |
| `fleet_stacks` | (flotte, classe) → nombre > 0 ; une unité n’existe que dans un stack d’une flotte |
| `fleet_cargo` | (flotte, ressource) → montant > 0 en micro-unités ; capacité vérifiée par le service |
| `fleet_missions` | Type, statut active/returning/completed, origine/destination, `started_at`, `arrival_at`, `recalled_at`, `return_at`, colonie payeuse, snapshot complet, clé ; une seule mission ouverte par flotte (index partiel + `fleets.active_mission_id`) |
| `fleet_mission_legs` | Ordinal → route, FK vers `RouteKnowledge` de l’Empire (patron `MissionLeg`) |
| `fleet_reports` | Rapport immuable par mission (arrivée, SURVEY), `observed_at = arrival/due`, `processed_at` |

Invariant « une unité dans une seule mission » garanti en base : stack → une seule flotte (FK),
flotte → au plus une mission ouverte (unique), flotte MOVING ⇔ mission active (CHECK) ; les
mutations de stacks/cargo exigent STATIONED sous le verrou du stream (service + tests de
concurrence). Pas d’identité individuelle des vaisseaux : rien ne l’exige avant Q10.

### Permissions (A14)

`fleet.read` (flottes, missions, rapports ; colonie payeuse visible seulement avec `colony.read`),
`fleet.build` (commander/annuler la production, avec `colony.read`), `fleet.command` (missions,
rappel, division/fusion ; CHARGER/DÉCHARGER exigent aussi `colony.read` ; SURVEY exige aussi
`galaxy.read`). Total 12 : relever ensemble DTO Game, schéma partagé, Portal, CHECK SQL, avec un
test aller-retour à 12 droits et le refus d’un treizième ; aucune attribution aux bindings existants.

### API envisagée (F07, après validation)

`GET /game/{u}/fleets` (Empires lisibles) ; `GET /game/{u}/fleets/{empire}` (flottes, stacks, cargo,
missions, files, rapports récents) ; `GET …/quote` (devis serveur d’une mission ou d’une
production) ; `POST …/orders`, `POST …/orders/{id}/cancel` ; `POST …/missions` ;
`POST …/missions/{id}/recall` ; `POST …/{fleet}/cargo`, `…/split`, `…/merge`. Toutes : GameSession,
binding/permission, scope Universe/Empire, CSRF/Origin, clé d’idempotence par membership, aucun
appel Portal. Les lectures rattrapent le stream opérations comme Galaxy aujourd’hui.

### UI envisagée (F08)

Écran « Flottes » réel, sans nouvelle entrée principale : production par colonie, flottes
stationnées (composition, lieu, cargo, actions), flottes en mission (origine → destination,
sauts, départ/arrivée, compte à rebours informatif), rappel confirmé, rapports récents. Dialogue
d’envoi avec devis serveur (durée, Flux, arrivée). Galaxy/System View : simple lien « Envoyer une
flotte ici » vers ce dialogue prérempli. Mobile-first, liste/cartes, cibles 44 px, pas de survol seul.

### Ruleset v0.4 (A15)

Copie complète de v0.3 + `fleets.json` (classes, files, remboursements, `survey_seconds`, coût
d’analyse) + exploration `fleet-survey-v1`. v0.1–v0.3 immuables, univers existants non migrés ;
la recette existante v0.3 reste valide. Les durées de recette accélérées restent test-only.

## Arbitrages nécessaires

Voir le tableau A1–A15 de la [proposition Q09](../01-game-design/fleets.md). Point le plus
structurant : A9 (cargo/transport livrés à l’étape 9 sans seconde colonie jouable, ou reportés à
l’étape 10). Après validation explicite, F02–F11 se déroulent sans validation par ticket, sauf
nouvelle décision produit réelle.
