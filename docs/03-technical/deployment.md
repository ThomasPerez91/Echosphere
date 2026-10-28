# Exécution locale et déploiement

**Statut : Docker local implémenté ; production future.**


## WSL2

Docker Desktop doit être démarré avec son intégration activée pour la distribution WSL2.
Utiliser Docker Compose v2 récent et cloner dans le filesystem Linux, par exemple `~/projects`.
Les ports 5173 et 8000 doivent être libres. Exécuter les commandes du README à la racine du dépôt.

Compose construit frontend et backend, initialise PostgreSQL 17 dans un volume nommé et attend
les healthchecks. PostgreSQL ne publie aucun port hôte. Backend et frontend publient seulement
sur le loopback ; l'accès Windows se fait via localhost avec l'intégration Docker Desktop.
Pas de Redis. Pas de montage source/live reload entre hôte et conteneur dans cette première version :
reconstruire après modification.

## Migrations après chaque mise à jour du backend

```bash
docker compose up --build -d --wait --wait-timeout 180
docker compose exec backend alembic upgrade head
docker compose exec backend alembic check
```

La première commande lance les services ; l'API ne modifie pas le schéma au démarrage. `/ready`
prouve la connexion PostgreSQL, pas la version du schéma. La migration 0001 crée les cinq tables,
sans données. `upgrade head` peut être relancé sans répéter ses effets. `alembic check` vérifie la
dérive entre ORM et schéma ; ce n'est pas un contrôle d'intégrité des données.
Ne pas exécuter de downgrade sur des données à garder : un downgrade base supprime ces tables.
La CI teste le downgrade uniquement dans une base dédiée jetable.

## Exploitation locale

`docker compose ps` : trois services healthy attendus.
`docker compose logs --tail=100 backend` : diagnostic API.
`docker compose exec postgres psql -U echosphere -d echosphere -c 'SELECT 1;'` : DB locale
(adapter noms si .env modifié).
`docker compose down` arrête sans supprimer les données. `down -v` détruit le volume : uniquement
pour une réinitialisation volontaire. Modifier le password dans .env ne modifie pas un rôle déjà créé.

`/health` reste 200 si PostgreSQL s'arrête ; `/ready` devient 503, puis retrouve 200 après reprise.
Un statut unhealthy n'entraîne pas automatiquement un redémarrage par Compose. Les services
n'ont pas de politique de redémarrage automatique à cette étape ; utiliser `docker compose up -d`.

## Production future

Construire et servir les assets statiques, reverse proxy TLS, secrets externes, migrations contrôlées,
sauvegardes testées, métriques et procédures de rollback. L'orchestrateur, hébergeur et stratégie de
scalabilité sont ouverts ; ne pas confondre les images de développement et une infrastructure publique.

Sources : [ordre de démarrage Compose](https://docs.docker.com/compose/how-tos/startup-order/),
[prérequis Vite](https://vite.dev/guide/).


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
