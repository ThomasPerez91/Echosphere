# Architecture temporelle et événements

**Statut : modèle validé ; moteur futur.**


Pas de simulation de chaque planète par seconde. Les actions longues sont des tâches avec dates
UTC. PostgreSQL conserve les échéances et leur état ; un redémarrage n'efface pas les travaux.

Types conceptuels : BUILDING_COMPLETE, RESEARCH_COMPLETE, FLEET_ARRIVAL, FLEET_RETURN,
EXPLORATION_COMPLETE, AI_TURN. Ce n'est pas encore un enum publié ni une table.

## Proposition de traitement à valider à l'étape 3

1. Lire un lot borné d'échéances dues, dans l'ordre logique prévu.
2. Réserver les entrées transactionnellement ; verrouiller les agrégats concernés.
3. Régler la production jusqu'à l'instant de l'événement, puis appliquer ses effets et suites.
4. Marquer le résultat dans la même transaction et conserver une clé d'idempotence.
5. En cas de crash avant commit, relire l'événement ; après commit, ne pas doubler l'effet.

Une approche `FOR UPDATE SKIP LOCKED` est envisageable, avec attention aux événements partageant
un agrégat. L'ordre des verrous, l'ordre des échéances simultanées et le traitement des événements
nouvellement créés mais déjà dus sont ouverts en Q13. Une réservation avec commit séparé nécessiterait
un bail récupérable ; ne pas ajouter un état bloqué sans expiration.

## Rattrapage et concurrence

Un événement en retard produit son effet à sa date logique, pas à l'heure du polling : autrement
la production changerait selon les redémarrages. Avant une commande sur une colonie, régler les
effets dus pertinents pour éviter de dépenser un état obsolète. Définir limites et backlog de
rattrapage sans perdre les événements. Le scheduler ne doit jamais dépendre d'un onglet ouvert.

Idempotence signifie effet métier unique malgré les reprises, pas promesse d'exécution réseau
« exactement une fois ». Dead letters, reprises bornées et diagnostic doivent être spécifiés
avant un worker réel. Aucun scheduler, bus ou tâche en mémoire n'est livré à l'étape 0.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
