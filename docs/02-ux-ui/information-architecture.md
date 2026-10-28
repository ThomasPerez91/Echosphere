# Architecture de l’information

**Statut : responsive validé ; détails UI orientatifs.**


Le produit possède deux présentations, desktop et mobile, fondées sur les mêmes objets et actions.
Les sections cibles sont Empire, Colonie, Recherche, Galaxie, Flottes, Rapports et Relations.
L’étape 4 propose cet ordre provisoire : Empire, Colonie, Recherche, Galaxie, Flottes, Rapports,
Relations. Q15 reste ouverte pour la validation produit et la future carte tactile.

## Priorités

Le bilan résume production, échéances et décisions urgentes. Une colonie permet de voir secteurs,
infrastructures et files. La galaxie aide à décider où explorer ou s'étendre. Les flottes présentent
missions et arrivées ; les rapports conservent les résultats utiles à une connexion différée.
Chaque écran détaille l'information au moment où une décision l'exige.

## Traversées principales

Alerte → objet concerné → décision → confirmation et prochaine échéance.
Colonie → infrastructure → coût et durée → ordre serveur → file actualisée.
Galaxie → système connu → comparaison → mission. Ce sont des parcours cibles, pas des routes
de gameplay implémentés. Le shell propose maintenant ces sept destinations par fragments URL ;
seul Empire présente le bilan technique, les autres sections expliquent leur état de préparation.
Mobile : quatre destinations principales et Plus pour Flottes/Rapports/Relations ; sélection
indiquée par aria-current, historique natif et focus sur le titre après un changement de destination.


## Références

- [Index](../README.md) · [Questions ouvertes](../05-project/open-questions.md)

## Sous-navigation Colony — Étape 5A

Colony réserve Vue d’ensemble / Infrastructures / Orbite / Défense, par fragments
#colony/overview, #colony/infrastructure, #colony/orbit et #colony/defense. #colony garde la vue
d’ensemble. Le focus suit h1 au changement de sous-section, liens directs et historique natif.
La sélection globale reste Colonie. Pas de huitième destination principale Defense.
Aucun univers / aucune colonie active est explicite ; aucune fixture runtime, stock, bâtiment ou
minuterie fictifs. Défense indique un système futur sans bouton de construction. Q15 reste ouverte.

## Portal puis Game — décision validée, écrans futurs

Landing publique → inscription/connexion → espace compte/lobby → liste des parties → créer/rejoindre
→ sélectionner Universe → Game UI. Un même compte peut revenir à sa liste et choisir une autre partie.
Le parcours ne suppose pas un empire unique global ; choix des rôles/empire partagé restent Q21/Q51.
Les sessions Game autonomes et handoff relèvent de [ADR 0008](../adr/0008-control-plane-game-data-plane.md).
Pas de nouveau menu implémenté ici : sept domaines Game conservés, Défense reste dans Colony.
Les UX de login, ticket expiré, logout et panne Portal attendent Q40–Q56, sans fausse route cliquable.
