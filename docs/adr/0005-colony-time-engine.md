# 0005 — Streams génériques et économie de colonie séparée

- Statut : acceptée ; révisée après audit de PR #3, avant sa fusion.
- Date : 2026-10-28.

## Contexte et correction

L'implémentation initiale rattachait ScheduledEvent directement à ColonyTimeline. Ce couplage aurait
obligé les échéances d'empire, flotte ou univers à se faire passer pour une colonie ou à réécrire le
scheduler. L'audit demande une abstraction extensible sans implémenter ces features futures.

## Décision

EventStream appartient à Universe et contient cursor_at/next_sequence. ScheduledEvent référence
(stream_id,universe_id), avec ordre due_at/séquence et clés idempotentes uniques par stream.
Le scheduler.py générique ne dépend ni de Colony, ni de ResourceBalance, ni d'un type de propriétaire.
Il prend le verrou de stream et dispatch des handlers serveur transactionnels.

ColonyTimeline contient le lien typé colony/stream/universe et settled_at économique. Des FK composites
interdisent les liaisons entre univers et stream_id est unique sur cet adaptateur. service.py compose
le scheduler avec le handler de taux ; ce dernier règle l'économie avant de modifier le taux.
Le rattrapage de colonie termine le règlement économique après rattrapage complet du stream.
Un événement sans effet économique peut faire avancer cursor_at sans produire une écriture de stock.

Pas de owner_kind/owner_id générique sans FK, ni d'héritage polymorphe ORM. De futurs adaptateurs
EmpireTimeline/FleetTimeline pourront lier leurs entités à EventStream par FK explicites ; ils ne sont
pas créés. Le scheduler ne requerra pas de nouvelle colonne sur tous les événements historiques.

## Garanties conservées

Verrou FOR UPDATE OF event_streams SKIP LOCKED ; tête bloquante par stream, autres streams/univers
indépendants. Transaction par événement, SAVEPOINT pour effets/enfants et cursor, retries bornés,
reprise après crash et relance explicite. Calcul économique exact en micro-unités avec reste,
UTC, absence de Redis et PostgreSQL autoritaire. Aucun contrat d'ordre global multi-streams inventé.

## Migration et limites

0001/0002 sont conservées. 0003 crée les streams, rattache chaque ancienne timeline et conserve UUID,
clés, dates, payload, statuts, compteurs et balances des événements 0002. Les anciens UUID de colonie
servent de mapping déterministe au backfill ; aucune hypothèse d'égalité au runtime.

Downgrade en ligne seulement : tous les streams doivent être rattachés à une colonie et cursor_at
égal à settled_at ; sinon refus avant DDL plutôt que perte de scopes ou de progrès. Les roundtrips
vides et peuplés sont testés. Les données de jeu futures, rulesets et ordre multi-agrégats restent ouverts.
Aucun handler Research/Fleet/AI/Combat ni mode multijoueur ajouté.

[Contrat](../03-technical/event-engine.md) · [Économie](../03-technical/resource-calculation.md) · [ADR 0006](0006-universe-game-instance.md)
