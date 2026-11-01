# Conception du moteur IA

**Statut : Orientation validée, future — moteur déterministe/testable sans LLM stratégique.**


Le moteur initial n'utilise pas de LLM. Un décideur Utility/Goals reçoit une observation autorisée,
un profil et un instant logique. Il évalue des objectifs, sélectionne une commande valide puis
passe par le service d'application commun. Les poids ne modifient pas les règles économiques.

## Séparation proposée

Observation filtrée → génération des options connues → score → départage déterministe → commande.
Un ordre stable de départage empêche l'ordre d'une requête SQL de modifier arbitrairement le choix.
Si un aléatoire devient utile, il devra être seedé et enregistré ; ce n'est pas encore décidé.

## Exécution future

Un AI_TURN persistant assure la reprise après crash. Budget de calcul, fréquence et backoff après
commande refusée relèvent de Q11/Q13. Un refus normal, tel qu'une ressource devenue insuffisante,
ne déclenche ni ressources compensatoires ni accès privilégié.

## Tests attendus

État identique et profil identique donnent la même décision ; connaissance cachée inaccessible ;
refus métier identiques à ceux des humains ; autonomie sur plusieurs cycles ; trace expliquant
les scores ; simulations headless sans HTTP. Commerce et diplomatie avancée ne doivent pas être
introduits pour « compléter » l'IA du bootstrap.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Frontières futures Portal/Game

Perception → Goals → Evaluation → Decision → Action reste dans le Game Backend, indépendant de
la présence ou de la disponibilité Portal. L’IA appelle les mêmes services métier que l’humain et
la simulation headless. Les comptes globaux ne lui confèrent aucun accès omniscient. Les mécanismes
de planification AI_TURN et leurs budgets restent à implémenter, aucune cadence fixée par la passation.

## AI01 — audit du code intégré

**Audit Codex local du 01/11/2026, lecture indépendante sur master
`a33a452b416ec83d4e8b91d84292913d18db5a40`.** Aucune implémentation IA, migration ou donnée
exécutable ajoutée. Les constats ci-dessous viennent du code, pas des comptes rendus antérieurs.
Les numéros de ligne désignent ce SHA. [Proposition Q11 non validée](../01-game-design/artificial-intelligence.md#q11--proposition-ai01-du-01112026-non-validée),
[plan conditionnel](../05-project/step-11-plan.md).

### Inventaire et points de réutilisation

| Domaine / preuve dans le dépôt | Fait constaté et conséquence IA |
| --- | --- |
| `backend/app/persistence/models.py:48` ; recherche `rg 'AI_TURN\|controller_type\|ai_controller\|ai_profile' backend scripts game_data` | Empire porte uniquement `controller_type` human/ai. Aucun contrôleur, profil, tour ou handler AI_TURN exécuté ; ce champ n'est pas une identité ni un droit. |
| `backend/app/colony/service.py:50`, `:66`, `backend/app/colony/rules.py:172`, `:306` | Règles strictes copiées par Universe ; versions v0.1→v0.5 chargées explicitement. Le chargeur n'a aucun champ IA. Ajouter un JSON seul ne crée pas de contrat et serait refusé comme extra. |
| `backend/app/colony/service.py:188`, `:359`, `:381` | `plan_order`, `catch_up_owned`, `enqueue` vérifient propriété, file, capacité réelle, prérequis, stocks et niveaux continus ; SAVEPOINT, coûts réservés, clé idempotente, pas de commit. Réutilisables sans HTTP. |
| `backend/app/colony/projection.py:78`, `:152` | Options utilisent le même `plan_order` ; unités exactes, stocks, taux et file propres disponibles. Le DTO complet contient des identités d'univers : extraire uniquement les données utiles au décideur, pas lui donner une Session ORM. |
| `backend/app/research/service.py:60`, `:87`, `:122`, `:240` | Stream Research distinct, file Empire 1+1, source Colony explicite, coût/durée snapshotés. Research précède tout stream Colony ; bonus acquis et file déjà financée doivent entrer dans la perception. |
| `backend/app/galaxy/service.py:58`, `:78`, `:174`, `:196`, `:234` | `detect`/`map_system` découvrent le monde lors d'effets autorisés ; `project_system` et `known_path` lisent les Knowledge de l'Empire. Ne jamais donner les fonctions de découverte ou le manifeste/seed au décideur. MONITORED ne vient que de ses colonies, pas d'une flotte stationnée. |
| `backend/app/galaxy/api.py:198`, `backend/app/fleet/api.py:365` | GET Galaxy/System/Fleet verrouillent sans rattraper les opérations. Un tour IA est une action interne autonome, pas un GET caché ni une page qui déclenche la stratégie. |
| `backend/app/fleet/service.py:48`, `:200`, `:508`, `:559`, `:593`, `:715` | Production, division/fusion, chargement/déchargement et lancement existent comme services transactionnels. Ordre opérations→Research→Colony ; attache payeuse imposée. Cargo chargé réellement, surplus de déchargement gardé à bord, pas de ressources d'Empire abstraites. |
| `backend/app/fleet/models.py:85`, `:144` | FK Universe/Empire/Knowledge et mission ouverte unique ; unité portée par un stack, pas un nouvel inventaire IA. Flottes MERGED/SETTLED à exclure des options, MOVING jamais mobilisables à nouveau. |
| `backend/app/fleet/service.py:628`, `:837`, `:1079`, `:1097` ; `backend/app/colonization/service.py:22` | COLONIZE vise une PlanetKnowledge ; pas d'information d'occupation étrangère au devis/lancement. La résolution serveur peut consulter l'occupation et les concurrents sous verrou planète, pas le décideur. Fondation : cargo livré, zéro revenu/bâtiment, colonisateur consommé, échec générique et flotte conservée. |
| `backend/app/colony/service.py:275` | `initialize_colony` reste le départ 12/2 doté de stocks et quatre infrastructures ; ce n'est ni une commande stratégique ni l'initialiseur de colonisation. Interdit de l'appeler comme compensation d'une IA pauvre. |
| `backend/app/colony/api.py:65`, `backend/app/fleet/api.py:329`, `:421`, `backend/app/access/service.py:237`, `:253` | GameSession/epochs/binding/permissions sont contrôlés par les adaptateurs humains. Les services internes reçoivent une identité de confiance et ne prouvent pas eux-mêmes une autorisation IA. Un faux cookie, User ou membership serait un contournement, pas une intégration. |
| `backend/app/control/contracts.py:12`, `backend/app/control/service.py:118` | 13 permissions existantes ; ProvisionUniverse crée seulement name/seed. Aucun provisioning de partie jouable ou principal IA dans le contrat Portal/Game. Ne pas élargir les permissions humaines ou simuler un compte IA. |
| `backend/app/simulation/scheduler.py:155`, `:180`, `:218` ; `backend/app/simulation/service.py:154` | Handler sous un stream, aucun second stream/commit/effet externe ; rollback et retry/blocked, curseur monotone. TimeEngine enregistre les domaines intégrés mais pas AI_TURN. Un handler IA appelant Colony/Research/Fleet violerait cette frontière. |
| `backend/app/simulation/worker.py:23` | Worker commun borné (lot 50, poll 1 s par défaut), aucun parcours de décision IA. Réutiliser les achèvements existants ; un nouveau rythme stratégique ne doit pas multiplier ni remplacer les événements métier. |
| `backend/app/galaxy/world.py:14`, `:91`, `scripts/colonization_game_fixture.py:41`, `:112` | Monde et sites candidats générés explicitement, pas de réservations. La recette sélectionne les sites par UUID et place des unités de rival directement en DB pour tester la concurrence. Ces helpers sont *_test seulement : pas un bootstrap équitable reproductible d'IA et pas une source de vaisseaux runtime. |
| `backend/migrations/versions/0001_world_foundation.py:47`, `0010_colonization.py:1` | Chaîne Game jusqu'à 0010 ; controller_type dès 0001, aucune table IA dans les modèles/migrations. Une persistance des tours réellement reprise après crash nécessitera une migration additive future, aucune réécriture de 0001–0010. |

Comparaison JSON locale en lecture seule : 5 infrastructures dans v0.1→v0.5, 8 technologies dès
v0.2 ; v0.3 Exploration abstraite, v0.4 probe/freighter + SURVEY, v0.5 ajoute colonizer/colonization.
Les contenus Colony/infrastructures/resources/Research/Galaxy v0.4 et v0.5 sont identiques hors
`version`. v0.5 n'a ni classe militaire, ni score d'ennemi, ni entretien ni moteur de relations.

### Écarts documentaires et risques d'intégration

- **Majeure pour une future implémentation naïve, pas bug runtime actuel :** le futur AI_TURN
  esquissé plus haut n'autorise pas plusieurs streams dans un handler. Option retenue dans la
  proposition ci-dessous : orchestrateur transactionnel hors handler, sans amender cet invariant.
- **Majeure avant activation IA :** controller_type seul ne garantit ni périmètre d'action ni
  observabilité limitée. Contrôleur serveur explicite et DTO sans ORM à prévoir ; aucune route
  humaine ne doit bénéficier de ce contexte interne.
- **Majeure avant recette d'autonomie :** une colonie fondée commence à 0/h ; sans priorité de
  bootstrap, un décideur peut dépenser son paquet sans revenu d'Alliages/Flux. Le service ne doit
  pas « réparer » une mauvaise décision en donnant des ressources.
- **Majeure pour la promesse de reproductibilité :** monde canonique seedé ne signifie pas UUID
  identiques entre deux bases. `Record` utilise gen_random_uuid et le rang COLONIZE inclut l'UUID.
  Promettre même décision sur observation/identifiants figés ; les campagnes nécessitent un
  manifeste d'identités et un calendrier d'entrées, pas seulement la seed.
- **Mineure documentaire :** vision/économie et plusieurs paragraphes historiques présentent
  encore Research/Fleet/Colonization comme futurs ; le catalogue et les handlers intégrés font
  foi. Le plan étape 10 envisageait aussi un champ ShipClass `colonize` ; le schéma réel reste
  inchangé, le colonisateur est décrit par ColonizationRules. Pas de refonte générale de ces docs.
- **Remarque de périmètre :** aucun contrôle automatique de difficulté, combat, diplomatie,
  population, scanner, surveillance par flotte ou projection d'occupation étrangère à réutiliser.
  Les inventer pour justifier un profil agressif fermerait implicitement Q10/Q18, hors lot.

### Preuves existantes examinées, limites de l'audit

Lecture des scénarios de tests : Colony (réservation/courses/rejeu/niveau >5), Research
(prérequis/deux sources/cascade), Galaxy/System (non-fuite/knowledge/GET sans achèvement), Fleet
(engagement, dépense multi-domaines, worker concurrent, snapshots), Colonization
(rang/ordre inverse/rappel/paquet/FK), sessions (expiration/révocation) et scheduler
(rollback/reprise/tête bloquée). Exemples : `test_fleet.py:589`, `test_colonization.py:341`,
`test_system_view.py:105`, `test_time.py:177` sous `backend/tests/integration/`.

CI post-merge **41340653571 sur a33a452** effectivement vérifiée : cinq jobs success ; journaux
lus : 364 tests Game, 124 Portal, 81 Vitest Game, 31 Chromium Game. Le job Compose contient les
smokes de base/Portal/control/handoff/Colony/Research/Galaxy/Fleet/Colonization et Alembic check.
Les fixtures de concurrence/recettes peuvent accélérer le temps et placer des unités directement
pour leur scénario : elles ne démontrent pas une IA économique ni sa cadence réelle.

Aucun test runtime, migration, Compose ou benchmark relancé localement pendant AI01 (mission
docs). Check documentaire/liens, comparaison JSON et diff seulement. Aucun résultat de charge,
équilibrage, autonomie, isolation matérielle ou recette appareil physique inféré. Absence de bug
supplémentaire prouvé dans les chemins examinés ≠ revue exhaustive de sécurité du dépôt.

## Architecture AI01 proposée — non validée, non implémentée

### Frontières et état

Game garde un module IA du même monolithe, séparable en processus pour borner CPU/pool ; aucun
service Portal par décision, ni microservice externe, LLM, Redis ou appel réseau stratégique.
Le décideur pur reçoit une **observation immuable autorisée**, profil/version, date et mémoire
propre bornée ; il renvoie WAIT ou une intention typée. Il n'a pas de Session, modèle ORM,
manifest de galaxie, seed, StartingSite ou callback lui permettant d'interroger la DB.

Le collecteur serveur de confiance réutilise les projections/helpers existants : Knowledge de
cet Empire, colonies et flottes propres, recherche et devis communs. Extraire les fonctions de
projection aujourd'hui dans les classes HTTP si nécessaire, sans changer leur filtrage humain.
Seule l'occupation propre est lisible ; jamais SELECT d'occupation étrangère pour choisir une
cible. Les vérifications autoritaires de lancement/résolution restent dans les services communs.
Chaque bloc de perception porte ses dates ; un fait ancien reste ancien, absence d'information
≠ vide. Aucun clone du calcul économique, des prérequis, du BFS ou des coûts dans la politique.

Contexte interne proposé : contrôleur persistant actif lié par FK composite à un Empire/Universe,
capabilities explicitement limitées aux opérations livrées (colony.read/construct,
research.read/start, galaxy.read, fleet.read/build/command, colony.expand). Aucun nouveau droit
HTTP, grant Portal ou délégation fondée seulement sur `controller_type`. Pas de cancel/rappel
automatique dans la politique proposée. Les contrôles d'action communs incluent les mêmes
combinaisons de droits que l'API humaine ; tests de parité obligatoires si extraction d'un
adaptateur d'application commun. Le dispatcher n'accepte ni Universe ni Empire produits librement
par le décideur : ils viennent exclusivement du contrôleur verrouillé ; les entités sont revalidées.

Persistance proposée (noms indicatifs, aucune table créée) :

- Contrôleur 1/Empire : FK (Empire, Universe), état enabled/paused/blocked, version profil/données/
  moteur, prochain rendez-vous UTC, séquence de décision, projet courant et curseurs de pagination.
  Ne pas créer de colonne Account credential ni de liaison User factice. Refus d'activation si
  bindings humains existants ; réciproquement pas de grant humain sur Empire IA actif, sans
  invalider les règles actuelles des autres Empires. Changer de contrôleur reste hors lot.
- Décision : clé unique (contrôleur, séquence), dates prévue/réelle, observation/versions figées,
  candidats/scoring/départage, intention/clé métier, résultat ou refus public, état des budgets.
  FK de scope réelles, pas de owner_kind/owner_id polymorphe. WAIT est aussi un résultat.
- Mémoire minimale : projet de préparation (pas un ordre/réservation parallèle), cibles dont son
  propre rapport indique l'échec et curseurs. Connaissance structurelle toujours dans Knowledge.
  Aucun registre de position ennemie ou d'occupation supposée.

Référence de traçabilité proposée : 100 dernières décisions rejouables par Empire, observation
≤256 KiB et candidats/résultat ≤64 KiB par tour ; dépassement = refus technique sans commande,
jamais troncature cachée des entrées du décideur. Conservation bornée au-delà de cette fenêtre,
compteurs agrégés et lien vers reçus métier existants ; pas de promesse de rejeu complet après
purge. Traces privées opérateur seulement, sans cookies/credentials/payload Account ; aucune
nouvelle API publique qui révèle les objectifs d'une IA ou sa Knowledge.

### Orchestration, temps, concurrence et reprise

**Option recommandée : rendez-vous durable sur le contrôleur, orchestrateur hors ScheduledEvent
handler.** Même backend/image Game, CLI/processus borné et explicitement activé. Le worker
TimeEngine continue de terminer les événements métier habituels. Une ligne next_decision_at
n'est pas un second simulateur de production/mouvement.

1. Sélectionner un contrôleur dû par `(next_decision_at, empire_id)` et FOR UPDATE SKIP LOCKED ;
   relire état/version sous verrou. Un contrôleur par transaction, au plus un tour par Empire
   dans un lot. Pause/arrêt opérateur prend ce même verrou, puis aucune nouvelle commande ;
   ordres déjà acceptés continuent normalement. Aucun verrou principal humain.
2. Ordre d'acquisition : contrôleur → opérations d'Empire → Research → streams des colonies
   propres existantes triés par UUID. Pas d'appel d'un domaine qui reprenne un verrou amont
   après un verrou aval. Les services actuels reprennent leurs propres locks de façon réentrante.
   Initialiser Research/opérations au bootstrap, pas en parcourant des contrôleurs incomplets.
3. Capturer l'heure serveur **après attente des locks existants**, puis rattraper les opérations,
   Research et colonies jusqu'à cette même date. Une COLONIZE due peut créer une Colony et un
   stream **neufs**, non visibles hors transaction : les inclure ensuite dans l'état et le
   règlement, sans acquisition d'un autre stream existant dans le handler. L'exception de
   création neuve est déjà celle de l'étape 10. Vérifier cet ordre par tests PostgreSQL avant
   toute activation ; un catch-up incomplet interdit toute décision/dépense.
4. Construire le DTO borné et ordonné, puis décider ; dispatcher vers `enqueue`, `research.start`,
   `order_ships`, `split`/`load`/`unload`/`launch` nécessaires au projet, **une seule commande**.
   Aucune écriture directe ResourceBalance/Fleet/Knowledge depuis la politique. L'heure du tour
   reste figée, sans antidatation à l'ancien rendez-vous. Les services revalident leur coût,
   leur scope et leurs règles ; un devis n'est jamais une réservation.
5. Dans la même transaction : effet/WAIT/refus métier, trace, mémoire, séquence suivante et
   prochain rendez-vous. Clé métier dérivée du contrôleur+séquence (`ai:…` distinct de `http:…`,
   ≤160 caractères) ; aucun nouvel UUID de clé sur retry. Crash avant commit = aucun effet du
   tour ; après commit = aucune seconde commande, même avec deux processus ou reprise opérateur.
6. Prochain rendez-vous sur la grille de 600 s ancrée au départ, strictement après l'heure
   observée ; pas de boucle sur chaque créneau manqué. Les durées métier restent les durées du
   ruleset. Tests avec horloge injectée, jamais sleep réel pour accélérer une partie de production.
7. Refus métier : conserver seulement le code autorisé et patienter au créneau suivant, pas
   d'essai d'un deuxième candidat dans ce tour. Erreur technique : rollback **de tout le tour** ;
   enregistrer retry/compteur en transaction courte distincte sous contrôleur avec condition de
   séquence/état pour ne pas écraser un autre worker ; après budget technique atteint, blocked
   opérateur. Un stream métier blocked conserve sa procédure de réparation existante.

Alternative écartée : AI_TURN handler qui appelle les services multi-streams ; contraire à
l'invariant actuel. Autre possibilité : AI_TURN ne produit qu'une intention et un dispatcher
l'exécute plus tard ; deux phases/outbox imposeraient revalidation et reprise supplémentaires
sans besoin ici. Un tick mémoire/cron sans ligne due persistée ne garantit pas la reprise.
L'esquisse AI_TURN en tête de document est donc historique/proposée, pas une instruction à coder.

### Déterminisme, ressources et validation future

Même observation canonique + mémoire + profil/données/version + date = mêmes candidats, scores,
choix et commande. Entiers uniquement, tri explicite, aucun hash Python ni UUID frais pour départager
les options. Les UUID persistés peuvent être des clés stables sur une même base ; un scénario
multi-bases doit figer/rejouer le manifeste des identités, pas promettre une égalité par seed seule.
Les résultats multi-Empires dépendent aussi des commandes humaines/temps/rangs de missions :
aucune garantie de même gagnant global malgré des entrées ou horaires différents.

Les parcours doivent être bornés **avant** matérialisation SQL/Python : 12 colonies, ≤50 systèmes/
250 mondes connus dans ce profil, flottes par page 64 et historiques limités. Génération ≤128
candidats, répartition par objectif et curseurs stables dans les données IA pour éviter de
focaliser toujours la première colonie. Pas de produit cartésien flottes×toutes planètes, ni de
SELECT global puis filtrage. Mesurer nombre de requêtes, durée des locks/tours, retard, erreurs,
WAIT par cause, ressources réellement payées et écarts entre profils ; objectifs ≠ mesures.

Nouveau ruleset v0.6 proposé : mêmes paramètres économiques que v0.5, section IA stricte, profils/
cadence/budgets/normalisations versionnés et épinglés. Loader et snapshots v0.1→v0.5 inchangés,
pas de migrateur implicite d'anciens univers. Bootstrap opérateur explicite : sélectionner des
sites distincts par ordinal canonique du générateur (pas UUID aléatoire), créer humain et IA avec
le même initialiseur à date commune, Knowledge locale puis contrôleurs. Transaction/rejeu de
bootstrap vérifiables ; aucun import des fixtures *_test dans le runtime. Ne pas attribuer de
membership humain à une IA, ni décider d'un nouveau parcours de lobby.

Tests futurs : décideur pur/rejeu et variation de monde caché sans changement de choix ; parité de
coûts/refus et capabilities ; isolation Universe/Empire ; deux workers/rollback/reprise/pause ;
catch-up complet et retard/coalescence ; colonie créée pendant le tour sans deadlock ni recul de
curseur ; progression autonome plusieurs cycles sans crédit/unité offerts, échec COLONIZE connu
sans révéler l'occupant ; budgets et pagination ; v0.1→v0.5 inchangés. Recette réelle page fermée,
redémarrage, Portal coupé et session humaine expirée sans arrêter les IA/ordres, preuve DB avant
lecture. Aucun de ces nouveaux tests n'est déclaré passé à AI01.
