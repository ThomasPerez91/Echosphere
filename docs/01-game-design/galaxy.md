# Galaxie

**Statut : graphe 2D et seed validés ; tailles orientatives.**


La galaxie est un graphe de systèmes stellaires et routes, pas une grille de coordonnées à la OGame.
Les positions 2D servent la représentation ; les edges définissent les trajets. Des carrefours,
frontières, accès défendables et régions lointaines doivent compter dans les décisions.

Orientation : 30–50 systèmes pour le prototype/MVP, 100–150 pour un univers standard futur.
Génération procédurale reproductible avec seed. La reproductibilité exige aussi une version du
générateur et de ses données ; une seed seule n'est pas une garantie entre versions.

## Génération future

Q06 doit fixer connexité, longueurs, impasses, nombre de planètes, contraintes des départs et critères
d'équité. Vérifier chemins accessibles, absence d'isolats involontaires et répartition des occasions
d'expansion. Ne pas imposer une topologie finale dans l'étape 0.

Le serveur détient la carte complète ; les projections API respectent les connaissances de chaque
empire. Les coordonnées ou identifiants cachés ne doivent pas fuiter dans un payload global.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)
