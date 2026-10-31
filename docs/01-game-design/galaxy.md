# Galaxie

**Statut : Q06 close produit pour étape 7, validation utilisateur explicite du 31/10/2026 avec amendements ; implémentée sur PR #10 (G02–G10), [contrat technique](../03-technical/galaxy-api-ui.md).**


La galaxie est un graphe de systèmes stellaires et routes, pas une grille de coordonnées à la OGame.
Les positions 2D servent la représentation ; les edges définissent les trajets. Des carrefours,
frontières, accès défendables et régions lointaines doivent compter dans les décisions.

Repère provisoire : 30–50 systèmes pour le prototype/MVP. Les tailles futures seront configurables ;
100–150 est une ancienne proposition, pas une taille standard validée.
Génération procédurale reproductible avec seed. La reproductibilité exige aussi une version du
générateur et de ses données ; une seed seule n'est pas une garantie entre versions.

## Génération future

Q06 fixe désormais connexité, longueurs, impasses, mondes et équité dans le contrat ci-dessous. Vérifier chemins accessibles, absence d'isolats involontaires et répartition des occasions
d'expansion. Ne pas imposer une topologie finale dans l'étape 0.

Le serveur détient la carte complète ; les projections API respectent les connaissances de chaque
empire. Les coordonnées ou identifiants cachés ne doivent pas fuiter dans un payload global.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Proposition Q06 — G01, 31/10/2026, en attente de validation

**Contrat validé par l’utilisateur le 31/10/2026 avec amendements**, issu de la proposition G01.
L’intitulé de section est conservé pour les liens historiques. Q06 close dans cette portée ;
les valeurs restent des paramètres de balance versionnés, pas des constantes métier.
G02–G10 autorisés après correctif CI Ubuntu 24.04 et cinq jobs verts ; arrêt seulement si les
mesures prouvent une incompatibilité ou si une nouvelle décision produit réelle est nécessaire.

### Taille et topologie proposées

| Sujet | Proposition pour le profil étape 7 |
| --- | --- |
| Taille | `system_count = 40` par défaut ; entier configurable de 30 à 50 inclus ; autres tailles refusées explicitement par cette version |
| Routes | Graphe simple non orienté, routes persistées, coût de traversée uniforme d’un saut ; aucune route implicite par proximité |
| Degré | Minimum 2, maximum 4 ; moyenne cible 3, intervalle accepté 2,8–3,2 ; au moins 50 % des systèmes ont 3 ou 4 routes |
| Impasses | Aucune impasse de degré 1 dans ce premier profil ; diversité par cycles, périphéries et détours, sans cul-de-sac initial |
| Connexité | Tous les systèmes appartiennent à une même composante ; aucun isolat, aucune région inaccessible |
| Ponts critiques | Aucune route dont la suppression seule déconnecte le graphe ; les accès défendables sont des passages alternatifs, pas une coupure unique imposée |
| Carrefours | Degrés 3/4 comme ci-dessus, maximum 4 pour la lisibilité ; pas de super-hub |
| Cycles/périphéries | Cycles obligatoires par absence de pont ; périphéries géométriques possibles, sans classe de région, bonus ni frontière territoriale générée |
| Distance | Nombre de sauts uniquement ; diamètre au plus `ceil(system_count / 4)` ; moyenne des plus courts chemins sur toutes les paires au plus 4,5 sauts |

Ces contraintes sont des critères d’acceptation à mesurer en G02, pas une faisabilité déjà prouvée.
Un goulot constitué d’un système d’articulation n’est pas interdit partout par cette proposition ;
un départ ne doit toutefois pas dépendre d’une seule sortie de sa zone initiale (critère ci-dessous).
Aucune relation avec les objectifs de 200 memberships/500 Empires des univers persistants futurs :
ce profil 30–50 systèmes ne prétend pas accueillir ces populations.

### Géométrie et reproductibilité

Positions entières dans un carré normalisé `[0, 1000]²`, séparation euclidienne minimale de
80 unités entre centres. Les routes privilégient des voisins spatiaux, longueur au plus 450 unités
visuelles ; cette longueur ne crée ni coût, ni vitesse, ni unité astronomique gameplay.
Minimiser les croisements avec un ordre de choix stable ; le nombre de croisements est mesuré,
aucune promesse de planarité. Le rendu distingue un croisement d’une jonction.

Le placement et les routes utilisent une suite pseudo-aléatoire spécifiée/versionnée, jamais le
hash Python, l’ordre d’un set, un UUID runtime, une horloge ou une bibliothèque de layout côté client.
L’algorithme précis sera choisi/testé en G02 après validation, en respectant ces critères.
La position approximative DETECTED est un instantané quantifié par cellules de 100 unités,
centre de cellule, indépendant du zoom ; le serveur ne livre jamais la coordonnée exacte derrière.
Les collisions de marqueurs approximatifs seront accessibles via la liste et un regroupement visuel.

Identité complète de génération : seed Universe (chaîne exacte, sans normalisation implicite),
`galaxy_generator_version = galaxy-v1`, tous les paramètres résolus (y compris nombre de sites de
départ), version de données et empreinte du snapshot de données. Sérialisation canonique et ordre
stable des systèmes, routes et planètes ; noms et capacités également déterministes.
Même entrée complète → même sortie canonique, octet pour octet, ou même échec explicite.
La comparaison porte sur les identifiants logiques locaux de génération ; UUID d’instance et dates
SQL de création ne font pas partie du monde canonique reproductible. Les UUID publics demeurent
opaques et propres à chaque Universe ; aucune séquence de génération n’est exposée au joueur.

Jusqu’à 64 tentatives déterministes, dérivées de la même entrée et d’un numéro de tentative.
Valider tout le graphe, les mondes et les départs avant publication atomique ; en cas d’épuisement,
erreur opérateur `generation_constraints_unsatisfied`, aucune galaxie partielle ni relâchement
silencieux des critères. Les tentatives et métriques restent côté opérateur.
Une version inconnue est refusée, jamais remplacée par la plus récente.

### Mondes proposés, portée limitée de Q04

| Paramètre | Proposition initiale |
| --- | --- |
| Planètes par système | 2 à 5 ; tirage pondéré 2/3/4/5 = 20/40/30/10 % |
| Secteurs par monde ordinaire | 9/12/15/18 avec poids 20/35/30/15 % |
| Capacité orbitale | 1/2/3 avec poids 25/50/25 % ; capacité réservée, aucun équipement orbital jouable ajouté |
| Minimum utile | Chaque système a au moins un monde avec ≥12 secteurs et ≥2 orbitaux ; correction déterministe du premier monde si nécessaire |
| Monde de départ | Un monde désigné de 12 secteurs/2 orbitaux par site ; c’est la référence de départ compatible avec l’initialiseur actuel, pas la capacité universelle |
| Traits | Différés : aucun trait, bonus naturel, habitabilité punitive, anomalie ou présence inventé dans cette version |

Les poids décrivent les tirages avant garanties et sélection des zones ; les fréquences finales
seront mesurées, sans prétendre à une indépendance statistique après correction.
« Exploitable » signifie ici capacité physique candidate pour l’expansion future ; aucune
colonisation, économie de planète non colonisée ou habitabilité définitivement décidée.
Q04 reste ouverte pour catalogue, effets des traits, démolition/réaffectation et orbitaux jouables ;
Q07 n’est pas fermée.

### Départs préparant plusieurs Empires

Paramètre `starting_site_count` : **4 par défaut**, 1 à 4 supportés. Un seul site affecté à
l’humain étape 7. Les autres sont des **sites candidats de génération**, pas des réservations
gameplay : aucun Empire/colonie/IA créé, aucune visibilité joueur, aucune interdiction cachée
d’exploration ou de future colonisation. Ils démontrent des positions raisonnablement équitables.
L’affectation multi-Empires est future et n’est pas développée maintenant.

Chaque site a un degré 3 ou 4, un monde de référence 12/2 et au moins 7 systèmes distincts dans
sa boule de rayon 2 (départ inclus). Deux chemins partant du site vers deux systèmes distincts
hors de cette boule doivent avoir des sommets internes disjoints : pas de zone initiale enfermée
par un unique passage. Distance minimale entre sites : 6 sauts ; les boules de rayon 2 ne se
recouvrent donc pas. Aucun parcours d’admission ou de sélection multijoueur dans cette étape.

Équité mesurée sur chaque boule de rayon 2 : nombre de systèmes, nombre de mondes ≥12/2,
somme des capacités sectorielles et somme des capacités orbitales. Pour chacune des quatre
mesures, `maximum / minimum <= 1,20` entre sites, testé en entiers ; minimum strictement positif.
Pas de score opaque agrégeant une mauvaise sortie et une bonne planète ; les quatre critères
sont obligatoires séparément. Un seul site exige les minima locaux mais pas de comparaison.
L’équité militaire/économique à long terme n’est pas garantie par ces métriques initiales.

### Persistance proposée

Génération explicite une fois pour un Universe neuf, sans systèmes/planètes/colonies préexistants ;
rejeu de la même intention retrouve le même manifeste, paramètres contradictoires refusés.
Manifeste immuable : version, seed, paramètres/snapshot/digest et résultat, puis nœuds/routes/mondes
persistés dans la même transaction. Un univers existant n’est jamais régénéré après changement
de code, au GET ou au démarrage ; aucune migration ne peuple automatiquement les anciennes bases.
Une nouvelle version du générateur crée de nouveaux univers seulement.

Plan, audit et critères de test : [étape 7](../05-project/step-7-plan.md).
L’autre arbitrage indispensable est le [contrat Exploration proposé](exploration.md#proposition-exploration-minimale--g01-31102026).

### Robustesse validée comme critère de sortie G02

Profil standard 40 systèmes / 4 sites / galaxy-v1 : **1 000 seeds déterministes fixes minimum,
0 échec**. Bords 30/1, 30/4, 50/1, 50/4 : au moins 100 seeds fixes chacun, succès vérifiés contre
chaque invariant. Ne retirer aucune seed difficile. Mesurer échecs/seeds/taux, temps moyen/p95,
tentatives et contraintes responsables. Le garde-fou 64 tentatives ne remplace pas cette preuve.
Si la robustesse n’est pas atteignable dans un temps raisonnable, arrêter et présenter mesures
et alternatives minimales avant tout assouplissement de degré/équité/distance/ponts/diamètre/zones.
