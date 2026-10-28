# Infrastructures

**Statut : catalogue économique v0.1 implémenté en domaine interne ; extensions futures.**


Chaque secteur accueille une infrastructure. Les infrastructures économiques principales ont une
progression continue : les niveaux 1–5 sont seulement l’early game de référence, sans plafond 5.
Cette décision remplace l’ancienne orientation I–V (2026-10-28). Limites : règles/prérequis et
représentation numérique. Catalogue chargé depuis game_data, aucune croissance codée en service.

| Surface, exemples | Orbite, exemples |
| --- | --- |
| Complexe d'extraction, Réacteur de Flux | Chantier orbital |
| Complexe industriel, Institut scientifique | Réseau de capteurs |
| Centre logistique, Réseau défensif | Station commerciale |
| Infrastructure administrative | Plateforme défensive |

La station commerciale est un exemple futur lié au commerce post-MVP, pas une obligation de l'étape 5.
Le catalogue économique de 5A et ses valeurs provisoires sont définis dans
[Économie v0.1](colony-economy-v0.1.md). Catalogue étendu et prérequis futurs restent Q04. Aucune formule de production n'est déduite
du nom d'un bâtiment.

## Cycle d'action futur

Le service vérifie possession, secteur disponible, prérequis et ressources avant de créer une tâche.
Une amélioration termine à une échéance serveur. La v0.1 fixe trois ordres, un actif, réservation immédiate et remboursements 100/80 %.
Réaffectation et démolition restent Q01/Q04. Voir les règles précises de cascade et saturation de
remboursement (Q39) dans la référence v0.1. Un client ne peut pas confirmer sa propre fin
de chantier. L'infrastructure achevée modifie les taux après règlement de la période précédente.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

La [défense future](planetary-defense.md) sera une infrastructure persistante configurable, pas
un empilement de canons. Aucune infrastructure défensive ou orbitale construisible à l’étape 5A.
