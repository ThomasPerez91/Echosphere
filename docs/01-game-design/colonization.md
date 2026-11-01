# Colonisation

**Statut : Q07 close pour le périmètre de l'étape 10 — validation explicite du 01/11/2026 avec
amendements (section ci-dessous), ainsi que la sous-décision Q04 ; implémentée sur PR #13
([technique](../03-technical/colonization-api-ui.md)).** Les chiffres
sont la balance v0.5 dans game_data versionné, jamais des constantes métier ni des vérités du
produit. La proposition A1–A30 ci-dessous s'applique telle qu'amendée.

Coloniser doit rester un choix d'expansion, pas une collecte automatique de mondes. On compare les
secteurs, l'accès et la position stratégique. Gérer des dizaines de planètes une par une n'est pas
l'objectif.

## Parcours cible

Découvrir → évaluer → préparer → envoyer → résoudre côté serveur → intégrer une vraie colonie.
Pas de clic « coloniser » gratuit, pas de récompense liée au temps connecté, pas de simulation
continue.

## Charge cognitive

Référence orientative : 1 colonie, puis 2–3, 4–6 et environ 8–12 au fil de la progression. Ces
repères ne deviennent pas des paliers de technologie sans décision explicite (voir A14).

## Amendements validés le 01/11/2026 (priment sur la proposition)

- **Q04 (v0.5 seulement) :** aucune habitabilité, aucun trait actif, aucune planète interdite ;
  9/12/15/18 secteurs et 1/2/3 orbitaux valides ; capacités physiques seule différence. Q04 reste
  ouverte globalement (traits, bonus/malus, orbital jouable, réaffectation, démolition).
- **Monde déjà possédé par l'Empire :** avec `colony.read`, refus explicite `target_owned` ; sans
  `colony.read`, refus générique `target_unavailable`, sans code révélateur. `colony.read` n'est
  pas exigé pour COLONIZE.
- **Paquet :** au moins le minimum, au plus la capacité cargo ; à la réussite, **tout** le cargo
  engagé devient le stock initial ; à l'échec ou au rappel, tout reste à bord.
- **Coût progressif :** N = colonies + colonisateurs existants + ordres de colonisateur ouverts ;
  consommer un colonisateur laisse N inchangé. Multiplicateur et coût exact figés à l'acceptation,
  annulation calculée sur le prix accepté (100/80 théoriques, plafond Q39).
- **Devis de production dynamique :** avant confirmation d'un ordre de colonisateur, le coût
  serveur courant (avec N) est affiché ; la commande le recalcule sous le verrou de la chronologie
  d'opérations d'Empire, qui sérialise deux commandes concurrentes (jamais deux fois l'ancien prix).
- **Colonisation dans le même système :** une autre planète du système où stationne la flotte est
  colonisable. Exception propre à COLONIZE : chemin vide, 0 saut, 0 trajet, 0 carburant,
  `travel_arrival_at = due_at = started_at`, mission persistée et résolue par le worker, aucun
  rappel. DEPLOY/SURVEY/RETURN gardent leurs invariants (chemin non vide).
- **Concurrence :** seule une mission concurrente `active`, non rappelée et mieux classée bloque.
  Une mission `completed`, `returning` ou rappelée ne bloque jamais. Une mission restée `active`
  derrière un événement `blocked` continue de bloquer : incident opérateur, pas résolution de jeu.
- **Rappel contre arrivée :** sérialisés, jamais colonie créée + rappel accepté, jamais un
  colonisateur à deux endroits ni deux rapports ; fenêtre de rappel décidée par l'heure serveur.
- **Projection multi-colonies d'un même système :** CHARGER/DÉCHARGER choisissent explicitement la
  colonie (`colonies_here`, filtré par `colony.read`), plus de « première colonie » implicite.
- **Snapshot COLONIZE :** couvre aussi planète cible, paquet minimum, rang et paramètres de
  plafond/cadence ; toute dérive avant le worker → `TimelineError`, aucun effet partiel.

## Proposition Q07 (COL01)

Base de la proposition : l'audit du code intégré à master `3a528b6` ([plan](../05-project/step-10-plan.md)).
Chaque arbitrage donne une **recommandation**, une alternative raisonnable quand il y en a une, et la
raison.

### Ruleset et périmètre

- **A1 — Nouveau ruleset v0.5.** v0.5 = copie complète de v0.4, plus le colonisateur, la mission
  COLONIZE et les règles d'expansion. Les univers v0.1 à v0.4 restent inchangés : un univers v0.4
  garde Flottes et SURVEY sans colonisation, et aucune migration silencieuse n'a lieu.
  - **Fichiers :** la classe `colonizer` va dans `fleets.json`. Les règles d'expansion vont dans un
    nouveau `colonization.json` : paquet minimum, coût progressif, plafonds, état initial.
  - **Alternative :** tout mettre dans `fleets.json`. Rejetée : cela mélange le catalogue de
    vaisseaux et les règles de colonie.
- **A2 — Périmètre v0.5 :** fondation pacifique d'une nouvelle colonie sur un monde connu. Pas
  d'abandon ni de transfert (voir A24 et A25). Pas de conquête, d'occupation militaire, de combat ou
  de traits planétaires.

### Éligibilité d'un monde

- **A3 — Connaissance minimale.**
  - Le système cible doit être au moins MAPPED (MAPPED ou MONITORED).
  - La planète exacte doit figurer dans `PlanetKnowledge` de l'Empire. Elle y figure dès la
    cartographie du système (structure durable).
  - Un système DETECTED ou un monde inconnu est refusé, avec la même erreur qu'un monde
    inexistant.
- **A4 — Tous les mondes générés sont éligibles :**
  - 9, 12, 15 ou 18 secteurs, et 1, 2 ou 3 emplacements orbitaux ;
  - pas de capacité minimale ;
  - pas d'habitabilité en v0.5 ;
  - aucune planète interdite, sites de départ candidats compris : ils ne sont pas des réservations
    (Q06).

  Seules les capacités physiques différencient les mondes. Les emplacements orbitaux restent une
  capacité réservée, sans effet sur l'éligibilité.
- **A5 — Monde déjà occupé par l'Empire lui-même :** refus au lancement (`target_owned`). C'est
  une information propre, donc sans fuite. Plusieurs colonies du même Empire dans un même système
  sont permises, sur des planètes différentes.

**Q04 — sous-décision nécessaire à l'étape 10 (à valider avec Q07) :** « En v0.5, aucune
habitabilité, aucun trait et aucune interdiction : tout monde généré est colonisable, et ses
capacités physiques sont sa seule différence. » Le reste de Q04 reste ouvert : catalogue, effets des
traits, emplacements orbitaux jouables, démolition et réaffectation.

### Connaissance et occupation réelle (Q08)

- **A6 — Lancement accepté sur la seule connaissance de l'Empire.**
  - Le serveur ne vérifie pas, au lancement, l'occupation étrangère ni les missions concurrentes, et
    ne refuse donc rien pour ces raisons. Un refus immédiat révélerait une présence que le
    brouillard de guerre ne permet pas de connaître.
  - L'occupation est vérifiée à l'arrivée, physiquement sur place.
  - **Alternative :** refus immédiat. Rejetée, car c'est une fuite gratuite (MAPPED → lancement →
    « Empire déjà présent »).
- **A7 — Ce qui est révélé à l'arrivée :** seulement que « ce monde n'était pas disponible à
  l'arrivée » (`target_unavailable`). Ne sont jamais révélés : l'Empire occupant, ses flottes, sa
  défense, ses stocks ou son activité. On ne distingue pas non plus « occupé » de « contesté par une
  arrivée simultanée » : `colonization_contested` révélerait une activité concurrente.

  En v0.5, rien n'est écrit dans la connaissance : pas de nouvel état d'occupation étrangère. Le
  rapport de mission est daté et immuable. Une observation étrangère durable relèvera d'un futur lot
  de renseignement.
- **A8 — Formulation de l'interface :** jamais « Libre ». Pour un monde sans colonie propre, on
  affiche « Occupation actuelle inconnue ».

### Colonisateur

- **A9 — Classe `colonizer` (« Colonisateur »), balance provisoire :**

  | Paramètre | Valeur proposée |
  | --- | --- |
  | Coût de base | 1 200 Alliages, 600 Flux, 300 Données |
  | Fabrication | 3 h, sans vitesse ni bonus (même règle que v0.4) |
  | Saut | 30 min (le plus lent du catalogue) |
  | Carburant | 20 Flux par saut |
  | Cargo | 1 000 (porte le paquet de fondation, voir A13) |
  | Cartographie | Non |
  | Quantité par ordre | 1 |

  Pour comparaison : sonde 80/40/40, cargo léger 200/60/20. Un ordre limité à 1 unité garde le coût
  progressif simple (A14).
- **A10 — Colonisateur consommé à la fondation (option A), recommandée.**
  - En cas de succès, il devient le noyau conceptuel de la colonie (Command Core) : il n'existe plus
    comme unité.
  - **Option B (réutilisable), rejetée :** sans perte réelle, un seul vaisseau coloniserait en
    boucle, ce qui détruit la cadence et le coût d'expansion.
  - En cas d'échec ou de rappel, il est conservé intact avec son cargo.
- **A11 — Une flotte vidée par la fondation n'est jamais supprimée.** Elle passe au nouveau statut
  persistant `SETTLED` : sans système, sans unités ni mission active. Elle reste dans l'historique
  comme une flotte MERGED, et ses missions et rapports gardent leur clé étrangère. Elle disparaît des
  listes actives.

### Mission COLONIZE

- **A12 — Composition et cible.**
  - La flotte compte **exactement 1 colonisateur et rien d'autre** : pas de sonde ni de cargo léger
    en v0.5. Cela évite les escortes et les restes de flotte après consommation.
  - La destination métier est une **planète** (`target_planet_id`). Le trajet suit la mécanique
    Flottes existante jusqu'au système parent, par `known_path`, sur un système MAPPED ou mieux.
  - Le carburant suit la formule v0.4 (`sauts × 20 Flux`) et il est payé par la colonie d'attache.
  - Tout est figé à l'acceptation : chemin, composition, cargo, règles, rang et cible.
- **A13 — Coût réel : modèle 3, recommandé. Le colonisateur, plus un paquet de fondation physique
  transporté dans sa cargaison.**
  - **Comment ça marche :** le joueur charge le paquet avec la commande CHARGER existante. Il est
    figé au lancement, puis versé à la nouvelle colonie seulement si la fondation réussit. En cas
    d'échec ou de rappel, il reste à bord sans perte. Aucune ressource n'est téléportée, et le
    mécanisme réutilise la cargaison de l'étape 9.
  - **Minimum exigé au lancement (provisoire) :** 500 Alliages, 250 Flux, 50 Données, soit de quoi
    bâtir environ deux producteurs. Plafond : la capacité cargo de 1 000.
  - **Modèle 1, rejeté :** le colonisateur seul ne paie pas le démarrage, et la colonie naîtrait
    vide ou dotée gratuitement.
  - **Modèle 2, rejeté :** un coût fixe débité au lancement, ce sont des ressources « téléportées »
    et perdues en cas d'échec concurrent.
  - **Contrainte acceptée :** la colonie d'attache doit disposer du paquet. Le joueur prépare
    l'expédition, ce qui est l'objectif.
- **A15 — Résolution immédiate à l'arrivée** (`due_at = travel_arrival_at`).
  - La concurrence est réglée par le rang (A17), donc une phase d'établissement n'apporte aucune
    décision au joueur. Ce serait de l'attente décorative, puisqu'il n'y a ni combat ni défense
    avant l'étape 12.
  - **Alternative :** une phase d'établissement de durée X. Elle ne se justifierait qu'avec une
    interaction possible pendant cette phase, plus tard.
- **A16 — Rappel**, identique au contrat de l'étape 9 :
  - possible pendant le trajet seulement (`now < travel_arrival_at`) ;
  - retour symétrique en temps vers le système d'origine, sans coût ni remboursement du carburant ;
  - colonisateur et cargo conservés ;
  - l'événement d'arrivée est acquitté `cancelled` ;
  - idempotent par clé d'intention ;
  - un rappel dont la mission a dérivé est refusé, comme le correctif snapshots de l'étape 9.

### Cadence et plafonds

- **A14 — Plafond souple, plus un plafond dur de sécurité.**
  - **Coût progressif du colonisateur :** multiplicateur `1 + 0,5 × (N − 1)`, figé à l'acceptation
    de l'ordre de fabrication. N compte, à cet instant, les colonies de l'Empire, ses colonisateurs
    existants et ses ordres de colonisateur ouverts. Exemples : N = 1 → ×1, N = 3 → ×2, N = 8 →
    ×4,5. On ne peut pas contourner la règle en stockant des colonisateurs bon marché.
  - **Plafond dur v0.5 :** 12 colonies par Empire, en comptant les colonies et les missions COLONIZE
    actives. Il est vérifié au lancement et versionné dans `colonization.json`.
  - **Alternatives :** plafond dur seul (frustrant, sans gradient) ou aucun plafond (un empire de
    50 colonies devient facile dès que la base de données le permet).
  - Tout reste simulable en entiers.
- **A18 — Une seule mission COLONIZE active par Empire.**
  - Garantie en base par un index unique partiel `(empire_id) WHERE kind='COLONIZE' AND
    status='active'`. Une mission rappelée (`returning`) ne compte pas.
  - Le cas « deux missions du même Empire vers la même planète » en découle.
  - Cette règle est distincte de « une mission par flotte » et des files de recherche et de
    production. Elle cadence l'expansion et la charge cognitive, et reste simple pour la future IA.
  - **Alternative :** une mission par colonie, ou aucune limite autre que le coût.

### Concurrence sur un même monde (critère de sortie)

- **A17 — Pas de réservation au lancement : la décision se prend à l'arrivée, selon un rang
  immuable.** Cela conserve l'intention « deux arrivées concurrentes » et évite la fuite qu'une
  réservation provoquerait (un refus au lancement révélerait la mission d'un autre Empire).
  - **Rang d'une mission :** `(due_at, started_at, mission_id)`, figé à l'acceptation. Plus petit =
    prioritaire. Avec des `due_at` égaux, la mission acceptée la première l'emporte ; si `started_at`
    est aussi égal, l'UUID persistant tranche.
  - **Règle de victoire :** la mission M fonde sa colonie sur la planète P si et seulement si :
    1. P n'a aucune colonie ;
    2. aucune autre mission COLONIZE vers P, dans le même univers, n'est à la fois **engagée** et
       **mieux classée**. « Engagée » veut dire non rappelée (`recalled_at IS NULL`) et non
       `returning`.
  - **Pourquoi c'est déterministe :** quand M est résolue, `now ≥ due_M`. Toute mission mieux classée
    a `due ≤ due_M`, donc sa fenêtre de rappel est déjà close : le fait qu'elle soit engagée est
    définitif. La décision ne dépend donc que des missions persistées et de leurs rangs, jamais de
    l'ordre des workers.
  - **Exemple :** si B (moins bien classée) est traitée avant A à cause d'un retard du worker, B voit
    A engagée et échoue sans fonder. A fonde ensuite. Le résultat est identique dans l'ordre
    inverse.
  - **Seule raison d'échec :** « monde indisponible ». Si A échoue parce que P est déjà occupée, B
    échoue pour la même raison.
- **Transaction (problème multi-stream, Q13).**
  - Chaque handler prend son propre stream d'opérations d'Empire, puis un verrou de ligne
    `FOR UPDATE` sur la planète cible (`planets`). C'est un verrou de ligne, pas un second stream.
  - Le rappel d'une mission COLONIZE prend le même verrou planète, après son propre stream. Il est
    donc sérialisé avec un handler concurrent qui lit « rappelée ou non ».
  - **Ordre de verrous :** stream de son Empire → planète. Personne ne détient une planète en
    attendant un stream, donc il n'y a pas d'interblocage.
  - Chaque handler n'écrit que sa propre flotte, sa mission, son rapport, sa connaissance et, en cas
    de victoire, la nouvelle colonie.
  - **Garanties en base :** `uq_colonies_planet` existe déjà (un seul propriétaire) ; un nouveau
    `founding_mission_id` unique garantit qu'une mission fonde au plus une colonie.
- **A19 — Le perdant.**
  - Sa mission est `completed`, avec un rapport `{outcome: failed, reason: target_unavailable}` et
    `observed_at = due_at`.
  - Sa flotte est stationnée dans le système cible, puisqu'elle y est physiquement arrivée. Il n'y
    a pas de retour automatique ni de téléportation.
  - Le colonisateur et le paquet sont conservés à bord ; le carburant n'est pas remboursé.
  - Le joueur choisit ensuite : RETURN, DEPLOY ou une autre colonisation. Le rapport ne nomme jamais
    le gagnant.
  - **Incident possible :** si une mission mieux classée reste bloquée pour un incident opérateur,
    les moins bien classées échouent alors que personne ne fonde. Ce cas reste déterministe, et il
    est documenté pour l'opérateur.

### Nouvelle colonie

- **A20 — État initial, avec un nouvel initialiseur général (`found_colony`).** Il est distinct de
  `initialize_colony`, qui reste l'initialiseur de la colonie de départ de référence, inchangé pour
  v0.1 à v0.4.
  - Capacités : celles de la planète générée (9 à 18 secteurs, 1 à 3 emplacements orbitaux). Le 12/2
    n'est pas imposé.
  - Bâtiments : aucune infrastructure gratuite ; Command Core conceptuel, hors secteurs ; tous les
    secteurs sont libres.
  - Ressources : stocks égaux au paquet livré, production 0/h, capacité de stockage de base de
    10 000 par ressource, venant du ruleset v0.5.
  - Fonctionnement : file de construction ordinaire (3 ordres, 1 actif). Nom = nom de la planète.
  - Timeline, `ColonyEconomy` et nouvel EventStream créés et ancrés à `due_at`.
  - **Alternative :** une petite production gratuite du Command Core. Rejetée : une colonie mal
    démarrée se ravitaille par le transport de l'étape 9 (CHARGER → DEPLOY → DÉCHARGER), ce qui
    relie colonisation et logistique.
- **A21 — Flottes après la fondation.**
  - `home_colony_id` ne change pas : aucun changement de base, ni implicite ni automatique, en v0.5.
  - RETURN vise toujours le système de la colonie d'attache.
  - La nouvelle colonie n'a pas de garnison immédiate : elle naît à la première production de
    vaisseau locale (`garrison_for` paresseux, déjà en place). La production v0.4 utilise la capacité
    de base de toute colonie, donc la nouvelle colonie peut produire dès qu'elle a les ressources.
  - Un changement de base reste un arbitrage futur explicite.
- **A22 — Connaissance après le succès :** colonie créée, puis `refresh_monitoring` de l'Empire. Le
  système cible passe MONITORED avec la présence propre datée.
  - Pas de `map_system` : aucun voisin découvert, aucune route révélée.
  - Pas de révélation d'Empires étrangers, de stocks ou de capteur.
- **A23 — Amendement d'un invariant de l'étape 9 :** « les handlers Flottes n'écrivent jamais dans
  une colonie » devient « jamais dans une colonie **existante** ». La victoire COLONIZE **crée** une
  colonie, avec son propre stream neuf, dans la même transaction. Aucun stream existant n'est pris,
  et aucune autre colonie, Research ou Portal n'est touché. Cet amendement est à valider.

### Abandon, transfert et historique

- **A24 — Abandon reporté.** En v0.5, une colonie n'est pas abandonnable. Un abandon implique les
  ressources, les constructions actives, les financements Research, les flottes d'attache, la
  cargaison, le brouillard de guerre et l'historique : aucune pseudo-implémentation partielle.
- **A25 — Transfert reporté** aux futurs lots relations, diplomatie et conquête. Changer `empire_id`
  ne suffit pas : il faudrait aussi traiter les timelines, Research, l'attache des flottes, la
  connaissance et les permissions.
- **A26 — Historique minimal.** `colonies.founded_at` (date logique) et
  `colonies.founding_mission_id` (FK unique), tous deux nuls pour les colonies de départ. Avec le
  rapport de mission, cela suffit tant qu'abandon et transfert sont reportés. Pas de table
  d'occupation historique.

### Permissions, API, interface et IA

- **A27 — Nouvelle permission `colony.expand`** : le total passe à 13 permissions, dans le DTO
  Game, le schéma partagé, Portal et le CHECK SQL, avec des tests « 13 acceptées, 14 refusées ». Il
  n'y a aucune attribution automatique.

  | Action | Droits requis |
  | --- | --- |
  | Lancer ou faire le devis d'une mission COLONIZE | `fleet.command` + `galaxy.read` + `colony.expand` |
  | Fabriquer un colonisateur | `fleet.build` + `colony.read` (ordres v0.4) |
  | Lire les missions | `fleet.read` |
  | Lire la nouvelle colonie | `colony.read` |

  - **Pourquoi :** une fondation est irréversible en v0.5 et crée un actif majeur. Un Empire partagé
    (Q21) doit pouvoir confier les opérations de flotte sans confier l'expansion.
  - **Alternative :** `fleet.command` seul. `colony.construct` n'est pas réutilisé, car il couvre la
    construction dans une colonie existante.
- **A28 — API :** extension de l'API Flottes existante, sans seconde API de déplacement.
  `POST .../fleets/{empire}/missions/preview` et `.../missions` acceptent `kind = COLONIZE` avec
  `target_planet_id`. Le devis serveur indique le chemin, le carburant, l'arrivée, le paquet à bord
  comparé au minimum, et le rang uniquement pour les missions de l'Empire lui-même. Aucun endpoint
  spécial IA.
- **A29 — Interface minimale.**
  - **System View :** un bouton « Coloniser… » par monde connu sans colonie propre, si les droits le
    permettent. Il ouvre le même dialogue Flottes que les autres missions.
  - **Dialogue Flottes :** planète cible, colonisateur, trajet, coût, paquet, arrivée, puis résultat.
  - **Écran Colonie :** après un succès, la nouvelle colonie apparaît dans le sélecteur existant.
    Il n'y a aucune nouvelle entrée de navigation globale.
  - Mobile de 320 à 1440 px, clavier et focus, dialogues, cibles de 44 px. Aucune logique de
    colonisation dupliquée dans React.
- **A30 — IA future (étape 11) :** mêmes services, coûts, brouillard de guerre et commandes. Aucun
  code IA en étape 10.

## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md) · [Flottes](fleets.md) · [Brouillard](fog-of-war.md)
- [Temps serveur](../03-technical/event-engine.md) · [Plan étape 10](../05-project/step-10-plan.md)
