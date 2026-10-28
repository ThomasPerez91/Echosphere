# Architecture technique

**Statut : monolithe modulaire validé.**


Frontend React/TypeScript/Vite ; backend Python/FastAPI ; PostgreSQL source de vérité.
SQLAlchemy et Alembic seront introduits lors des modèles/migrations, pas artificiellement au bootstrap.
Redis est facultatif plus tard ; aucun besoin actuel. Pas de microservices.

## Frontières futures

Modules envisagés : univers, empires/colonies, économie/construction, recherche, exploration,
flottes/combat, connaissance/rapports, relations et IA. Ils composent un même backend, avec une base
transactionnelle commune. Les noms de packages finaux ne sont pas une décision acquise.
Les services d'application orchestrent les commandes ; les règles de domaine ne dépendent pas du web.
Les adaptateurs HTTP et IA utilisent les mêmes services et validations.

## État livré

`backend/app/main.py` : sondes uniquement via psycopg, sans table ni migration.
`frontend/src/` : placeholder et requête de disponibilité. `game_data/` : intention documentée,
aucun paramètre de jeu. Docker lance trois services locaux. Le proxy Vite relaie `/api/*` vers le
backend ; le navigateur ne résout jamais le hostname Docker `backend`.

## Évolution contrôlée

Un worker temporel futur pourra être un processus distinct du même codebase ; cela ne crée pas un
microservice. Extraire un composant seulement sur besoin mesuré et ADR. Les interactions métier,
UTC, transactions et visibilité sont décrites dans les documents spécialisés.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
