# Colonie v0.11 — bâtiments par type, emplacements libres, rythme rapide

**Statut : décision utilisateur du 09/11/2026 (principes) ; valeurs chiffrées = proposition
provisoire à valider en recette ; non implémenté.** Les parties existantes restent sur leur ruleset
figé (v0.10) ; seules les nouvelles parties utilisent v0.11.

## Décisions de l’utilisateur (09/11/2026)

- **Modèle « B + emplacements libres »** : les bâtiments clés existent **une fois par colonie** et
  montent en niveau ; quelques **emplacements libres** permettent de spécialiser la colonie.
- **Déblocage guidé** : l’ordre de déblocage est imposé (prérequis), pour qu’un joueur ne puisse pas
  ignorer ce qui mène à l’exploration (Forge orbitale) ou à la recherche (Institut des Échos).
- Les bâtiments inaccessibles restent **visibles et grisés**, avec leur prérequis.
- **Rythme** : une action toutes les **10 à 20 minutes** en début de partie ; beaucoup de niveaux,
  bon marché au départ ; quelques heures par niveau seulement plus tard.
- Écart constaté en recette v0.10 : après deux constructions, 8 h d’attente avant la suivante.

## Modèle proposé

| Catégorie | Types | Nombre | Emplacement |
|---|---|---|---|
| Clés (uniques) | Centre de commandement (existant implicite), Complexe industriel, Centre logistique, **Forge orbitale** (nouveau), **Institut des Échos** (nouveau) | 1 par colonie | Emplacement réservé, n’occupe pas d’emplacement libre |
| Production | Complexe d’extraction, Réacteur de Flux, Nœud de données | 1 de base (réservé) + répétable | La base est réservée ; un exemplaire supplémentaire occupe un **emplacement libre** |

- **Emplacements libres** = taille de la planète (secteurs actuels) − emplacements réservés : une
  petite planète spécialise peu, une grande beaucoup.
- **Plafond de niveau** par planète : `10 + secteurs / 2` (8 secteurs → 14, 12 → 16, 16 → 18).
- **Prérequis guidés** (proposition) : Forge orbitale 1 ← Complexe industriel 2 ; Institut des Échos 1 ←
  Nœud de données 3 ; Centre logistique 1 ← Complexe d’extraction 3 ; construire des vaisseaux exige
  la Forge orbitale (niveau = classes débloquées et vitesse) ; lancer une recherche exige
  l’Institut des Échos (niveau = vitesse et paliers de recherche).

## Courbes proposées (à valider par simulation avant implémentation)

- Durée : `60 s × 1,55^(n−1)` → niveau 5 ≈ 6 min, 7 ≈ 14 min, 10 ≈ 52 min, 12 ≈ 2 h, 15 ≈ 8 h.
- Coût : `base × 1,5^(n−1)` (base extraction 60 Alliages + 15 Flux).
- Production : `base × n × 1,1^(n−1)` (base extraction 30/h → niveau 10 ≈ 700/h).
- File de 3 ordres conservée ; stocks de départ ajustés pour que la première heure enchaîne
  5 à 8 actions. Les valeurs finales sont fixées par un script de simulation (rythme visé : une
  action réalisable toutes les 10–20 min pendant les premières heures).

## Travaux (lot COL-11)

1. Ruleset v0.11 (copie de v0.10 + `colony.json`/`infrastructures.json` nouveaux) et validation.
2. Moteur : plafond de niveau par planète, unicité par type, emplacements réservés vs libres,
   prérequis par niveau ; exigences Forge orbitale (flottes) et Institut des Échos (recherche).
3. IA : politique adaptée (même règles que le joueur).
4. Interface Infrastructures : une ligne par type (niveau 0 visible, grisé si verrouillé, prérequis
   affiché), emplacements libres séparés.
5. Création de partie : v0.11 par défaut ; v0.10 conservée pour les parties existantes.
Noms (10/11/2026, utilisateur : éviter les termes d’OGame) : **Forge orbitale** et **Institut des Échos** ; assets dans [la liste](../visual-reference/assets-a-produire.md).
