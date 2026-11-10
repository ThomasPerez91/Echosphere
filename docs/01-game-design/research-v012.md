# Recherche v0.12 — paliers III et IV

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
