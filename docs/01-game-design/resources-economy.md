# Ressources et économie

**Statut : trois ressources validées ; paramètres ouverts.**


| Nom de travail | Usages envisagés |
| --- | --- |
| Alliages | Structures, coques et infrastructures |
| Flux | Énergie, propulsion et technologies énergétiques |
| Données | Recherche, électronique, capteurs et technologies avancées |

Seulement ces trois ressources principales au MVP. Leurs noms restent provisoires. Les ressources
rares sont futures. Pas de nourriture ni de biens de consommation issus des mockups.

## Principes

Production passive calculée avec le temps écoulé. Les coûts, capacités de stockage, taux,
consommations et éventuels coûts d'entretien restent en Q03. Ne pas supposer que Flux désigne
une jauge de puissance instantanée : c'est ici une ressource principale, son modèle exact est ouvert.
Les actions vérifient les fonds côté serveur et appliquent leur dépense transactionnellement.
Un rafraîchissement du navigateur ne crée jamais de ressources.

## Paramétrage futur

Conserver les valeurs dans `game_data/`, validées et versionnées. Simuler les goulots de départ,
le retour sur investissement et les possibilités de rattrapage avant de fixer les coefficients.
Les détails d'intégration, d'arrondi et de changement de taux sont décrits dans le calcul technique.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)
