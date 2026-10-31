# Modèle de données conceptuel

**Statut : fondations, Colony 5A/5D et identité 5C intégrées à master via PR #8 (`0e2ca11`).**
Les sections de migrations et extensions ci-dessous décrivent leur état à livraison ; leurs mentions
« futures » de Membership/GameSession/5D sont historiques. Référence actuelle :
[API Colony](colony-api-ui.md), [handoff](game-handoff.md) et [contrôle privé](portal-game-control.md).
Research étape 6 sur PR #9, Q05 validée : [plan](../05-project/step-6-plan.md),
[schéma/API](research-api-ui.md).


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
à concevoir aux étapes concernées. L’identité/authentification humaine existe depuis 5C ; ce tableau n’est pas l’inventaire des tables livrées.

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
Q51–Q54 closes pour leurs contrats 5B, Q21 partage d’Empire validé le 31/10/2026, parcours produit futur.

Compte global et plusieurs univers simultanés ; User → UniverseMembership → Universe →
éventuellement Empire/rôle/permissions. Pas de réduction à Empire.owner_user_id, partage Q21 validé, sans owner unique.
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

## Extension C03 sur PR #7

[Sessions Portal/CSRF](portal-sessions.md) : migration Accounts additive p0002, cinq tables
profils/appareils/sessions/challenges/intentions de logout. Aucun schéma Game modifié. Les intentions
de déconnexion sont persistées mais leur livraison/acquittement distant reste à C06/C07.

## Extension C04 sur PR #7

[Opérations sensibles sans MFA](portal-account-security.md) : step-up par action cinq minutes/unique,
reset trente minutes, double confirmation email une heure et logout global. Migration Accounts p0003
additive, notifications chiffrées et intentions de révocation Game pending. MFA/privilèges refusés
sans preuve suffisante ; [C05](portal-mfa.md) fournit maintenant les facteurs et leur intégration.
Aucune livraison Game ou API Colony ajoutée.

## Extension C05 sur PR #7

[MFA Portal](portal-mfa.md) : TOTP unique, cinq WebAuthn nommables, dix secours uniques et récupération
limitée quinze minutes ; preuve par action cinq minutes, garde-fous privilégiés WebAuthn, aucune
restauration support inventée. Migration Accounts p0004_mfa, clé TOTP séparée, cooldown progressif,
audit et notifications. Ajout de facteur/régénération volontaire protégés conservent les sessions ;
activation, réduction/remplacement/désactivation et récupération révoquent globalement. Intentions
Game pending à ce checkpoint C05 ; [C06](portal-game-control.md) livre depuis leur transport et
acquittement. Aucun secret Accounts ou SQL Portal dans Game, aucune API Colony.

## Extension C06 sur PR #7

[Lobby et contrôle privé](portal-game-control.md) : références/memberships/outbox Accounts p0005,
droits/bindings/ledger/epochs Game 0005. Listener mTLS distinct de l’API publique, certificat client
épinglé depuis TLS, aucune identité de header ; destinations configurées, pas de SQL Portal→Game.
Snapshots complets/révisions monotones, retry d’opération stable sans nouvelle date, acquittement
validé et réconciliation. Révocations compte/appareil diffusées à chaque cible configurée, sources
acknowledged seulement après tous les acquittements. Sessions Game ajoutées par [C07](game-handoff.md), aucune API Colony.
Lobby limité à son compte, pending/applied/expiration datés, aucun univers de démo ou join public ;
GET sans activité ni renouvellement, refresh volontaire classé serveur. Recette réelle sur deux bases
temporaires *_test et refus TLS/headers, séparée du Chromium à API interceptée ; résultats dans progress.


## Complément C07 sur PR #7

[Handoff et sessions Game](game-handoff.md) : ticket signé Ed25519 local, pré-auth navigateur,
échange POST atomique et cookie par univers ; contexte minimal et logout, aucun endpoint Colony.
Game additive 0006_game_sessions, Accounts p0005_control inchangée. Rotation/production et
nettoyage à recetter en C09 ; commandes sécurisées réservées à 5D.


Compléments actuels sur PR #7 : [C08 parcours et shell](portal-game-ui.md),
[C09 recette et opérations](portal-operations.md). Aucun début de 5D ni exposition production.

## Extension étape 6 — PR #9

Game 0007 ajoute EmpireResearch (FK Empire/Universe/EventStream), ResearchOrder (source Colony
composite dans le même Empire/Universe, snapshots et reçus) et AcquiredTechnology unique.
Index uniques actif/suivante/technologie non annulée et clés/séquences par Empire. Aucune caisse
Empire, migration Accounts ou modification des anciennes migrations. Contrats et downgrade :
[Research technique](research-api-ui.md). Les sections C01–C09 ci-dessus restent historiques.
