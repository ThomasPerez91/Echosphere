# Moteur temporel persistant

**Statut : socle de l'étape 3 implémenté pour une colonie ; autres agrégats futurs.**

Pas de simulation de chaque planète chaque seconde. Production à la demande et échéances persistées
dans PostgreSQL ; le worker ne fait que consulter la file des événements, même sans navigateur connecté.
Le même code de monolithe est utilisé par l'API et le processus worker. Aucun Redis ou WebSocket.

## Contrat livré

`app/simulation/` contient horloge, calcul pur, modèles et services. Chaque colonie initialisée possède
une ligne `colony_timelines` servant de verrou, trois `resource_balances` et sa file `scheduled_events`.
L'initialisation exige les trois stocks/taux explicitement fournis par le futur service métier ; elle
n'offre aucune ressource par défaut. La migration ne peuple aucune donnée.

`schedule` est une primitive interne, pas une commande joueur : transaction explicite, verrou de la
colonie, clé idempotente et contenu JSON figé. Même clé + même type/date/payload renvoie l'événement
existant, même terminé ; même clé avec autre contenu produit IdempotencyConflict. Un événement ne
peut précéder `settled_at`. Les futurs services joueurs devront rattraper à l'instant de commande
avant de planifier une nouvelle action ; cette primitive n'autorise pas un client à antidater ses ordres.

## Ordre et concurrence (partie technique de Q13)

Ordre strict par colonie : `due_at`, puis séquence monotone allouée sous verrou. Un événement créé
par un handler au même instant logique reçoit une séquence supérieure ; sa création participe à la
même transaction. Aucune garantie d'ordre global entre colonies : interactions multi-agrégats,
verrous des flottes/combat et priorités de gameplay simultanées restent Q13.

Le worker sélectionne la tête de chaque file via une requête LATERAL, puis réserve une ligne timeline
avec `FOR UPDATE OF colony_timelines SKIP LOCKED`. Il relit la tête après verrouillage sous READ COMMITTED.
Deux workers ne traitent jamais deux échéances de la même colonie en parallèle ; un autre agrégat
peut avancer. Une tête bloquée ou en backoff ne laisse pas passer ses successeurs.

## Atomicité et reprise

Dans une transaction par événement : compter la tentative, ouvrir un SAVEPOINT, régler les ressources
jusqu'à **due_at**, appeler le handler, enregistrer completed et les éventuels événements suivants.
Le timestamp completed_at décrit le traitement effectif ; il ne remplace pas la date logique.
Un crash avant commit annule l'ensemble ; après commit, l'événement completed n'est plus éligible.
Pas de réservation persistée séparément, donc aucun bail à expirer après crash.

Si un handler lève une Exception, le SAVEPOINT annule aussi production, changements et enfants.
La transaction conserve seulement le diagnostic borné : attempts, next_attempt_at et code générique
`handler_failed` ou `unknown_event`, jamais texte d'exception/payload dans les logs. Après trois
échecs par défaut (réessais espacés de 30 s), état blocked et intervention explicite après correction.
Une perte de connexion empêchant le commit annule aussi ces compteurs ; le worker récupère son accès
PostgreSQL et relit les données persistantes. BaseException modélise une interruption de processus
qui ne doit pas être transformée en échec métier committé.

## Rattrapage autoritaire

`catch_up(session, colony_id, until, limit=100)` prend le même verrou et traite les échéances dues,
puis règle la production jusqu'à until. Horloge injectée, pas de projection dans le futur ou en arrière.
Si la limite est atteinte ou si une tête échoue/attend un retry, `complete=False` : la colonie n'est
jamais projetée au-delà d'un événement dû non appliqué. Le futur service de dépense doit refuser de
continuer sur ce résultat et reprendre le rattrapage ; aucun service de dépense n'est encore livré.
La transaction appartient à l'appelant, qui peut conserver les progrès ou tout annuler sur refus.

## Handlers et périmètre

Seul `RESOURCE_RATE_CHANGE` est livré, avec resource alloys/flux/data et entier non négatif
rate_per_hour en micro-unités. Il change le taux après règlement de l'ancien intervalle. Coûts,
bâtiments, recherches, flottes et AI_TURN n'ont pas de handler fictif ; un type inconnu est bloqué
après retries, pas marqué réussi. Les handlers restent du code serveur de confiance : pas de commit,
d'appel externe ou de verrou d'une autre colonie. Aucun endpoint temporel public n'est exposé.

## Exécution et récupération

Compose : PostgreSQL → migrate (terminé avec succès) → API/worker → frontend. Le worker traite des
lots de 50 et attend une seconde entre lots ; c'est un polling de file, pas un tick de production.
`--limit`, `--poll-interval`, `--max-attempts`, `--retry-delay` sont bornés et configurables en CLI.
Les choix 50/1s/3/30s sont techniques, ne changent pas les durées des futures actions de jeu.
Le worker a une politique restart unless-stopped ; aucune sonde HTTP de progression n'est revendiquée.

```bash
docker compose exec worker python -m app.simulation.worker --once --limit 50
docker compose exec worker python -m app.simulation.worker --blocked --limit 50
# Seulement après avoir corrigé le handler ou la cause, pour l'UUID listé :
docker compose exec worker python -m app.simulation.worker --retry UUID_DU_EVENT
```

La relance explicite remet le compteur de tentative à zéro, conserve identité/date/payload et n'efface
pas les événements. Une purge/archivage de l'historique et les changements de version restent futurs.

[Calcul des ressources](resource-calculation.md) · [Déploiement](deployment.md) · [ADR 0005](../adr/0005-colony-time-engine.md)
