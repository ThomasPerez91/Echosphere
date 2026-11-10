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

L’exploitation contestée (attaque d’une opération d’extraction, extracteurs sans escorte
destructibles, défense locale obligatoire) reste à faire : elle étend la résolution des combats
à une cible « opération » et demande ses propres tests de concurrence.

