# Architecture de l’information

**Statut : responsive validé ; détails UI orientatifs.**


Le produit possède deux présentations, desktop et mobile, fondées sur les mêmes objets et actions.
Les sections cibles sont Empire, Colonie, Recherche, Galaxie, Flottes, Rapports et Relations.
Leur ordre final, libellés et regroupements seront validés à l'étape 4 (Q15).

## Priorités

Le bilan résume production, échéances et décisions urgentes. Une colonie permet de voir secteurs,
infrastructures et files. La galaxie aide à décider où explorer ou s'étendre. Les flottes présentent
missions et arrivées ; les rapports conservent les résultats utiles à une connexion différée.
Chaque écran détaille l'information au moment où une décision l'exige.

## Traversées principales

Alerte → objet concerné → décision → confirmation et prochaine échéance.
Colonie → infrastructure → coût et durée → ordre serveur → file actualisée.
Galaxie → système connu → comparaison → mission. Ce sont des parcours cibles, pas des routes
frontend déjà implémentées. Le bootstrap n'a qu'une page sans navigation de gameplay.


## Références

- [Index](../README.md) · [Questions ouvertes](../05-project/open-questions.md)
