# Performance

**Statut : principes validés ; budgets à mesurer.**

Le serveur ne simule pas toutes les planètes chaque seconde. Production à la demande et événements
dus limitent le travail au volume utile. Les événements doivent être indexés par échéance/état ;
les lectures de connaissances par empire. Paginer les collections et éviter les requêtes N+1.
Ces index sont des recommandations futures, pas des migrations de l'étape 0.

## Mesures à introduire

Latence p50/p95 des lectures/mutations, temps de règlement d'un agrégat, retard p95 des événements,
débit de rattrapage, durée d'un tour IA, charge/locks PostgreSQL et taille des projections carte.
Les budgets initiaux Q17/Q29 sont validés ci-dessous comme objectifs à mesurer. Ne pas annoncer
une capacité multijoueur sans benchmark représentatif.

Prototype : 30–50 systèmes, standard futur 100–150 ; ces tailles ne déterminent pas seules la charge.
Le nombre d'empires, de tâches dues et de colonies actives comptera davantage pour le backend.
Tester une reprise avec beaucoup d'échéances simultanées avant de multiplier les workers.

## Frontend

Pas d'assets cinématiques lourds au bootstrap. Évaluer la carte sur un téléphone intermédiaire,
préférer une représentation mesurée aux animations continues, charger les détails à la demande.
Le build actuel est une base, sans budget JS final ni dépendance de cartographie choisie.
Optimiser sur mesures ; ne pas ajouter Redis pour contourner prématurément une requête mal conçue.

Voir [architecture](../03-technical/architecture.md) et [tests](testing-strategy.md).

## Cible future Portal/Game

**Statut : Orientation validée, non implémentée.**

La cible Portal/Game impose des budgets et ressources isolables : surcharge Portal ne doit pas
épuiser pools/CPU/RAM Game ou empêcher les workers. Mesurer l’isolation réelle, pas seulement
la séparation de modules ; aucun benchmark ni garantie DDoS réalisé par cette documentation.

## Budgets initiaux Q17/Q29 — décision du 31/10/2026, non démontrée

Charge : 1 Universe persistent, 200 memberships humaines, 50 GameSessions humaines simultanées,
jusqu’à 500 Empires humains + IA à terme. Valeurs initiales configurables, aucune garantie de capacité.

| Mesure | Objectif initial |
| --- | --- |
| Lecture Game API | p95 < 250 ms |
| Mutation gameplay | p95 < 500 ms |
| Erreurs serveur hors erreurs métier | < 0,1 % |
| Retard worker | p95 < 2 s ; p99 < 5 s |
| Handoff Portal → Game | p95 < 1 s |
| Health/readiness | < 100 ms |

Benchmarks futurs séparant Portal, Game HTTP, workers, PostgreSQL et IA. Consigner matériel,
ruleset, volume/activité, percentiles et erreurs ; aucune suite fonctionnelle ne démontre ces budgets.
