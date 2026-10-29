# Modèle de données conceptuel

**Statut : Implémenté jusqu’au domaine Colony 5A sur PR #5 ; identité et autres domaines futurs.**


| Concept | Responsabilité et relations proposées |
| --- | --- |
| Universe | Frontière d’instance de jeu ; seed et appartenance d’instance ; ruleset/version via universe_economies en 5A |
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

## Schéma historique 0002 (remplacé par 0003)

colony_timelines : colony_id PK/FK, settled_at, next_sequence ; verrou et ancrage commun.
resource_balances : clé colony_id/resource, stock, rate_per_hour et remainder BIGINT, capacity nullable,
updated_at. Exactement trois lignes fournies par initialize ; aucune ligne automatiquement peuplée.
scheduled_events : UUID, colony, due_at, séquence, clé idempotente, type/payload JSONB, statut,
tentatives, prochaine tentative, completed_at et code d'erreur générique. Unicité des clés/séquences
par colonie et index de file. Les timestamps sont timestamptz. Aucune suppression en cascade.
Ces trois tables ne spécifient pas encore bâtiments, recherche, missions ou événements inter-empires.

## Migration 0003 : scope générique et intégrité d'univers

EventStream : UUID, universe_id FK Universe, cursor_at et next_sequence. Il n'est ni une colonie
ni un pointeur polymorphe sans FK. ScheduledEvent référence (stream_id, universe_id) par FK composite ;
clés idempotentes et séquences uniques par stream, index d'ordre par stream.
ColonyTimeline : colony_id PK, universe_id, stream_id unique, settled_at. FK composites vers
Colony(id,universe_id) et EventStream(id,universe_id). La contrainte unique correspondante sur Colony
est ajoutée ; ResourceBalance reste attaché à l'adaptateur économique. Aucun lien user_id sur Empire.

0003 migre les événements 0002 sans changer UUID, clé, état, tentatives, payload ni stock/reste.
Downgrade seulement si tous les streams ont un adaptateur colonie et cursor_at=settled_at ; sinon
refus avant DDL, aucune suppression d'historique générique pour forcer le retour en arrière.
Le downgrade nécessite une base en ligne pour cette vérification. 0001 et 0002 restent inchangées.

## Participation/configuration futures, non implémentées

Universe n'est implicitement ni solo ni possédé par un User unique. Account/User ↔ UniverseMembership
↔ éventuellement Empire ↔ rôle/permissions est une future association, pas une table actuelle.
Plusieurs humains, éventuel partage d'empire et spectateur/admin restent possibles sans être décidés.
Règles gameplay par Universe ou ruleset/version, jamais un singleton serveur. Aucune table d’identité ou champ de mode/place ajouté ; les vitesses économie/construction
existent dans le snapshot universe_economies v0.1, sans nouveau mécanisme de mode. Voir [ADR 0006](../adr/0006-universe-game-instance.md).

## Invariants des étapes futures

Références cohérentes au même univers, absence de stock négatif, occupation de secteur valide,
une exploitation active d'un monde selon les règles à définir, unicité d'effet d'un événement.
Utiliser `timestamptz`, UTC applicatif et contraintes DB en complément des services.
L'historique d'occupation et les collisions de colonisation relèvent de Q07.

Proposition : IDs opaques, index des échéances et clés de visibilité par empire. La représentation des ressources est déjà micro-unités BIGINT et reste exact (étape 3) ;
les autres paramètres économiques encore ouverts restent Q03. Ne pas créer toutes ces tables
simplement parce que le diagramme conceptuel les mentionne.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Persistance économique Étape 5A

Migration 0004_colony_economy additive : universe_economies (ruleset validé épinglé et vitesses),
colony_economies (ancrage et séquence), colony_infrastructures (type, niveau, sector_index),
construction_orders (snapshot, coût réservé, séquence, états et dates, remboursement enregistré).
FK composites colonie/univers, unicité secteur et clé de commande, niveau >=1, un actif par index
partiel. Capacité de planète, unicité configurable des types et queue_limit sont vérifiées sous
verrou de stream par le service, sans duplication de game_data en CHECK SQL. Aucun service de
redimensionnement de planète. ResourceBalance et ColonyTimeline restent l’autorité économique.
Aucune table DefenseNetwork/DefenseModule créée ; les futurs adaptateurs typés peuvent s’ajouter.
Voir [ADR 0007](../adr/0007-colony-economy.md) et [règles v0.1](../01-game-design/colony-economy-v0.1.md).

## Identité et bases cibles — sous-ensemble C02 implémenté sur PR #7

Les [contrats 5B validés](identity-contracts.md) distinguent Membership souhaitée côté Portal,
accès effectif versionné et bindings d’Empire côté Game ; une participation par compte/univers.
Les participations et accès restent non implémentés. C01 initialise portal_alembic_version ;
[C02/p0001](portal-registration.md) ajoute users, password_credentials, account_tokens, email_outbox,
abuse_counters et security_events dans Accounts DB seulement. Aucun accès Game créé. Schémas/contraintes sont délégués à 5C/5D ;
Q51–Q54 closes pour leurs contrats 5B, Q21 partage d’Empire toujours ouverte.

Compte global et plusieurs univers simultanés ; User → UniverseMembership → Universe →
éventuellement Empire/rôle/permissions. Pas de réduction à Empire.owner_user_id, partage Q21 ouvert.
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) sépare Accounts DB et Game DB :

| Base future | Données cibles ; sous-ensemble C02 précisé ci-dessus |
| --- | --- |
| Accounts DB, propriétaire Portal | users, credentials/hashes, sessions Portal, MFA/récupération, informations globales membership/lobby |
| Game DB, propriétaire Game | État gameplay existant et futures références minimales global_user_id/universe_id/membership ou access id/empire éventuel/role/status |

Aucun mot de passe/credential Accounts répliqué en Game DB, pas de FK inter-bases imposée.
Portal n’écrit pas dans Game DB ; changements via interface interne Game authentifiée/idempotente.
Portal porte l’intention ; Game l’application locale. Outbox, révisions/idempotence et révocations
ciblées Q51–Q54 validées ; détails de stockage délégués, aucun SQL nouveau dans ce lot.
Les FK composites d’univers actuelles restent inchangées. User est implémenté par C02 ; Membership/GameSession restent futurs.
