# 0004 — Première persistance et migrations explicites

- Statut : acceptée, choix technique réversible dans le périmètre des étapes 1–2.
- Date : 2026-10-28.

## Contexte

Les concepts Universe/Empire/System/Planet/Colony doivent être persistants avant le moteur temporel.
Une relation entre deux univers ne doit pas être possible même si un service contient une erreur.

## Décision

SQLAlchemy 2 synchrone avec psycopg et Alembic. UUID générés par PostgreSQL, dates timestamptz,
connexions UTC et FK composites pour la contenance. Sessions transactionnelles explicites,
pool borné et récupération par pre-ping. Révisions figées indépendantes des modèles ORM courants.
Migration explicite, pas de create_all ou de migration par worker API.

Une planète n'a qu'une exploitation courante dans ce schéma. Historique et transfert restent Q07 ;
les capacités n'imposent pas les bornes indicatives du game design. Pas d'endpoint métier sans auth.

## Conséquences et alternatives

Contraintes DB et services se complètent. Tests PostgreSQL réels nécessaires : SQLite ne prouve pas
le comportement des UUID, timestamptz et migrations PostgreSQL. L'asynchrone n'est pas introduit sans
besoin mesuré ; il ajouterait une seconde convention aux deux sondes actuelles. Auth, scheduler,
génération galactique et choix d'équilibrage restent hors de ce lot.

[Modèle](../03-technical/data-model.md) · [Backend](../03-technical/backend.md) · [Index ADR](README.md)

## Portée et évolution documentaire

Note de portée : les exclusions et cinq modèles décrivent le lot historique 1–2. Les migrations
0002–0004 ajoutent temps et domaine Colony ; compte/Portal futurs dans [ADR 0008](0008-control-plane-game-data-plane.md).
