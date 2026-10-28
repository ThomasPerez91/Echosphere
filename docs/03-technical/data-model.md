# Modèle de données conceptuel

**Statut : fondations et temps de colonie persistants ; autres domaines futurs.**


| Concept | Responsabilité et relations proposées |
| --- | --- |
| Universe | Seed, version de génération, règles/version des données |
| Empire | Appartient à un univers ; pilotage humain ou IA |
| System / Route | Nœud et liaison du graphe, propres à un univers |
| Planet | Monde physique d'un système, traits et capacité |
| Colony | Exploitation d'une planète par un empire |
| Infrastructure | Occupation d'un secteur ou emplacement orbital de colonie |
| Research | État de recherche global d'empire |
| Fleet / Mission | Unités engagées et mouvement planifié |
| Knowledge / Report | Projection par empire et information datée |
| ScheduledEvent | Échéance persistante et référence métier |

Le tableau distingue le modèle cible de la partie implémentée ci-dessous ; les autres concepts restent
à concevoir aux étapes concernées. L'identité/authentification humaine n'est pas implémentée.

## Schéma livré (migration 0001_world_foundation)

| Table | Champs spécifiques et garanties |
| --- | --- |
| universes | name, seed ; aucune génération exécutée |
| empires | universe_id, name, controller_type human/ai |
| stellar_systems | universe_id, name ; pas encore de positions/routes |
| planets | universe_id, system_id, name, sector_capacity > 0, orbital_capacity >= 0 |
| colonies | universe_id, empire_id, planet_id unique |

Chaque table a un UUID généré par PostgreSQL et un created_at timestamptz. Noms non vides, limite
technique 120 caractères ; seed chaîne de 200 caractères. Une seed n'est pas unique : plusieurs
univers peuvent partager une graine. Le générateur et sa version seront introduits à l'étape 7.
Aucune valeur par défaut de secteurs/orbite ne fige les orientations de gameplay 9–18/12.

Des FK composites imposent que planète/système et colonie/empire/planète appartiennent au même
univers. Les index suivent les relations de contenance. Suppression restrictive : aucune cascade
ne détruit silencieusement un empire. Le modèle représente seulement l'exploitation courante,
sans historique, abandon ou conquête ; Q07 reste ouverte. Une migration ultérieure pourra conserver
cet historique sans transformer l'unicité présente en règle de colonisation définitive.

## Schéma temporel livré (0002_colony_time)

colony_timelines : colony_id PK/FK, settled_at, next_sequence ; verrou et ancrage commun.
resource_balances : clé colony_id/resource, stock, rate_per_hour et remainder BIGINT, capacity nullable,
updated_at. Exactement trois lignes fournies par initialize ; aucune ligne automatiquement peuplée.
scheduled_events : UUID, colony, due_at, séquence, clé idempotente, type/payload JSONB, statut,
tentatives, prochaine tentative, completed_at et code d'erreur générique. Unicité des clés/séquences
par colonie et index de file. Les timestamps sont timestamptz. Aucune suppression en cascade.
Ces trois tables ne spécifient pas encore bâtiments, recherche, missions ou événements inter-empires.

## Invariants des étapes futures

Références cohérentes au même univers, absence de stock négatif, occupation de secteur valide,
une exploitation active d'un monde selon les règles à définir, unicité d'effet d'un événement.
Utiliser `timestamptz`, UTC applicatif et contraintes DB en complément des services.
L'historique d'occupation et les collisions de colonisation relèvent de Q07.

Proposition : IDs opaques, index des échéances et clés de visibilité par empire. Choix des types
numériques et précision monétaire/ressources à arrêter en Q03. Ne pas créer toutes ces tables
simplement parce que le diagramme conceptuel les mentionne.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
