# 0005 — Chronologie persistante par colonie et calcul exact

- Statut : acceptée comme décision technique de l'étape 3, sans arbitrage des paramètres métier.
- Date : 2026-10-28.

## Contexte

Le rattrapage hors connexion, les changements de taux et plusieurs workers ne doivent pas modifier
les résultats. Une file verrouillée par événement seul pourrait exécuter deux échéances de la même
colonie dans le désordre ; un arrondi jeté à chaque lecture créerait une perte liée à la fréquence.

## Décision

Verrou PostgreSQL d'une timeline par colonie ; ordre due_at puis séquence allouée sous verrou.
Réservation SKIP LOCKED de timelines, pas d'événements indépendants du même agrégat. Une transaction
par événement, SAVEPOINT pour annuler intégralement un handler défaillant et préserver retries bornés.
Tête blocked/backoff bloquante pour sa colonie, autres colonies indépendantes. Aucune réservation
avec commit séparé ni file mémoire comme autorité.

Calcul en micro-unités entières, taux horaires et reste exact persisté. Règlement aux dates logiques,
horloge injectable et rattrapage borné qui ne saute jamais une échéance due. Le même monolithe fournit
API et worker ; un service migrate séparé exécute Alembic avant les deux processus dans Compose.

## Conséquences et limites

Les commandes futures doivent prendre ce verrou et vérifier la complétude du rattrapage. Les handlers
sont serveur, transactionnels et sans effets externes. Pas de promesse de livraison réseau exactement
une fois. Aucun rendement, coût, taille de stockage ou ressource initiale n'est arrêté ici.
Ordre multi-agrégats, transferts, flotte et combat nécessiteront une conception complémentaire Q13.
Le choix technique d'un plafond optionnel saturant ne fixe pas les valeurs économiques Q03.

[Contrat temporel](../03-technical/event-engine.md) · [Calcul](../03-technical/resource-calculation.md)
