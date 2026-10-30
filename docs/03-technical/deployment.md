# Exécution locale et déploiement

**Statut : Docker local implémenté ; production future.**


## WSL2

Docker Desktop doit être démarré avec son intégration activée pour la distribution WSL2.
Utiliser Docker Compose v2 récent et cloner dans le filesystem Linux, par exemple `~/projects`.
Les ports 5173 et 8000 doivent être libres. Exécuter les commandes du README à la racine du dépôt.

Compose construit frontend et backend, initialise PostgreSQL 17 dans un volume nommé, attend
sa santé, exécute migrate puis démarre API/worker et enfin frontend. PostgreSQL ne publie aucun port hôte. Backend et frontend publient seulement
sur le loopback ; l'accès Windows se fait via localhost avec l'intégration Docker Desktop.
Pas de Redis. Pas de montage source/live reload entre hôte et conteneur dans cette première version :
reconstruire après modification.

## Migrations après chaque mise à jour du backend

```bash
docker compose up --build -d --wait --wait-timeout 180
docker compose exec backend alembic upgrade head
docker compose exec backend alembic check
```

Compose exécute désormais le service migrate (alembic upgrade head) avant API/worker.
L'API ne migre pas le schéma au démarrage de chaque worker. Relancer upgrade head reste idempotent. `/ready`
prouve la connexion PostgreSQL, pas la version du schéma. Sur la branche 5A, les migrations 0001–0004 aboutissent à 13 tables métier, plus alembic_version,
sans partie créée automatiquement. `upgrade head` peut être relancé sans répéter ses effets. `alembic check` vérifie la
dérive entre ORM et schéma ; ce n'est pas un contrôle d'intégrité des données.
Ne pas exécuter de downgrade sur des données à garder : le downgrade 0004 peuplé est refusé ;
un downgrade vide/base reste destructif pour le schéma.
La CI teste le downgrade uniquement dans une base dédiée jetable.

## Exploitation locale

`docker compose ps -a` : postgres/backend/frontend healthy, worker running et migrate exited (0) attendus.
`docker compose logs --tail=100 backend` : diagnostic API.
`docker compose exec postgres psql -U echosphere -d echosphere -c 'SELECT 1;'` : DB locale
(adapter noms si .env modifié).
`docker compose down` arrête sans supprimer les données. `down -v` détruit le volume : uniquement
pour une réinitialisation volontaire. Modifier le password dans .env ne modifie pas un rôle déjà créé.

`/health` reste 200 si PostgreSQL s'arrête ; `/ready` devient 503, puis retrouve 200 après reprise.
Un statut unhealthy n'entraîne pas automatiquement un redémarrage par Compose. Le worker a une politique restart unless-stopped ;
les autres services utilisent leur politique par défaut. Utiliser `docker compose up -d` pour les relancer.

## Migration 0003 : arrêt coordonné et downgrade

Avant une mise à jour sur une base déjà utilisée, arrêter API/worker anciens, appliquer les migrations,
puis redémarrer les processus avec la même version. Ne pas mélanger workers 0002 et schéma 0003.
En local : docker compose down (sans -v), puis up --build avec le service migrate et le nouveau code.
0003 conserve l'historique et les balances. Son downgrade est en ligne seulement et refuse tout
stream générique sans colonie ou cursor_at différent de settled_at ; ne pas supprimer ces données
pour le forcer. Sauvegarder et tester une restauration avant toute migration sur données à conserver.

## Worker et incidents temporels

Le worker n'expose aucun port. Logs : `docker compose logs --tail=100 worker migrate`.
Il traite une file SQL par lots et récupère les connexions après panne DB ; il ne recalcule pas toutes
les colonies chaque seconde. `docker compose restart worker` ne perd pas les échéances persistées.
Lister les événements bloqués puis relancer explicitement un UUID après correction : commandes dans
[moteur temporel](event-engine.md). Ne pas effacer un événement pour masquer une panne.
La commande --once démarre un consommateur additionnel borné ; elle peut coexister avec le daemon.

## Production future

Construire et servir les assets statiques, reverse proxy TLS, secrets externes, migrations contrôlées,
sauvegardes testées, métriques et procédures de rollback. L'orchestrateur, hébergeur et stratégie de
scalabilité sont ouverts ; ne pas confondre les images de développement et une infrastructure publique.

Sources : [ordre de démarrage Compose](https://docs.docker.com/compose/how-tos/startup-order/),
[prérequis Vite](https://vite.dev/guide/).


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Cible locale future Portal/Game — documentation seulement

**Décision validée, non implémentée** : Windows 11 + Ubuntu WSL2 + VS Code + Docker + Codex local,
ChatGPT Desktop facultatif. Machine partagée permise au développement ; séparation opérationnelle
possible en déploiement. Au checkpoint 5B le Compose gardait cinq services Game ; C01 l’étend
avec les services Portal et HTTPS local, détaillés plus bas.

| Composant futur possible | Plan |
| --- | --- |
| Portal frontend | Landing/compte/lobby |
| Portal backend | Control Plane |
| Accounts PostgreSQL | Stockage de compte, credentials hors Game |
| Game frontend | Jeu après sélection d’univers |
| Game backend | Commandes/lectures de partie |
| Game worker | Production et échéances, indépendant de Portal |
| Game PostgreSQL | État autoritaire des parties |

Noms de services, routage/TLS, placement, pools et budgets futurs à spécifier ; pas des services
lancés aujourd’hui. CPU/RAM/scaling/bases/réseau doivent être isolables pour limiter l’impact des
attaques Portal. Voir [ADR 0008](../adr/0008-control-plane-game-data-plane.md). Aucune recette WSL2
réelle n’est revendiquée ici ; [reprise concrète](../06-handoff/work-codex-handoff.md).

## Socle Portal C01 — sur PR #7

Accounts DB et API/frontend Portal séparés, Alembic p0000 propre, origines HTTPS locales via Caddy.
Les services et le volume Game sont conservés. Le lancement Compose inclut désormais ces services,
sans compte, session ou API gameplay. Les descriptions précédentes des cinq services décrivent
le socle Game ; la [recette Portal](portal-foundation.md) détaille certificats, commandes et limites.

## Extension C02 — développement local seulement

[Comptes/vérification et livraison](portal-registration.md) ajoutent portal-secrets-init,
portal-mail-worker et Mailpit (UI loopback 8025, SMTP réseau interne non publié), volumes portal_secrets
et portal_mail_data. Ne pas perdre la clé des emails en attente ; aucune clé en Git.
Migration Accounts p0001 additive ; aucun changement Game. Aucun fournisseur de production choisi.

## Extension C03 sur PR #7

[Sessions Portal/CSRF](portal-sessions.md) : migration Accounts additive p0002, cinq tables
profils/appareils/sessions/challenges/intentions de logout. Aucun schéma Game modifié. Les intentions
de déconnexion sont persistées mais leur livraison/acquittement distant reste à C06/C07.

## Extension C04 sur PR #7

[Opérations sensibles sans MFA](portal-account-security.md) : step-up par action cinq minutes/unique,
reset trente minutes, double confirmation email une heure et logout global. Migration Accounts p0003
additive, notifications chiffrées et intentions de révocation Game pending. MFA/privilèges refusés
sans preuves futures C05 ; aucune livraison Game ou API Colony ajoutée.
