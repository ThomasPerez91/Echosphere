# Contrats API

**Statut : Game public = sondes et contexte/sessions C07 ; Portal C01–C07 et interface privée mTLS livrés sur PR #7, non intégrés ; gameplay futur.**
[Routes C02, erreurs et protections](portal-registration.md). [Routes C03](portal-sessions.md), sessions/CSRF et logout ; [C06 lobby/mTLS](portal-game-control.md) livré, [C07 handoff/GameSession](game-handoff.md) livré sur PR #7.


| Endpoint backend | Succès | Échec attendu | Utilité |
| --- | --- | --- | --- |
| GET /health | 200, `{"status":"ok"}` | Échec processus/HTTP | Liveness sans accès DB |
| GET /ready | 200, `{"status":"ready"}` | 503, `{"detail":"Database unavailable"}` | Connexion PostgreSQL et SELECT 1 |
| GET /docs | Documentation OpenAPI FastAPI | — | Développement local |

`/ready` utilise un délai de connexion de 3 secondes et un statement timeout de 3 secondes.
Les détails de connexion ne sont pas renvoyés. Aucune authentification ni donnée personnelle. Aucun endpoint métier public ne contourne ce manque.
Le frontend appelle `/api/ready`, relayé par Vite sur `/ready`.

## Futurs contrats

Les routes métier ne sont pas encore créées. Elles valideront identité, droits sur l'empire,
appartenance à l'univers et état des commandes. Ne jamais accepter les stocks, coûts, taux ou dates
de fin calculés par le client comme autorité. Définir pagination, erreurs structurées et clé
idempotente des commandes avant les premières mutations. Contrat logique d’erreur dans [identity-contracts](identity-contracts.md), schéma détaillé délégué.

Les réponses seront des projections filtrées selon la connaissance. Aucun endpoint « carte entière »
exposé puis masqué côté UI. L'affichage d'échéances nécessite des timestamps absolus UTC avec offset,
convertibles localement. WebSockets hors étape 0 ; polling futur seulement si besoin établi.


## Frontière d'instance et future participation

Universe isole les données de partie ; ne pas supposer un univers par utilisateur ou par processus.
Toute future API authentifiée contrôle User → Membership → Universe → permissions → Empire/Entity,
puis filtre aussi les informations selon le fog of war. Aucune donnée d'un autre univers ne doit
être lisible/modifiable via un identifiant d'entité fourni par le client. Un UUID opaque n'est pas
une autorisation. Les primitives génériques de stream exigent universe_id et vérifient son scope ;
les adaptateurs internes de colonie ne sont pas des routes HTTP et n'authentifient pas un joueur.

Account/User ↔ UniverseMembership ↔ éventuellement Empire ↔ rôle/permissions reste conceptuel ;
C02 crée le compte en Accounts DB seulement ; aucun membership ou owner_user_id Game. controller_type human/ai n'est
pas un droit d'accès. Règles gameplay futures par instance/ruleset ; aucune présence de navigateur
nécessaire à la progression. Notifications/WebSockets futurs restent des projections, jamais autorité.
[Modes](../01-game-design/game-modes.md) · [ADR 0006](../adr/0006-universe-game-instance.md).

## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Contrats Portal/Game validés en 5B — C02–C07 partiellement implémentés

[identity-contracts](identity-contracts.md) porte les autorités, opérations internes, handoff,
sessions, erreurs et règles compte/MFA validés le 2026-10-29. Le [registre Q40–Q56](../05-project/open-questions.md)
distingue contrats clos, détails techniques délégués et reports. Game expose les sondes et [C07 handoff/sessions/contexte](game-handoff.md), sans gameplay. Portal ajoute les sondes C01 et les
[routes d’inscription/vérification C02](portal-registration.md), et les [sessions C03](portal-sessions.md), sans route gameplay. 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`) ; contrats partiellement implémentés par C02–C07 sur PR #7.

Portal expose les services compte/lobby dans le périmètre C02–C07. Après ticket signé 60 s/unique lié au navigateur,
GameSession opaque : accès direct Game, sans proxy ni consultation Portal par commande. Game vérifie
session → accès/membership/univers → permissions/binding Empire → propriété/visibilité, puis
revalide les droits dans la transaction d’acceptation d’une commande.

Interface interne privée mTLS, autorisée par service/opération ; aucune écriture SQL Portal→Game DB.
Contrat de livraison : intention/outbox Portal, effet/résultat idempotent Game, révisions ordonnées,
retry/acquittement/réconciliation, révocations ciblées et absence de résurrection par ancien ticket.
Noms d’opérations et erreurs logiques dans le canonique ; URLs/OpenAPI/schémas détaillés délégués
à 5C/5D avant code dépendant. Aucun join privé/persistant ajouté par implication.

Chaque frontend utilise son API même origine ; CORS credentials refusé par défaut, exception sur
besoin explicite et allowlist minimale. CSRF, cookies host-only Secure/HttpOnly, protections du
POST de handoff et activité explicite classée côté serveur sont des protections C03/C07 implémentées sur PR #7 ;
leur configuration production reste à recetter. Aucun secret localStorage.

5C compte/lobby est le lot courant autorisé ; cadrage avant code substantiel. 5D API Colony/UI
protégée reste hors lot et nécessitera son instruction distincte. Tests futurs
et prérequis opérationnels sont référencés dans la matrice du canonique ; aucun test d’auth réalisé
par la rédaction. [ADR 0008](../adr/0008-control-plane-game-data-plane.md).

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
