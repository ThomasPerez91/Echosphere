# Backend

**Statut : fondation des étapes 1–2 implémentée ; gameplay futur.**

Python 3.12, FastAPI, SQLAlchemy 2, psycopg, Alembic et pydantic-settings. `create_app(settings)`
compose les adaptateurs. `app/api/probes.py` garde les contrats /health et /ready. `app/core/config.py`
valide les variables POSTGRES_* et les délais ; un port invalide arrête la configuration au démarrage.
Le mot de passe est un SecretStr et la construction d'URL SQLAlchemy conserve les caractères réservés.
Aucun .env n'est chargé implicitement par Settings : Compose injecte les valeurs ; en natif, les exporter.

## Connexions et transactions

`persistence/database.py` crée le pool, limité à cinq connexions sans débordement, avec pré-ping,
délai d'attente du pool et connect/statement timeouts. Ces limites sont des choix techniques de départ,
pas une capacité de charge promise. Les connexions PostgreSQL ont timezone=UTC. Le lifespan libère
le pool à l'arrêt. Les handlers synchrones utilisent le pool de threads FastAPI.

`create_session_factory(engine)` donne des sessions dont les services futurs posséderont la transaction :
`with factory.begin() as session`. Commit seulement si toutes les validations et écritures réussissent,
rollback sur exception. Une future commande humaine ou IA traversera le même service applicatif.
Pas de repository générique ou de bus de commande vide introduit à l'avance.

## Persistance

Cinq modèles : Universe, Empire, StellarSystem, Planet et Colony. Première migration explicite,
indépendante des classes ORM courantes. Pas de `create_all` au démarrage ni de migration concurrente
par worker API. Les migrations sont une action séparée et vérifiable (voir déploiement).
Les migrations ne peuplent aucune donnée de galaxie, de ressource, de bâtiment ou d'utilisateur.

## Contrats et sécurité (Q16 cadrée, toujours ouverte)

Les deux sondes conservent leurs réponses. Aucun endpoint de création/liste d'empires n'est exposé
en attendant une identité authentifiée et un contrôle d'accès objet. Le type human/ai décrit un
contrôleur d'empire, il n'authentifie personne. Identité/session, enveloppe d'erreur métier et contrat
d'idempotence seront arbitrés avant la première mutation HTTP. Aucune JWT factice ni clé de dev ne
contourne ces décisions.

## Temps de colonie

Le module simulation apporte une horloge injectable, des calculs purs et un processeur PostgreSQL.
Le service migrate de Compose exécute Alembic avant API/worker. Une migration par processus API reste
interdite. Voir [contrat temporel](event-engine.md) avant toute commande qui touche un stock.
Les mutations HTTP et l'auth restent hors de ce lot ; le changement de taux est un handler interne,
pas un endpoint permettant au joueur de choisir son rendement.

## Validation

Unitaires : sondes, configuration, masquage des secrets. Intégration PostgreSQL dédiée : migrations
upgrade/downgrade/upgrade et absence de dérive, liens cohérents entre univers, occupation unique,
capacités valides, timestamps UTC et rollback complet. CI exécute les intégrations ; aucun SQLite
ne remplace les garanties PostgreSQL. Les bases de tests doivent se terminer par `_test`.

[Architecture](architecture.md) · [Modèle](data-model.md) · [API](api.md) · [Déploiement](deployment.md)
