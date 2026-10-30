# 5D — API Colony sécurisée et UI Colony

**Statut : en cours sur `work/step-5d-secure-colony-ui` (PR #8), non intégré à master.**
[Plan 5D](../05-project/step-5d-plan.md) · [contrats 5B](identity-contracts.md) ·
[handoff C07](game-handoff.md) · [économie v0.1](../01-game-design/colony-economy-v0.1.md) ·
[ADR 0007](../adr/0007-colony-economy.md) · [ADR 0008](../adr/0008-control-plane-game-data-plane.md).

## Principes

Le backend Game reste l’autorité : stocks, production, coûts, durées, niveaux, capacités, ordre de
la file, droits et échéances viennent du serveur et du ruleset épinglé à l’univers. Les routes
authentifient, autorisent puis délèguent aux services 5A (`enqueue`, `cancel`, `catch_up_owned`).
Aucune règle n’est recalculée dans un handler HTTP ou dans React. Aucun appel Portal pendant une
requête gameplay : une GameSession valide suffit tant que ses échéances 5B ne sont pas atteintes.

Validation et prévisualisation partagent les mêmes fonctions du service : `plan_order` (secteur,
file, contiguïté, unicité, prérequis, ressources), `cancellation_plan`/`recoverable_refunds` (cascade,
remboursements théoriques 100/80, plafonnement et pertes Q39) et `effective_duration_us`. La projection appelle ces fonctions
sur l’état chargé ; la commande les rappelle sous verrou avant de dépenser.

## Chaîne d’autorisation

Chaque requête, dans une seule transaction Game :

1. cookie `__Host-game-session-<univers>` → GameSession vivante (8 h absolues, 2 h d’inactivité,
   au plus `access_valid_until`), verrou du principal (même verrou que les révocations C06) ;
2. GameAccess actif et epochs compte/appareil/accès cohérents ;
3. colonie de cet univers → EmpireBinding de la participation sur l’Empire propriétaire ;
4. sans `colony.read` sur cet Empire, réponse identique à un identifiant inconnu (404
   `colony_not_found`) : un UUID connu ne donne aucun droit et ne révèle pas l’existence ;
5. permission de l’opération : `colony.read`, `colony.construct` ou `colony.cancel` (403
   `permission_denied`). Un administrateur plateforme n’a aucun droit gameplay implicite.

Les commandes revérifient ces droits dans la transaction qui les accepte, puis verrouillent le stream
de la colonie (ordre : principal puis EventStream, comme le contrat 5B). Une commande acceptée est
une activité explicite : `last_activity_at` avance, jamais l’échéance absolue ni `valid_until`.
Une lecture, un timer ou un rafraîchissement automatique ne comptent pas comme activité.

## Routes (origine Game, préfixe `/api` retiré par le proxy)

| Méthode et chemin | Permission | Effet |
| --- | --- | --- |
| GET `/game/{univers}/colonies` | `colony.read` par Empire lié | Liste des colonies lisibles, sans autre donnée |
| GET `/game/{univers}/colonies/{colonie}` | `colony.read` | Rattrapage paresseux puis projection |
| POST `/game/{univers}/colonies/{colonie}/construction-orders` | `colony.construct` | Construction ou amélioration réservée |
| POST `/game/{univers}/colonies/{colonie}/construction-orders/{ordre}/cancel` | `colony.cancel` | Annulation 100/80 avec cascade |

Lectures : header `X-Game-Request: bootstrap`, origine absente ou Game, aucune query string.
Commandes : `Origin` exacte Game, `Content-Type: application/json`, `X-CSRF-Token` dérivé de la
session (vérifié avant tout accès DB), corps strict sans champ supplémentaire ni coercition :

```json
{"idempotency_key": "16–64 caractères [A-Za-z0-9_-]", "infrastructure_type": "extraction_complex",
 "sector_index": 5, "target_level": 1}
```

L’annulation exige un corps `{}` exact. Les réponses de commande renvoient l’ordre et la projection
à jour issus de la même transaction.

## Idempotence et concurrence

La clé client est préfixée par la participation (`http:<membership>:<clé>`) avant d’atteindre la
contrainte unique 5A par colonie : même clé et même contenu → même ordre sans second prélèvement,
même clé et contenu différent → 409 `idempotency_conflict`, même clé chez un autre participant →
commande indépendante. Un retry après timeout réutilise la clé de l’intention : jamais de second
ordre. L’annulation est idempotente par identité d’ordre. Les courses (double clic, dernier slot de
file, amélioration concurrente du même bâtiment, annulations simultanées) sont sérialisées par le
verrou du principal puis du stream et testées.

## Projection

Montants en micro-unités entières sérialisées en chaînes décimales (précision exacte, aucun float
navigateur), durées en microsecondes (chaînes), dates UTC ISO-8601 avec offset, `server_time` de la
lecture. Contenu : identité colonie/planète/système/Empire/univers, secteurs (capacité, construits,
réservés, libres), stocks/capacités/taux horaires, infrastructures et niveaux, file (statut, coûts
snapshot, `started_at`/`due_at`, bonus appliqué, prévisualisation d’annulation avec remboursement,
cascade et raison), options de construction/amélioration (coût, durée de base, durée effective
estimée seulement si l’ordre démarrerait immédiatement, production/capacité/bonus du niveau cible,
disponibilité et raison). La projection ne contient que la colonie autorisée ; elle reste
compatible avec un futur filtrage par fog of war (aucune donnée d’autre Empire/univers).

La lecture applique le rattrapage déterministe de 5A sous verrou (mêmes événements que le worker) :
la colonie progresse sans navigateur ni lecture, et une lecture tardive voit l’état exact.

## Erreurs

Corps `{"error": {"code": ...}, "portal_url": ...}`, `Cache-Control: no-store`.

| Code | Statut | Cas |
| --- | --- | --- |
| `authentication_required` | 401 | Cookie absent/inconnu, session expirée/révoquée, accès suspendu |
| `origin_denied`, `csrf_denied` | 403 | Origine, header bootstrap ou preuve CSRF invalides |
| `permission_denied` | 403 | Lecture permise mais opération non accordée |
| `colony_not_found`, `order_not_found` | 404 | Hors scope, sans lecture ou inconnu |
| `invalid_request` | 415/422 | Type de contenu, corps, champ ou infrastructure inconnus |
| `queue_full`, `sector_unavailable`, `unique_limit`, `prerequisites_unmet`, `insufficient_resources` | 409 | Règles 5A |
| `order_completed`, `idempotency_conflict` | 409 | Annulation tardive, clé réutilisée |
| `colony_busy`, `temporarily_unavailable` | 503 | Événement bloqué/budget de rattrapage, base indisponible |

Q39, arbitrage du 31/10/2026 : l’annulation reste possible ; crédit plafonné par ressource, excédent
perdu définitivement. La projection `cancel.refund` contient le théorique agrégé, `recoverable` le
crédit possible et `lost` la perte (chaînes de micro-unités), avec `also_cancels` pour toute la cascade.
Même calcul pur en projection et commande ; application sous verrou après rattrapage, reçus
`order.refunded` contenant le réel, replay par identité d’ordre sans second crédit. L’annulation
n’utilise pas de nouvelle clé client : un retry après réponse perdue vise le même ordre.

## UI Colony (frontend Game)

`useColony` lit la liste puis la projection de la colonie (GET, jamais activité), applique
seulement des réponses plus récentes (`server_time` monotone, générations, abort) et n’envoie une
commande que sur clic explicite, une à la fois. Clé d’intention conservée après une issue inconnue
(timeout, réseau, 5xx) pour qu’un retry ne crée jamais un second ordre ; un refus 4xx clôt
l’intention puis relit la colonie. Un 401 relit la session C07, qui affiche l’expiration et le retour
lobby. La barre d’avancement est une projection visuelle des dates serveur ; à l’échéance, une
lecture légère est déclenchée (puis 3/10/30 s si le worker tarde, ensuite bouton explicite) : jamais
d’achèvement côté client ni de polling permanent.

Sous-navigation Vue d’ensemble / Infrastructures / Orbite / Défense. Vue d’ensemble : stocks et
capacités, production, alertes dérivées des valeurs serveur (stock ≥ 90 %, file pleine, aucun
secteur libre), file et résumé tabulaire. Infrastructures : file avec avancement et annulation
confirmée (théorique, récupérable, perte définitive et liste détaillée de la cascade affichés), infrastructures existantes avec
amélioration, nouvelles infrastructures avec coût, durée de base/effective, secteur libre choisi,
bouton désactivé et raison serveur si indisponible. Orbite et Défense restent des états futurs
explicites, sans bouton ni donnée inventée. Top bar : stocks et production de la colonie ; Empire
affiche la colonie réelle et sa construction en cours. Aucun élément illustratif des mockups
(population, défenses, accélération, bâtiments hors catalogue) n’est implémenté.

Responsive vérifié 320/390/768/1440 en Chromium : pas de débordement horizontal, boutons ≥ 44 px,
centre de chaque bouton réellement atteignable dans le viewport (barre mobile fixe compensée par
`scroll-padding-bottom`), clavier sur construction/annulation et sous-navigation.

## Recette réelle et résilience Portal (D08)

`python3 scripts/smoke_colony_compose.py` (après build des images de l’arbre courant ; job CI
compose-smoke) crée un projet Compose aléatoire sans port hôte, bases `echosphere_colony_*_test`,
puis : compte de test et Universe provisionné par Portal via mTLS, graphe Colony de référence par
`scripts/colony_game_fixture.py` (refusé hors de sa base dédiée ; vitesse de construction ×60 de
l’instance pour finir en secondes, règles v0.1 sinon identiques), binding Empire par
`SetUniverseAccess`. Chromium réel 390 px (`scripts/colony_browser.mjs`, sans interception) :

1. login Portal → lobby → handoff signé → shell Game ;
2. construction d’un Nœud de données : ordre réel, Alliages réservés immédiatement ;
3. page fermée ; le coordinateur constate en base que le worker termine l’ordre ;
4. nouvelle page : niveau/production mis à jour (Données 120/h), action suivante acceptée ;
5. arrêt réel de Portal API et du worker de contrôle (`/api/ready` Portal ≥ 500) : colonie relue,
   nouvelle construction acceptée, worker qui achève amélioration et réacteur, aucune requête
   vers l’origine Portal pendant la séquence ;
6. Q39 : worker arrêté et stockage rempli uniquement dans la base jetable, nouvel ordre puis
   saturation ; UI théorique/récupérable/perte avant confirmation, annulation à capacité et replay
   de l’ordre sans nouveau crédit ; aucun appel Portal ;
7. échéance de session atteinte (échéance absolue ramenée juste après la dernière activité dans la
   base de test) : commande refusée, UI d’expiration, lecture 401.

Le projet et ses volumes sont supprimés ; la pile conservée n’est pas touchée.

## Données de partie et tests

Aucun parcours produit ne crée encore une partie : les tests et recettes créent Universe (provision
C06), économie, Empire, planète et colonie de référence uniquement dans des bases `*_test`, puis
lient l’Empire par `SetUniverseAccess`. Tests : `backend/tests/integration/test_colony_api.py`,
`frontend/src/Colony.test.tsx`, `frontend/e2e/colony.spec.ts` (API interceptée).
