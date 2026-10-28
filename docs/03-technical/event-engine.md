# Scheduler générique et règlement économique

**Statut : étape 3 corrigée sur PR #3 ; scheduler extensible, économie de colonie comme premier adaptateur.**

## Deux responsabilités explicites

EventStream(universe_id, cursor_at, next_sequence) → ScheduledEvent(stream_id, universe_id).
Le module scheduler.py ne référence ni Colony ni ResourceBalance. Un stream est un scope d'ordre,
de verrouillage et d'idempotence appartenant à une instance Universe ; ce n'est pas un pointeur
owner_kind/owner_id sans intégrité référentielle.

ColonyTimeline(colony_id, universe_id, stream_id unique, settled_at) → ResourceBalance.
Ses FK composites garantissent que colonie et stream sont dans le même univers. service.py est
l'adaptateur économique : le handler RESOURCE_RATE_CHANGE règle les ressources jusqu'à due_at avant
le changement de taux ; catch_up termine le règlement économique jusqu'à la cible si complete=True.
Un événement non économique peut avancer cursor_at sans modifier settled_at : aucun calcul de
production n'est imposé au scheduler générique. Un future adaptateur pourra faire de même pour un
empire, une flotte ou un univers, sans implémenter ces domaines actuellement.

## Planifier et contrôler le scope

Les fonctions génériques create_stream/lock_stream/schedule/catch_up_stream utilisent universe_id
explicitement. Un stream absent ou d'un autre univers donne la même erreur de scope ; les FK
composites interdisent aussi les événements incohérents même si un service omet une validation.
Les helpers internes de colonie infèrent leur scope depuis le lien DB ; ils ne sont pas des endpoints
authentifiés et ne remplacent pas Membership/permissions d'une future API.

Une clé idempotente est unique par stream : même clé/type/date/payload renvoie l'événement existant,
y compris terminé ; un contenu différent produit IdempotencyConflict. Les payloads sont copiés JSON
et les timestamps UTC. Planifier avant cursor_at est refusé. Les futurs services joueurs devront
rattraper le scope à l'instant de commande avant de planifier leur action, sans antidater depuis le client.

## Ordre et concurrence

Ordre déterministe par stream : due_at puis séquence allouée sous verrou. Les événements enfants
créés au même instant logique reçoivent une séquence supérieure. Aucun ordre global entre streams
n'est promis ; opérations impliquant plusieurs agrégats restent Q13.

La requête LATERAL sélectionne chaque tête, puis FOR UPDATE OF event_streams SKIP LOCKED réserve
un stream sans bloquer les autres. La tête est relue après verrouillage sous READ COMMITTED.
Une tête blocked ou en backoff ne laisse jamais passer ses successeurs. Un worker peut traiter
plusieurs univers ; aucune variable globale ne sélectionne un univers unique pour tout le processus.

## Atomicité et reprise

Transaction par événement : compteur de tentative, SAVEPOINT, avancement cursor à due_at, handler,
completed et enfants. Si le handler échoue, rollback du curseur, des stocks et enfants ; la transaction
conserve seulement attempts/next_attempt_at/code générique, sans payload ou détail d'exception en log.
Après trois échecs par défaut, état blocked ; retry différé de 30 secondes et reprise explicite après
correction. Une interruption avant commit annule tout ; après commit l'effet ne se répète pas.
Pas de réservation persistée séparée, pas de bail orphelin ni queue mémoire comme autorité.

Le calcul des stocks utilise la date logique, pas l'heure tardive du poll. completed_at est la date
de traitement effective. Les handlers ne commitent pas, n'appellent aucun service externe et ne
prennent pas un second stream ; ajouter un domaine futur nécessitera de documenter ses verrous.
Leur code est serveur de confiance, pas un sandbox de plugins tiers.

## Rattrapage borné et économie

Scheduler.catch_up_stream(session, stream_id, universe_id, until, limit=100) traite les événements dus
puis avance le curseur. Limite ou tête en erreur/backoff : complete=False, sans dépassement d'échéance.
L'horloge injectable interdit un avancement futur ; un retour dans le passé est refusé.
TimeEngine.catch_up(session, colony_id, until) utilise ce contrat et règle les ressources uniquement
si le stream est complet. Un service de dépense futur exigera cette complétude sous le même verrou
avant coûts et écritures dans sa transaction ; aucun tel endpoint public n'est exposé maintenant.

Le seul handler métier technique livré est RESOURCE_RATE_CHANGE (alloys/flux/data, taux entier
non négatif). Les exemples BUILDING_COMPLETE, RESEARCH_COMPLETE, AI_TURN, FLEET_ARRIVAL/RETURN,
EXPLORATION_COMPLETE sont des extensions documentées, pas des handlers factices ou features implémentés.
Un type inconnu suit la politique retry/blocked, jamais une réussite silencieuse.

## Migration et exploitation

0003 préserve l'historique 0002 et extrait ses streams ; 0001/0002 inchangées. Downgrade refusé si
un stream n'a pas d'adaptateur colonie ou si son curseur économique ne permet pas le retour sans
perte (cursor_at != settled_at). Vérification en ligne avant tout DDL ; roundtrip peuplé en CI.

Compose exécute migrate puis API/worker du même monolithe. Le worker traite par lots de 50 et attend
une seconde entre lots ; ce n'est pas un tick qui simule toutes les planètes. CLI bornée :

```bash
docker compose exec worker python -m app.simulation.worker --once --limit 50
docker compose exec worker python -m app.simulation.worker --blocked --limit 50
# Après correction, uniquement pour l'UUID réellement listé :
docker compose exec worker python -m app.simulation.worker --retry UUID_DU_EVENT
```

La CLI opérateur peut inspecter plusieurs univers ; elle n'est pas une API joueur. Retry conserve
identité/date/payload et remet le compteur de tentatives à zéro. Polling/retries sont techniques,
pas des paramètres de vitesse gameplay. Archivage/versionnement des payloads et métriques de charge
restent futurs. Aucun WebSocket/Redis, aucune présence de navigateur comme condition de progression.

[Calcul](resource-calculation.md) · [ADR 0005](../adr/0005-colony-time-engine.md) · [Instance](../adr/0006-universe-game-instance.md)

## Construction Étape 5A

TimeEngine enregistre CONSTRUCTION_COMPLETE. Le handler vérifie order_id/univers/stream/clé,
règle les ressources à due_at, applique le niveau une seule fois et active le prochain ordre à la
même date logique. Effets et événement suivant sont dans la transaction du scheduler ; pas de commit
ou autre lock de stream. Annulation sous le même lock après catch-up ; échéance annulée acquittée
avec error_code cancelled, sans modifier sa date ni terminer le chantier métier. Le worker reprend
les événements persistants sans joueur connecté. Voir [ADR 0007](../adr/0007-colony-economy.md).
