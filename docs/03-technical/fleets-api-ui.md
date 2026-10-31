# Flottes — persistance, chronologie, API et UI

**Contrat technique étape 9, Q09 close le 31/10/2026 avec amendements ; réalisé sur PR #12.**
[Règles produit](../01-game-design/fleets.md), [plan F00–F11](../05-project/step-9-plan.md).
Ruleset `v0.4` uniquement ; univers v0.1–v0.3 sans flottes ni migration.

## Données et migration 0009

Migration Game `0009_fleets` après 0008, DDL figé généré depuis les modèles (aucune dérive
`alembic check`) : `ship_orders`, `fleets`, `fleet_stacks`, `fleet_cargo`, `fleet_missions`,
`fleet_mission_legs`, `fleet_reports` et le registre d’idempotence `fleet_operations`. FK
composites Universe/Empire, ancrage sur `empire_exploration`, colonie d’attache et payeuse
`colonies(id, empire_id, universe_id)`.

Invariant d’engagement garanti en base : une unité n’existe que comme compte d’un stack d’une
flotte ; `active_mission_id` unique et FK `(active_mission_id, id) → fleet_missions(id, fleet_id)` ;
index unique partiel « une mission ouverte par flotte » ; CHECK STATIONED ⇔ système présent,
MOVING ⇔ mission ouverte, garnison toujours stationnée et unique par colonie. Stationnement
FK vers `system_knowledge` de l’Empire, trajets FK vers `route_knowledge` : jamais hors des
connaissances. Rappel contraint en base (pendant le trajet, jamais RETURN, retour symétrique).
Flotte fusionnée = statut MERGED conservant l’historique. Downgrade refusé avec données ou droits Fleet.

## Chronologie des opérations d’Empire

Le stream `EmpireExploration` existant devient conceptuellement la chronologie des opérations
d’Empire, sans renommage : Exploration v0.3, production et flottes. Événements
`SHIP_ORDER_COMPLETE` (lot entier dans la garnison, activation de l’ordre suivant déjà payé),
`FLEET_ARRIVAL` (DEPLOY/RETURN ; SURVEY cartographie à `due_at` via `map_system`) et
`FLEET_RETURN` (fin de rappel). Handlers mono-stream : jamais d’écriture Colony, de Portal, de
session ou de navigateur ; vérification stream/clé/échéance/snapshot/chemin, rapport immuable
`observed_at = due_at`, rejeu sans double effet.

**Aucune projection ne rattrape cette chronologie** (Flottes, carte et missions Galaxy, System
View) : un GET ne termine ni production, ni arrivée, ni expédition ; il verrouille seulement le
stream pour sérialiser le rafraîchissement de surveillance. Seuls le worker et les commandes
(rattrapage complet sous verrou avant décision) la font avancer. Changement appliqué aussi aux
lectures Galaxy existantes, avec tests de régression.

Ordre des verrous : principal Game → opérations d’Empire → Research → colonies (triées). Les
handlers Colony/Research ne prennent jamais ce stream. Le déchargement est une commande : un
crédit à l’arrivée exigerait un second stream dans un handler.

## Règles appliquées

Production : file dédiée par colonie (3 ordres, 1 actif), quantité 1–20, coût total débité à
l’acceptation, durée `N × durée unitaire` sans vitesse ni bonus ; annulation 80 % actif / 100 %
en attente, crédit plafonné Q39 (`recoverable_refunds`), événement acquitté `cancelled`.
Missions : chemin serveur `known_path` (plus court, départage stable, intermédiaires
cartographiés), destination MAPPED+ (DEPLOY/RETURN) ou DETECTED (SURVEY, sondes seules) ;
`travel = sauts × temps/saut le plus lent ÷ speeds.fleet` (plafond entier), SURVEY + 15 min
d’analyse ; Flux `sauts × Σ(n × flux/saut)` + 20 Données pour SURVEY, débités sur la colonie
d’attache. Rappel avant `travel_arrival_at`, `return_at = recalled_at + (recalled_at − started_at)`.
Cargo commun 500/cargo léger ; CHARGER débite la colonie du système, DÉCHARGER crédite jusqu’au
stockage libre et laisse le surplus à bord ; division/fusion stationnées, capacités vérifiées.

## API

Préfixe `/game/{universe}/fleets` : `GET` (Empires lisibles), `GET /{empire}` (catalogue, files
avec preview d’annulation, flottes, missions récentes et rapports, systèmes connus),
`POST /{empire}/orders`, `/orders/{id}/cancel`, `/missions/preview` (devis sans mutation),
`/missions`, `/missions/{id}/recall`, `/{fleet}/split`, `/merge`, `/load`, `/unload`.
Toute commande : GameSession, binding, CSRF/Origin, clé d’intention par membership, activité
explicite, aucun appel Portal. Droits : lecture `fleet.read` ; production + `fleet.build` +
`colony.read` ; commandes + `fleet.command` (SURVEY + `galaxy.read`, cargo + `colony.read`).
Sans `colony.read` : aucune colonie, attache, payeuse ni preview de cargo transmise. Flottes
étrangères/inconnues/autre univers : même 404 ; systèmes DETECTED listés seulement avec `galaxy.read`.

## UI

Écran « Flottes » réel : production et file, garnisons et flottes stationnées, missions
(SURVEY en deux temps), rapports, dialogues avec devis serveur, previews d’annulation et de
déchargement, rappel proposé seulement pendant le trajet. Validateurs stricts (fuite Colony sans
droit ou nom d’un système DETECTED refusés). Raccourci « Envoyer une flotte ici » depuis Galaxy
et System View vers le même flux ; la Galaxie indique le mode d’exploration v0.4. Mobile 320–1440,
cibles 44 px, clavier et focus, aucune donnée inventée.

## Recette

`scripts/smoke_fleet_compose.py` (projet, bases et volumes `*_test` jetables, durées de test
seulement) : production UI page fermée puis worker, SURVEY UI, GET après échéance sans effet avec
worker arrêté, cartographie prouvée en base avant relecture, rappel DEPLOY idempotent, rappel
refusé pendant l’analyse, CHARGER → DEPLOY → DÉCHARGER vers une seconde colonie de test au
stockage partiel, Portal coupé, expiration de session. Résultats et CI dans [progress](../../progress.md).
