# Ruleset v0.12 — paliers de recherche III et IV, score de relation, dossiers

**Statut : implémenté sur la branche de recette le 10/11/2026 à la demande de l’utilisateur
(« plus de technologies ») ; valeurs d’équilibrage provisoires, à valider en recette.** Les
rulesets restent figés par univers : seules les nouvelles parties (création Portal en v0.12) ont
ces paliers ; les parties v0.11 et antérieures sont inchangées.

## Contenu

Chaque domaine passe de deux à quatre paliers (16 technologies). Le palier III renforce l’effet
du domaine et remplace le palier II (effet maximal par type, comme aujourd’hui). Le palier IV
ouvre un **nouvel effet** et demande aussi le palier II d’un domaine voisin, pour croiser les
arbres.

| Domaine | III | IV (nouvel effet) | Prérequis du IV |
|---|---|---|---|
| Ingénierie | Fabrication modulaire III : −15 % Alliages des constructions | Assemblage orbital : −15 % coût des vaisseaux | Ingénierie III + Énergie II |
| Énergie | Gestion énergétique III : −15 % Flux des constructions | Chaînes de propulsion : −20 % durée de fabrication des vaisseaux | Énergie III + Ingénierie II |
| Calcul | Calcul scientifique III : −15 % durée des recherches | Planification prédictive : −15 % durée de base des constructions | Calcul III + Xénoscience II |
| Xénoscience | Protocoles d’analyse III : −15 % Données des recherches | Résonance des échos : −25 % Données des recherches | Xénoscience III + Calcul II |

Coûts : palier III 600/480/1 200 (Alliages/Flux/Données), 20 min ; palier IV 1 800/1 440/3 600,
1 h. Centre de recherche requis : niveau 5 pour le III, 8 pour le IV (1 et 3 inchangés).

## Règles

- Un effet s’applique aux **nouveaux ordres** seulement et il est figé dans leur instantané, comme
  les effets existants : une commande de vaisseaux acceptée garde son prix, sa durée et sa
  livraison unité par unité même si les technologies changent ensuite.
- Les effets sur les vaisseaux valent pour toutes les classes et pour l’IA (mêmes services).
- Fichiers : `game_data/rulesets/v0.12` générés par `scripts/rulesets/make_v012.py` depuis v0.11.

## Relations : score et évaluation (même ruleset)

Le score de relation (−100 à +100) est une **lecture** des faits datés que le serveur connaît
déjà ; il n’est ni stocké ni utilisé par une règle (pacte, combat et IA ne le lisent pas).

| Fait | Points (provisoires) |
|---|---|
| Pacte en vigueur | +40, plus +2 par jour d’ancienneté (au plus +20) |
| Rupture notifiée | −30 |
| Proposition de pacte reçue | +10 |
| Hostilité subie | −50 si elle date de moins de 7 jours, −20 de moins de 30 jours |
| Hostilité de votre part | −15 si elle date de moins de 7 jours |

Libellés : Hostile (≤ −50), Méfiant (≤ −15), Neutre (≤ 14), Cordial (≤ 49), Allié au-delà.
L’**évaluation** montre seulement les dernières forces militaires de l’autre Empire observées dans
un de vos rapports de combat (survivants, puissance et coque d’après les règles), avec leur date ;
sans combat, les forces restent inconnues. Les accords de recherche et commerciaux restent à
concevoir (mécanique d’échange à décider).

## Dossiers de découverte complets (A4, EXP-02c — même ruleset)

L’étude qui complète un dossier (tous ses indices étudiés par l’Empire) charge en soute la
récompense du dossier (2 000 Données, provisoire) et **révèle** (DETECTED, sans nom ni structure)
les systèmes portant une opportunité remarquable à 3 routes au plus des indices. Le plan d’étude
vérifie que la soute peut porter les Données de la curiosité **et** la récompense : une étude ne
perd jamais une partie de son résultat. Le rapport de mission donne la récompense et les systèmes
révélés ; la vue Rapports le classe en Recherche.

## Exploitation contestée (A1, D5 amendée — même ruleset)

- Une **ATTACK peut viser un gisement** connu de l’Empire (prospecté), avec les mêmes règles de
  trajet, de carburant aller-retour et de préavis qu’une attaque de planète.
- Le **défenseur est lié au lancement**, sous le verrou du gisement : l’Empire étranger qui y a le
  plus d’extracteurs au travail à cet instant (égalité : plus petit identifiant). Rien n’en est
  dit à l’attaquant ; si personne n’exploite le gisement, la cible est vide à la bataille.
- À la bataille, défendent les vaisseaux militaires **stationnés** du défenseur dans le système
  et les **escortes** de ses extractions en cours sur ce gisement. Si le défenseur n’a plus de
  vaisseau militaire (victoire de l’attaquant ou aucune défense), ses opérations d’extraction sont
  **détruites** : la revendication se clôt à la bataille, la soute est perdue, la flotte disparaît
  et son propriétaire reçoit un rapport « Exploitation détruite ». Une extraction qui a gagné
  continue et se termine normalement (ses escortes perdues sont comptées dans la vérification).
- Un pacte couvrant la bataille l’annule, comme pour une planète. La bataille est un acte hostile
  daté et crée les contacts, comme les autres combats.

## Présences étrangères et classes sur la carte (11/11/2026)

Validé par l’utilisateur le 11/11 (« vasi fait ») : la carte montre les colonies étrangères que
l’Empire connaît légitimement et classe leur Empire.

- **Sources**, les mêmes que les contacts : une colonie étrangère aujourd’hui dans un système
  surveillé par une colonie propre (datée de la lecture), et le monde visé par une attaque propre
  dont le rapport nomme le défenseur (daté de la bataille). Aucun capteur distant, aucune
  occupation devinée ; un défenseur apprend l’attaquant, pas où sont ses colonies.
- **Classe** (`relations.map.hostile_days` = 7) : pacte en vigueur → **Allié** ; sinon score
  Hostile ou fait hostile (d’un côté ou de l’autre) depuis moins de 7 jours → **Hostile** ; sinon
  score Cordial ou Allié → **Allié** ; sinon **Neutre**. Sans contact : **Inconnu**. C’est une
  lecture des mêmes faits datés que le score, jamais un nouvel état de jeu.
- **Portée** : ruleset v0.12 avec `relations.map` (nouvelles parties) et droit `relations.read`
  (la source combat demande aussi `combat.read`). Projection Galaxie `foreign`, sans migration.
- **Carte** : anneau vert (allié), ambre (neutre), rouge (hostile) ou gris (inconnu) ; filtres
  Alliés / Neutres / Hostiles actifs ; légende, infobulle, fiche rapide et vue système affichent
  l’Empire et sa relation.
