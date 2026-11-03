# UX-API-01 — Trajet réel d’une mission exposé par l’API Game

**Statut : principe validé par l’utilisateur le 03/11/2026 (D-UX-2) ; développement autorisé dans
une PR technique dédiée. Implémenté par Claude sur `work/ux-api-01-mission-path` (PR Draft vers
`work/step-13b-first-contact`). Tests purs exécutés ; tests PostgreSQL écrits, non exécutés (session sans
PostgreSQL), à exécuter en recette locale.** Contexte : [Flottes API](fleets-api-ui.md) ; refonte UX/UI et carte de commandement UX04 sur la
[PR #19](https://github.com/ThomasPerez91/Echosphere/pull/19) (`docs/02-ux-ui/redesign/`).

## Besoin

La carte de commandement doit montrer par où passe une flotte. Le serveur calcule déjà le chemin
(`galaxy.known_path` sur les routes connues de l’Empire), le persiste (`fleet_mission_legs` et
`snapshot.path`, identifiants de routes) et le revérifie (`verified_path`), mais ne renvoyait que
`hops`. Le client ne doit pas recalculer ce chemin : c’est une règle de gameplay côté serveur.

## Contrat

Champ additif `path` : liste ordonnée d’identifiants de systèmes (UUID en texte) — départ, chaque
système traversé, destination. `len(path) == hops + 1` ; `[départ]` seul pour une mission de 0 saut
(COLONIZE ou ATTACK dans le système courant).

| Endpoint | Ajout |
| --- | --- |
| `POST /game/{universe}/fleets/{empire}/missions/preview` | `path` du devis |
| `GET /game/{universe}/fleets/{empire}` → `missions[]` | `path` de la mission telle qu’elle a été lancée |
| `POST …/missions`, `…/recall` et autres commandes | Inchangés ; la projection `fleets` renvoyée contient `missions[].path` |

Le champ est **absent** (jamais `null`, jamais partiel) quand le serveur ne peut pas l’établir
exactement : routes qui ne s’enchaînent pas, legs différents du snapshot accepté, système hors de
la Knowledge de l’Empire. Un client qui l’ignore fonctionne comme avant.

## Règles

| Sujet | Règle implémentée |
| --- | --- |
| Source du devis | Les routes mêmes sur lesquelles le devis est calculé (`plan_mission`) ; la route affichée est celle du coût et de la durée |
| Source d’une mission | Ses `fleet_mission_legs` ordonnés, exigés égaux à `snapshot.path` ; aucun recalcul à la lecture (la Knowledge a pu changer depuis le départ) |
| Extrémités des routes | `route_knowledge` de l’Empire (pas la table monde) ; une route inconnue retire le champ |
| Fog of War | Chaque système doit être dans la `system_knowledge` de l’Empire (tout état) ; sinon le champ entier est retiré, jamais tronqué. Aucun nom, aucune planète, aucune identité ajoutés : le client joint `path` à ses propres projections, un signal détecté reste anonyme |
| Signaux et `galaxy.read` | Les systèmes intermédiaires sont MAPPED+ (`known_path` ne traverse pas un DETECTED) ; seul un SURVEY se termine sur un signal, dont l’identifiant est déjà exposé par `destination` de la mission, avec ou sans `galaxy.read` ; le devis SURVEY exige déjà `galaxy.read` |
| Droits et isolation | Ceux de l’endpoint, sans droit nouveau ; requêtes bornées à l’univers et à l’Empire de la session ; les missions d’autres Empires ne sont jamais projetées |
| Lecture | Aucune écriture, aucun rattrapage de chronologie, aucun événement |
| Coût de lecture | Deux requêtes indexées par mission projetée (legs, routes connues) et une lecture de la Knowledge par projection ; aucune pour le gameplay |
| Gameplay | Aucun changement de durée, coût, règle de déplacement ou résultat ; pas de migration |

## Retours, rappels et cas particuliers

`path` décrit toujours l’**aller lancé**. Le moteur ne persiste pas de chemin de retour distinct :

| Cas | Comportement du moteur (vérifié dans le code) | `path` exposé |
| --- | --- | --- |
| DEPLOY, SURVEY, RETURN | Legs `known_path` ; SURVEY vers un système DETECTED | Aller ; la destination d’un SURVEY reste un identifiant anonyme |
| COLONIZE, ATTACK distants | Legs `known_path` vers un système MAPPED+ | Aller |
| COLONIZE, ATTACK à 0 saut | Aucun leg, origine = destination | `[départ]` |
| Rappel (DEPLOY, SURVEY, COLONIZE) | `return_at = recalled_at + (recalled_at − started_at)`, arrivée sur `snapshot.origin_id` | Aller inchangé, statut `returning` |
| ATTACK rappelée ou après bataille | Retour symétrique ou trajet complet vers l’origine | Aller inchangé |
| Retour 13B (v0.9) | `record_way_back` rejoue en miroir les systèmes atteints (`fleet_passages`, direction `return`) | Aller ; le retour = systèmes atteints en sens inverse |
| Retraite automatique 13B | Mission DEPLOY/RETURN ordinaire lancée par `fleet_service.launch` | Son propre `path` |
| Flotte interceptée 13B | Mission terminée à l’entrée, rapport `INTERCEPTED` | Aller lancé ; aucun système adverse ajouté |
| Missions terminées | Legs conservés | Aller lancé |

Le client peut donc dessiner un retour comme l’aller parcouru en sens inverse depuis le point
atteint, en le présentant comme estimé ; avant v0.9, le moteur ne modélise que les dates du retour.

## Code et tests

| Fichier | Rôle |
| --- | --- |
| `backend/app/fleet/path.py` | Fonctions pures `systems_along` (enchaînement des routes) et `public_path` (sauts, destination, Fog) |
| `backend/app/fleet/service.py` | `known_systems`, `route_endpoints`, `quote_path`, `mission_path` ; `preview` ajoute `path` |
| `backend/app/fleet/api.py` | `mission_view` ajoute `path` (ensemble des systèmes connus lu une fois par projection) |
| `backend/tests/test_fleet_path.py` | Tests purs : direct, plusieurs sauts, 0 saut, ordre, routes incohérentes, sauts/destination, Fog |
| `backend/tests/integration/test_mission_path.py` | PostgreSQL : devis = mission = legs, lecture sans mutation ni recalcul, snapshot divergent, rappel et retour, ATTACK après bataille, 0 saut, SURVEY v0.4, interception, retraite, autres Empires/univers, lecteur `fleet.read` |
| `backend/tests/integration/test_combat.py` | `path` ajouté à la comparaison « même devis quelle que soit l’occupation » |

## Intégration frontend (PR #19, lot séparé, non commencé)

Examen du code de `work/ux-redesign` à `d7986ce`, sans modification de cette branche :

| Point | Comportement actuel de la PR #19 | Adaptation nécessaire |
| --- | --- | --- |
| Devis | `previewMission` garde `path` seulement si c’est un tableau d’UUID de longueur `hops + 1` ; `serverPath` exige départ = système de la flotte, arrivée = `destination_id`, systèmes présents dans la projection Galaxie | Aucune ; 0 saut accepté (`[départ]`) |
| `missions[]` | Validateur tolérant (champ ignoré), type `MissionView` sans `path` ; la carte ne connaît que les trajets des missions lancées dans l’onglet (mémoire locale) | Ajouter `path?: string[]` au type, le valider (UUID, `hops + 1`, départ = `origin.id`, arrivée = `destination.id`, sinon supprimé) et l’utiliser à la place de la mémoire locale |
| Position estimée | `missionPosition` suit `path` ; si un système du chemin manque sur la carte, aucune position n’est dessinée | Revenir au segment départ–destination, toujours libellé « estimée » |
| 0 saut | Un chemin d’un seul système ne produit aucun segment | Afficher la flotte sur son système, sans ligne |
| Retours | Retour dessiné à rebours de l’aller depuis le point estimé du rappel | Conserver, avec le libellé « retour estimé en miroir de l’aller » (conforme au moteur v0.9) |
| Fog of War | Seuls les systèmes de la projection Galaxie sont nommés ; un signal reste « Signal détecté » | Aucune |
| Tests | Vitest et Playwright sur un `path` simulé | Ajouter `missions[].path` valide/invalide, 0 saut, retour, système absent de la carte ; prototype : fixtures de missions avec `path` |
| Documentation | UX04 et passation décrivent la ligne indicative | Mettre à jour après le lot |

Ordre : publier cette PR, vérifier qu’aucun autre agent n’écrit sur `work/ux-redesign`, puis lot
frontend sur cette branche. Le champ étant optionnel, le lot ne dépend pas de la fusion de cette PR
(aucune dépendance circulaire) ; il se teste avec des réponses simulées puis en recette réelle
quand les deux branches sont réunies.

Conflits prévisibles quand les deux branches seront réunies : ce document existe aussi, en version
« contrat proposé », sur `work/ux-redesign` (garder la version de cette PR) ; `docs/README.md`
(lignes voisines) ; l’entrée temporaire de la Fast CI est identique dans les deux branches.

## Recette en univers réel (poste local)

1. Base de test : `RUN_DB_TESTS=1` et PostgreSQL `*_test` (cf. [reprise](../06-handoff/work-codex-handoff.md)),
   puis `cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q` (suite complète) et
   `.venv/bin/pytest -q tests/integration/test_mission_path.py tests/integration/test_combat.py tests/integration/test_frontier.py`.
2. Pile Compose de démonstration (univers v0.9), branche de cette PR : vérifier `alembic current`
   inchangé (aucune migration).
3. Avec un Empire humain, appeler le devis puis lancer : DEPLOY sur 2 sauts ou plus, SURVEY vers un
   signal, COLONIZE à 0 saut et distant, ATTACK distante. Pour chacun : `path` du devis = `path` de
   la mission dans `GET …/fleets/{empire}` ; `len(path) == hops + 1` ; chaque paire consécutive
   est une route connue ; la destination d’un SURVEY reste sans nom.
4. Rappeler un DEPLOY à mi-trajet : `path` inchangé, statut `returning`, passages `return` en miroir.
5. Laisser une ATTACK se résoudre : `path` inchangé au retour ; côté défenseur, aucune mission ni
   chemin de l’attaquant.
6. Provoquer une interception et une retraite 13B : mission interceptée avec son aller lancé ;
   retraite avec son propre `path`.
7. Session `fleet.read` seule, autre Empire, autre univers : aucun chemin étranger, mêmes 404.
8. Relire deux fois la projection : aucune écriture (missions, événements, legs inchangés).
9. Ancien client (frontend de #17) : les écrans Flottes et Galaxie fonctionnent sans changement.
