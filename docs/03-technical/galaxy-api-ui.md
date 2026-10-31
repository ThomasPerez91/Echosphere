# Galaxie et Exploration — contrat technique étape 7

**Statut : implémenté sur PR #10 (brouillon puis Ready), non fusionné ; vérifier GitHub avant reprise.**
Contrats produit : [Galaxie/Q06](../01-game-design/galaxy.md), [Exploration](../01-game-design/exploration.md),
[Fog/Q08](../01-game-design/fog-of-war.md). Plan et preuves : [étape 7](../05-project/step-7-plan.md),
[progress](../../progress.md). Q09 (Fleet) reste ouverte ; étape 8 System View non commencée.

## Ruleset et génération

`game_data/rulesets/v0.3` est un ruleset complet : ressources, Colony, infrastructures, Research,
`galaxy` (paramètres galaxy-v1) et `exploration` (abstract-expedition-v1). v0.1/v0.2 sont inchangés
et refusent ces sections ; aucun Universe existant n’est migré vers v0.3. Générateur pur et corpus :
[progress G02](../../progress.md#g02--générateur-et-corpus-de-robustesse-31102026),
`PYTHONPATH=backend python3 scripts/measure_galaxy.py` pour les mesures opérateur.

`app.galaxy.world.generate_world` est un service **explicite** (opérateur/test/headless), jamais
appelé au GET, au démarrage ni par migration. Sous verrou Universe : refus si le ruleset épinglé
n’a pas de galaxie ou si l’Universe possède déjà des systèmes ; rejeu de la même intention (seed,
taille, sites, données) → même manifeste ; paramètres différents → `IdempotencyConflict`. Publication
atomique : manifeste `universe_galaxies` (version, entrées complètes dont snapshot des données,
empreinte SHA-256 du monde canonique), puis StellarSystem/Planet existants et leurs extensions
`galaxy_systems` (ordinal, position entière), `galaxy_planets` (ordinal), `galaxy_routes`
(extrémités ordonnées, paire unique) et `galaxy_starting_sites` (candidats internes, jamais exposés,
aucune réservation gameplay). Un seul site est utilisé par la recette.

## Persistance et connaissance

Migration Game **0008_galaxy_exploration** après 0007, DDL figé : douze tables, FK composites
Universe partout (routes ↔ systèmes, planète ↔ système, Knowledge ↔ Empire/système, mission ↔
colonie/Empire/Universe, étapes ↔ routes, rapport ↔ mission), contrainte d’unicité ajoutée sur
`planets (id, system_id, universe_id)`, CHECK des permissions de binding étendu. Downgrade possible
à vide, refusé si une table Galaxy/Exploration est peuplée ou si un binding porte un droit Galaxy.
Les migrations 0001–0007 ne changent pas ; Accounts n’a pas de migration (permissions transportées).

**UNKNOWN = absence de ligne.** `system_knowledge` porte DETECTED/MAPPED/MONITORED par Empire :
DETECTED = position approximative (centre de cellule `detected_cell_size`) sans aucune structure ;
MAPPED/MONITORED = nom, position exacte et `mapped_at` copiés au moment de la cartographie
(CHECK `ck_system_knowledge_structure`) ; MONITORED exige `last_seen_at` et observation.
`planet_knowledge` copie nom/capacités ; `route_knowledge` n’existe qu’entre deux systèmes connus
(deux FK vers la Knowledge du même Empire). Les projections lisent **uniquement** ces tables : aucune
jointure vers le monde réel pour enrichir une réponse, aucun filtrage Python/React d’un monde complet.

Surveillance : seul le système contenant une colonie propre devient MONITORED (observation =
identifiants de ses propres colonies), rafraîchi à la lecture sous le stream Exploration, sans timer.
Sans présence réelle : MONITORED → MAPPED, structure et `last_seen_at` conservés. Aucun partage
entre Empires. `initialize_empire` (explicite, après la vraie colonie) : origine cartographiée puis
surveillée, voisins directs DETECTED et routes incidentes ; Research initialisé avant le stream
Exploration pour ne jamais prendre le verrou Empire après lui.

## Exploration, temps et verrous

`empire_exploration` lie un EventStream par Empire. Commande `start` : autorisation, rattrapage
Exploration, idempotence, destination DETECTED, plus court chemin BFS **sur RouteKnowledge seule**
(intermédiaires MAPPED/MONITORED, départage stable par identifiant), capacité unique (index partiel
`ix_exploration_active`, 0 file), rattrapage Research puis Colony source, devis v0.3
(50 Alliages, 50 + 10 × h Flux, 25 Données ; durée 15 min × (2h + 1)), débit intégral, mission,
étapes `exploration_mission_legs`, snapshot et `EXPLORATION_COMPLETE` dans la même transaction.
Aucune annulation/rappel/remboursement/perte aléatoire. Ordre : principal Game → Exploration →
Research → Colony ; aucun code Colony/Research ne prend Exploration.

Handler dans le TimeEngine/worker existant, sous le seul stream Exploration : vérifie payload,
Universe, stream, clé, échéance, snapshot recalculé depuis les règles épinglées et contiguïté du
chemin persistant ; toute incohérence lève (rollback, retry/blocked opérateur), jamais faux succès
ni remboursement. Effets atomiques : destination MAPPED, voisins UNKNOWN → DETECTED, routes
incidentes, rapport immuable (`observed_at = due_at`, `processed_at` réel, chemin, routes, voisins
approximatifs), mission completed. Aucun débit, appel Portal, session ou second stream.

## API et permissions

Préfixe Game `/game/{universe_id}` (navigateur : `/api/game/...`).

| Méthode / chemin relatif | Contrat |
| --- | --- |
| GET `/galaxy` | Empires du membership effectif portant `galaxy.read` |
| GET `/galaxy/{empire_id}` | Systèmes/routes connus, sources et devis serveur (si `colony.read`), missions (si `exploration.read`) |
| GET `/galaxy/{empire_id}/systems/{system_id}` | Détail selon l’état ; UNKNOWN/absent/étranger → même 404 `system_not_found` |
| GET `/exploration/{empire_id}/missions` | Missions et rapports figés, `exploration.read` |
| POST `/exploration/{empire_id}/missions` | `idempotency_key`, `colony_id`, `destination_id` ; chemin/coût/durée calculés serveur |

Démarrer exige `galaxy.read` + `exploration.read` + `exploration.start` + `colony.read`, pas
`colony.construct` ni privilège implicite. Binding sans `galaxy.read` : 404 comme Empire inconnu ;
droit manquant : 403. Clé d’intention isolée par membership ; même clé/même corps → même mission,
même clé/autre corps → 409 `idempotency_conflict`. Refus métier 409 (`destination_mapped`,
`destination_unreachable`, `exploration_active`, `insufficient_resources`, `galaxy_unavailable`),
503 retry technique. Enveloppes GET/POST, CSRF, Origin, no-store et absence d’activité en lecture
identiques à Colony/Research. Permissions ajoutées au DTO de contrôle (9 droits), au schéma
partagé v1, à l’allowlist Portal et au CHECK SQL ; aucun grant existant n’est modifié.

## UI et recette

Écran Galaxie du shell : carte SVG + HTML limitée à la projection, pan pointeur/tactile dans la carte
(`touch-action: none` sur la carte seule), zoom molette/boutons/clavier, recentrage, nœuds focusables
(Entrée/Espace), liste textuelle équivalente, légende par forme et texte, panneau de détail par état,
devis serveur, confirmation irrévocable, mission active datée et rapports. Les marqueurs DETECTED
partageant une cellule sont écartés à l’affichage seulement. Validation stricte des réponses : une
réponse DETECTED avec structure ou une référence orpheline est refusée. Même discipline de commande
que Research (aucune mutation au rendu, clé réutilisée seulement après résultat inconnu).

Recette réelle : `python3 scripts/smoke_galaxy_compose.py` après build Compose du même arbre.
Projet unique sans ports hôte, bases `echosphere_galaxy_game_test` / `echosphere_galaxy_accounts_test`,
volumes détruits à la fin. Fixture strictement test : génération explicite, un Empire sur un site,
legs Exploration de 2 s pour cette instance (coûts réels). Login/handoff réel, carte limitée,
lancement, page fermée, redémarrage du worker, preuve en base (mission, MAPPED, rapport) avant
réouverture ; Portal API/contrôle arrêtés, nouvelle expédition et progression ; expiration → 401
sur commande pendant qu’une expédition déjà acceptée se termine. Résultats : progress et CI.

## Limites

Pas de Fleet, IA, colonisation, combat, capteurs, anomalies ni System View. Création complète de
partie et affectation multi-Empires des sites candidats hors lot. Noms générés provisoires
(« System NNNNNN », « World n »). Aucune garantie de charge au-delà des mesures G02.
