# Performance

**Statut : principes validés ; budgets à mesurer.**

Le serveur ne simule pas toutes les planètes chaque seconde. Production à la demande et événements
dus limitent le travail au volume utile. Les événements doivent être indexés par échéance/état ;
les lectures de connaissances par empire. Paginer les collections et éviter les requêtes N+1.
Ces index sont des recommandations futures, pas des migrations de l'étape 0.

## Mesures à introduire

Latence p50/p95 des lectures/mutations, temps de règlement d'un agrégat, retard p95 des événements,
débit de rattrapage, durée d'un tour IA, charge/locks PostgreSQL et taille des projections carte.
Les seuils et la charge de référence restent ouverts en Q17. Ne pas annoncer une capacité multi-joueur
sans benchmark représentatif.

Prototype : 30–50 systèmes, standard futur 100–150 ; ces tailles ne déterminent pas seules la charge.
Le nombre d'empires, de tâches dues et de colonies actives comptera davantage pour le backend.
Tester une reprise avec beaucoup d'échéances simultanées avant de multiplier les workers.

## Frontend

Pas d'assets cinématiques lourds au bootstrap. Évaluer la carte sur un téléphone intermédiaire,
préférer une représentation mesurée aux animations continues, charger les détails à la demande.
Le build actuel est une base, sans budget JS final ni dépendance de cartographie choisie.
Optimiser sur mesures ; ne pas ajouter Redis pour contourner prématurément une requête mal conçue.

Voir [architecture](../03-technical/architecture.md) et [tests](testing-strategy.md).
