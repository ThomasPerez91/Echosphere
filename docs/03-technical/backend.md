# Backend

**Statut : bootstrap implémenté.**


Python 3.12, FastAPI et psycopg. L'application ne possède ni tables métier ni migrations.
`app/main.py` contient les sondes ; les tests remplacent la fonction d'accès DB pour vérifier les
contrats sans dépendance externe. Un contrôle réel PostgreSQL est prévu dans le smoke Compose CI.

## Choix minimal

Une connexion courte par `/ready`, fermée à la sortie du contexte, suffit au bootstrap. Le handler
synchrone est exécuté par FastAPI dans son pool de threads. Ne pas conserver une connexion cassée
entre probes. Évaluer pool, SQLAlchemy et Alembic à l'étape 1/2 avant le trafic métier.

## Structure future

Les routes délèguent aux services d'application. Ceux-ci valident les commandes et coordonnent
transaction, règles pures et persistance. Humains et IA passent par le même chemin. Ne pas construire
une hiérarchie générique de repositories pour les deux sondes actuelles.

Les variables POSTGRES_* sont lues côté serveur ; psycopg reçoit des arguments nommés afin que les
caractères réservés d'un mot de passe ne cassent pas une URI. Configuration UTC et aucune fuite de
credentials dans une réponse HTTP. Ruff et pytest font partie des checks obligatoires.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
