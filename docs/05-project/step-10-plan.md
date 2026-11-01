# Étape 10 — Colonisation et expansion

**Q07 ouverte : aucun code métier Colonization avant validation explicite de la proposition COL01.**
Base master `3a528b62079a4e177e65fdef7ce324b14784a08f` : étape 9 Flottes intégrée via PR #12, CI
post-merge 41322146062 success (5/5), vérifiée le 01/11/2026. Branche unique
`work/step-10-colonization`, une seule PR brouillon vers master. Aucun merge autorisé ; étape 11 IA
non commencée. Règles produit : [Colonisation](../01-game-design/colonization.md).

Critère de sortie roadmap : concurrence sur un monde résolue sans double propriétaire.
Périmètre : fondation pacifique d’une nouvelle Colony sur un monde connu, dans les limites que Q07
validera. Hors périmètre : IA, combat, relations, commerce, espionnage, conquête, défense active,
population, terraformation, traits planétaires complets (Q04).

| Ticket | Travail et preuve attendue |
| --- | --- |
| COL00 | Synchro post-merge (CI 41322146062 5/5), master ff-only, branche, PR brouillon, statuts canoniques, ce plan |
| COL01 | Réalisé : audit ci-dessous, [proposition Q07](../01-game-design/colonization.md) A1–A30 et sous-décision Q04 ; **arrêt** |
| COL02+ | Non autorisés avant validation de Q07 ; découpage proposé ci-dessous |

Pendant COL00/COL01 : documentation, audit, proposition et schémas conceptuels seulement. Aucun
ruleset v0.5 exécutable, classe ou mission de colonisation, migration, table, endpoint ou UI.

## COL01 — audit du code intégré (master `3a528b6`)

Lecture faite des documents produit, projet et technique exigés, puis du code : modèles, services,
migrations jusqu'à 0009, permissions, interface et recettes. Les écarts entre documentation et code
sont signalés comme tels.

### Ce qui permet déjà plusieurs colonies

- **Occupation :** `colonies` est limitée par Univers/Empire, et `uq_colonies_planet` garantit un
  seul occupant par planète.
- **Capacités :** la construction et la projection Colony utilisent déjà
  `planet.sector_capacity`, pas le ruleset (`colony/service.py` dans la planification d'ordre,
  `colony/projection.py`). Les emplacements orbitaux ne sont lus nulle part dans le jeu.
- **Monde généré :** `planets` et `galaxy_planets` portent déjà les capacités 9 à 18 et 1 à 3.
  `PlanetKnowledge` fige nom et capacités pour chaque Empire dès `map_system`.
- **Surveillance :** `refresh_monitoring` gère déjà plusieurs colonies propres par système.
- **Écran Colonie :** il a déjà un sélecteur dès qu'il y a plus d'une colonie, la liste est triée
  par `created_at`, et `Colonies.listing` filtre par `colony.read`.
- **Production de vaisseaux :** elle est possible dans toute colonie (capacité de base), avec une
  garnison créée à la demande par `garrison_for` ; une file par colonie.
- **Research :** la colonie de financement est explicite à chaque ordre.

### Ce qui doit réellement changer

1. **`initialize_colony` refuse toute planète autre que 12/2.** Il dote aussi gratuitement les
   stocks de départ et les quatre infrastructures en secteurs 1 à 4. Il faut créer un initialiseur
   distinct `found_colony`, piloté par le ruleset v0.5 et le paquet livré, sans toucher à la colonie
   de départ (A20). L'initialisation bas niveau `simulation.service.initialize` (stream, timeline et
   soldes explicites) est réutilisable telle quelle.
2. **Mission et flotte.**
   - `fleet_missions` : ajouter `COLONIZE` au CHECK de type, une colonne `target_planet_id` avec
     clé étrangère vers `planet_knowledge(empire, planet, universe)`, la contrainte
     `kind='COLONIZE' ⇔ cible`, un index de recherche des concurrents par
     `(universe_id, target_planet_id)` et l'index unique partiel « une COLONIZE active par Empire ».
   - `fleets` : ajouter le statut `SETTLED` et ses CHECK.
   - `colonies` : ajouter `founded_at` et `founding_mission_id` (unique).
3. **Snapshots.** La vérification du snapshot (correctif de l'étape 9) doit inclure la cible, le
   paquet minimum et le rang, avec des clés propres au type de mission : les snapshots v0.4
   existants ne changent pas.
4. **Projection Flottes.** `colony_here` choisit la *première* colonie du système, ce qui devient
   ambigu avec deux colonies propres dans un même système. Il faut une liste par planète pour
   CHARGER/DÉCHARGER (l'API prend déjà un `colony_id` explicite). La projection doit aussi exclure
   `SETTLED`, comme elle exclut déjà `MERGED`.
5. **Ruleset.** Le chargeur associe aujourd'hui « v0.4+ » à galaxy + fleets. v0.5 ajoute
   `colonization`, obligatoire en v0.5 et absent de v0.1 à v0.4. `ShipClass` gagne un indicateur
   `colonize` et une quantité maximale par classe, avec des valeurs par défaut pour v0.4 sans en
   changer le contenu.
6. **Permissions.** Passage à 13 si A27 est validé : contrats, schéma, Portal, CHECK, tests et
   révisions Alembic attendues par les recettes.

### Interactions inattendues avec Flottes v0.4

- **Invariant à amender :** « les handlers n'écrivent jamais dans une colonie » est incompatible
  avec une fondation par handler. L'amendement A23 limite l'interdiction aux colonies existantes ;
  la création se fait dans la transaction du handler, avec un stream neuf. L'autre option est une
  fondation en deux temps (victoire, puis commande), plus fragile.
- **Concurrence multi-stream :** deux Empires = deux streams. La solution passe par un verrou de
  ligne sur la planète et un rang immuable (A17), sans second stream. Le rappel doit prendre le même
  verrou planète.
- **Consommation d'unité :** la règle de l'étape 9 « une flotte opérationnelle garde au moins une
  unité » interdit une flotte vide. La consommation passe donc par le nouveau statut `SETTLED`
  plutôt que par une suppression.
- **Retard du worker :** si la tête du stream d'un Empire est bloquée, sa colonisation mieux classée
  ne se résout pas, et les concurrents moins bien classés échouent. Le comportement reste
  déterministe et doit être documenté pour l'opérateur.
- **Sites de départ candidats :** ils sont colonisables (Q06 interdit les réservations). La future
  IA (étape 11, Q11) devra donc être provisionnée à la création de l'univers, avant que ces sites ne
  soient pris. C'est à noter pour Q11, sans le décider ici.
- **Rien à changer :** le carburant est payé par la colonie d'attache, le retour se fait vers
  l'attache, `speeds.fleet` ne s'applique qu'aux trajets, et `known_path(mapped=True)` couvre déjà
  COLONIZE.

### Écarts entre documentation et code

- **`colony-economy-v0.1.md` :** la phrase sur le contrôle de capacité « limité à la référence » est
  exacte. En revanche, la doc ne dit pas que la construction utilise déjà les capacités réelles de
  la planète, ce qui simplifie l'étape 10.
- **`planets-colonies.md` :** il annonce que « l'identité de l'occupant et le transfert devront être
  arbitrés avant les migrations métier ». C'est cohérent avec Q07, qui reste ouverte, et
  l'occupation courante reste `uq_colonies_planet`.

## Découpage proposé après validation de Q07

| Ticket | Travail et preuve attendue |
| --- | --- |
| COL02 | Ruleset v0.5 (copie v0.4, colonisateur, `colonization.json`), chargeur, validation et tests de règles ; v0.1–v0.4 inchangés |
| COL03 | Migration 0010 depuis un DDL figé (mission COLONIZE et cible, `SETTLED`, historique colonie, index, permissions 13), downgrade refusé avec données |
| COL04 | `found_colony` : capacités réelles, paquet → stocks, aucune infrastructure gratuite, timeline ancrée à `due_at` ; colonie de départ inchangée |
| COL05 | Mission COLONIZE : lancement, snapshot, rang, verrou planète, règle de victoire, consommation/`SETTLED`, coût progressif et plafonds |
| COL06 | Rapports, connaissance (MONITORED sans révélation), rappel avec verrou planète, perdant stationné |
| COL07 | API (devis/lancement COLONIZE) et permission `colony.expand` partout, tests 13/14 |
| COL08 | Interface : dialogue Flottes, « Coloniser… » dans System View, sélecteur multi-colonies, CHARGER/DÉCHARGER par planète |
| COL09 | Tests : concurrence (deux Empires, `due_at` égaux ou différents, deux workers), idempotence, non-fuite, responsive |
| COL10 | Recette Compose réelle : fabrication, paquet, colonisation, concurrence, Portal coupé, expiration |
| COL11 | Revue indépendante, CI 5/5, documentation, passation |

### Tests prévus pour COL02 et après

- **Concurrence :** deux Empires sur la même planète, avec des `due_at` égaux ou différents, deux
  workers, et un ordre de traitement inversé qui doit donner le même gagnant.
- **Tentatives répétées :** deux tentatives du même Empire ; mission contre rappel ; arrivée contre
  nouvelle tentative.
- **Cibles refusées :** cible déjà possédée, autre univers, inconnue, DETECTED seulement ;
  connaissance obsolète.
- **Reprise :** nouvelle tentative d'événement, idempotence, redémarrage du worker, Portal coupé,
  session expirée.
- **Fuites :** aucune fuite de l'Empire occupant, ni dans les rapports, ni dans l'API, ni dans
  l'interface.
