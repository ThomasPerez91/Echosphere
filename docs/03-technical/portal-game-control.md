# Lobby et interface interne Portal→Game — C06 de 5C

**Statut : implémenté sur work/step-5c-portal-account-lobby / PR #7, non intégré à master.**
2026-10-30, Codex local ; instruction utilisateur « Continue » après C05.
[Contrats 5B inchangés](identity-contracts.md) · [ADR 0008](../adr/0008-control-plane-game-data-plane.md) ·
[Plan 5C](../05-project/step-5c-plan.md) · [MFA C05](portal-mfa.md).

## Périmètre et frontières

Portal conserve références d’univers, intention de membership et livraison. Game conserve Universe,
droits effectifs, bindings explicites et marqueurs de révocation. Aucun SQL Portal→Game, FK entre
bases, import de modèle Game en Portal ou credential Accounts dans Game. Le worker de contrôle
Portal utilise son pool Accounts ; l’adaptateur privé Game son pool Game. Le worker temporel reste
indépendant et ne prend aucun verrou d’identité. Aucun handler économique ou game_data modifié.

Le lobby affiche uniquement les participations réelles du compte connecté, vide sinon. Une seule
participation compte/univers ; aucun plafond de memberships déduit des limites de sessions. État
souhaité distinct de l’acquittement ; pending ne signifie jamais applied. Suspension/révocation et
expiration sont visibles, avec date du dernier contrôle. Aucune entrée dans Game n’est disponible
avant **C07 handoff/GameSession**. Aucun endpoint Colony avant 5D.

Pas de catalogue public, invitation, join/leave, démarrage jouable, Empire/monde/IA de démonstration
ou règle de partage inventée. ProvisionUniverse crée seulement le conteneur Universe name/seed ;
aucune galaxie, colonie ou économie implicite. L’interface peut référencer explicitement des empires
existants, mais aucun parcours joueur de partage/spectateur n’est livré. Q21 et Q19–Q29 restent ouverts.

## Listener privé, mTLS et identité de service

Processus **game-control** du même backend Game, commande `python -m app.control.http`, port TLS
9443 uniquement sur réseaux Docker, aucun port hôte publié. L’application publique app.main ne monte
aucune route /internal ; headers X-Control-Service/X-Client-Cert/X-Forwarded-Proto ne confèrent aucun
droit. Aucun proxy ne termine le TLS de ce listener ; proxy_headers=False, access_log=False.

TLS exige un certificat client chaîné vers la CA Portal dédiée, puis le protocole HTTP H11 de la
version Uvicorn figée extrait l’empreinte du certificat **depuis la connexion TLS vérifiée**. Seules
les empreintes autorisées donnent le principal portal-control ; scheme HTTPS et identité vérifiées
avant lecture d’un résultat. Même un autre certificat signé par la CA attendue est refusé en HTTP
403 s’il n’est pas épinglé. Autorisation explicite des opérations pour ce service, sur les univers de
ce Game Backend ; aucun service tiers, service en lecture seule ou délégation publique implicite.
Le listener est fermé si le fichier d’identité attendu est absent. Adaptateur H11 couvert par recette
réelle, à vérifier lors d’une mise à jour Uvicorn.

Portal vérifie CA serveur et nom DNS, présente son propre certificat client ; HTTPX utilise un contexte
SSL explicite, trust_env=False, aucune redirection ou fallback HTTP/verify=False. Les destinations
viennent uniquement de PORTAL_CONTROL_TARGETS (JSON ID→origine HTTPS), jamais d’une URL de requête
ou de la base. Configuration initiale : primary→https://game-control:9443. Les IDs sont stables ;
retirer/renommer une cible alors qu’une livraison est pending exige traitement opérateur, pas abandon.

PKI **de développement** générée par control-tls-init : CA serveur et CA client distinctes dans
control_ca ; clés CA root privées uniquement dans ce processus ponctuel. Volumes game_control_tls
et portal_control_tls séparés, clés de feuilles privées 0600, montages workloads en lecture seule ;
Game ne reçoit pas la clé privée du client Portal. CA/certificats publics seulement échangés. Les
clés email/TOTP sont encore distinctes ; pas de clé de handoff avant C07. Aucun secret Git/VITE ou
installation de confiance CA sur l’hôte.

Feuilles 30 jours, CA locales 10 ans, aucun écrasement/renouvellement implicite ; expiration ou
incohérence bloque l’initialisation. Renouvellement/remplacement de clés et redémarrage sont des
opérations explicites, à préparer dans la recette C09 ; pas de PKI production prétendue. Game peut
accepter une seconde empreinte via CONTROL_NEXT_PEER_CERT pour une rotation avec recouvrement.
Configuration de production/domaines/sauvegarde/rotation demeure un prérequis de déploiement Q49.

## Contrat versionné et transactions Game

[Schéma pur v1](../../contracts/portal-game/v1.schema.json), généré depuis les DTO d’admission Game et
comparé par test. Enveloppe JSON : version=1, operation_id UUID stable, message discriminé par kind.
Champs supplémentaires et types/statuts/dates invalides refusés, corps borné à 64 Kio. Les schémas
n’importent ni ORM ni credentials. Portal sérialise ce contrat indépendamment, sans dépendance au
package Game ; la recette HTTP valide l’interopérabilité réelle des deux applications.

| Opération / route privée | Contrat C06 |
| --- | --- |
| POST /internal/v1/operations — provision_universe | UUID/name/seed explicites ; conteneur seul, conflit si UUID avec autre contenu |
| Même route — set_universe_access | Snapshot complet membership/compte/univers, révision, access_epoch/account_epoch, état, dates absolues et bindings |
| Même route — revoke_sessions | Compte ou appareil, génération monotone ; marqueur persistant même sans accès préexistant |
| GET /internal/v1/operations/{id} | Résultat immuable du service, opération et empreinte de contenu ; auth avant lookup |
| GET /internal/v1/access/{membership_id} | Snapshot effectif, lecture sans renouvellement |
| GET /internal/v1/health | Santé du listener authentifié, pas un accès anonyme public |

États active/suspended/revoked. Permissions distinctes colony.read/colony.construct/colony.cancel,
aucun droit implicite d’administrateur/créateur ; liste vide sans Empire signifie aucun droit Colony.
Game vérifie chaque Empire dans le même univers ; FK composites GameAccess/univers et Empire/univers
sur EmpireBinding. Pas de Empire.owner_user_id ni contrainte fermant Q21.

Ledger control_operations : principal de service + operation_id, SHA-256 du JSON canonique validé,
résultat et effet dans **la même transaction Game**. Même clé/contenu : même résultat immuable ;
autre contenu : 409. Verrou transactionnel de déduplication puis GamePrincipal ; l’ordre futur est
identité/accès avant EventStream, jamais un lock d’identité depuis un handler temporel. Provisionnement
verrouillé par UUID d’univers. Aucune transaction distribuée.

Révision plus basse ignorée et résultat superseded avec état effectif ; révision égale contradictoire
refusée ; génération d’accès jamais abaissée. Changement d’état/bindings exige une génération supérieure,
réactivation comprise. Renouvellement à droits identiques augmente seulement la révision de livraison,
sans invalider les autres sessions futures. Tombstones/ledger/epochs ne sont pas purgés avec l’audit
90 jours. À C07, sessions et tickets devront vérifier ces générations ; aucun ancien ticket restauré.

portal_confirmed_at est une date serveur Portal, valid_until au plus huit heures après, jamais
réception +8 h. Confirmation future refusée. Message retardé expiré peut être enregistré, sans rendre
son accès temporel valide ; le lobby le marque expiré. Livraison/retry/lecture/réconciliation ne
renouvellent aucune date. Les commandes et GameSessions ne sont pas encore implémentées : C07/5D
devront appliquer ces bornes et générations localement, sans appel Portal par commande.

## Intention, outbox, acquittement et réconciliation

Portal alloue révision/génération sous verrou User, partagé avec opérations sensibles C03–C05, et
committe membership + snapshot complet + ControlOutbox ensemble. Le contenu/digest/opération ne
changent jamais pendant les retries. Workers concurrents prennent les livraisons avec SKIP LOCKED.
Timeout/réponse perdue : même opération ; dès la seconde tentative, consultation du résultat avant
rejeu éventuel. Retry exponentiel 2→60 s, aucune erreur distante transformée en succès ; défaut
permanent visible comme pending/last_error minimal, sans credential/payload dans les logs.

Un receipt doit correspondre à opération/digest/scope/révision/contenu. Acquittement et projection
sont dans une transaction Accounts ; reçu contradictoire rollbacké. Réponse ancienne ne rabaisse pas
la projection acquittée. Le résultat historique d’une ancienne opération n’est pas un état temps réel.

Réconciliation : éligibilité au contrôle après 60 s configurables, GetAccessRevision authentifié ;
traitement borné par boucle, aucune latence maximale de livraison garantie. État inférieur ou
absent : nouvelle livraison du **même snapshot/révision/dates**, sans renouvellement. État supérieur
ou contradictoire : pending, aucune adoption de cet état comme nouvelle intention Portal ni abaissement
forcé de Game ; investigation opérateur. Panne réseau : aucune confirmation inventée. Les GET du
lobby montrent un état daté, pas une garantie de disponibilité instantanée de Game.

Les sources C03 LogoutRequest et C04/C05 AccountRevocation restent atomiques avec la révocation locale.
Le worker matérialise leur fan-out durable par cible configurée, FK explicites/unicités par source et
cible. Elles ne deviennent acknowledged qu’après **toutes** les cibles acquittées ; une source déjà
matérialisée mais pending ne bloque pas la matérialisation des suivantes. Générations compte/appareil
indépendantes et monotones dans Game. Une panne ne remet aucune fenêtre de huit heures à zéro.

C06 applique les marqueurs compte/appareil ; révocation de membership via son snapshot complet.
La révocation d’une GameSession précise et son branchement effectif restent C07, aucune table de
session factice créée. Le lobby connecté peut afficher pending/acknowledged des révocations ; le
message après logout reste prudent en attente. Suivi anonyme après fermeture du cookie et parcours
complet de fin de déconnexion à compléter avec C07/C08, aucun accès compte grâce à une ancienne session.

## Stockage et exploitation

Accounts **p0005_control** : universe_references, universe_memberships, control_outbox. Références
sans FK distante ; bindings souhaités en snapshot, Game seul valide leur existence/scope. Game
**0005_game_access** : game_principals, game_devices, game_accesses, empire_bindings, control_operations.
Générations, contraintes et FK locales ; révisions précédentes inchangées. Downgrade peuplé refusé,
roundtrips seulement sur bases *_test, aucune suppression de données à conserver.

Processus portal-control-worker : `python -m portal_app.control.worker [--once --limit 50]`, pools et
réseaux séparés du worker mail ; aucune clé email/MFA nécessaire à cette livraison. Concurrency privée
32, timeout HTTP 3 s, paramètres techniques initiaux ; aucune preuve de charge/DDoS annoncée.
PORTAL_CONTROL_POLL_SECONDS=2, PORTAL_CONTROL_RECONCILE_SECONDS=60 ; IDs de cibles configurés stables.
Aucun port interne publié, aucun accès réseau Portal→PostgreSQL Game.

Orchestration technique réservée à un opérateur disposant du processus/DB Accounts ; aucun endpoint
public de création/join ni console admin. Identifiants réels explicites, aucun défaut de permissions :

```bash
docker compose exec portal-backend python -m portal_app.control.operator provision \
  --universe-id <uuid> --backend primary --name <nom> --seed <seed>
docker compose exec portal-backend python -m portal_app.control.operator set-access \
  --user-id <uuid-compte-existant> --universe-id <uuid> --status active --bindings '[]'
```

Pour référencer un Empire existant, fournir explicitement son UUID et les permissions dans --bindings ;
un UUID d’un autre univers est refusé par Game. Ces commandes n’inventent ni règles de démarrage ni
une partie jouable et ne sont pas exécutées automatiquement sur les bases conservées.

GET public /api/lobby/memberships : PortalSession normale, bootstrap/Origin exacts, no-store ; uniquement
son compte. Aucun accès par cookie de récupération MFA ou profil seul. Lecture automatique sans
activité ; bouton « Actualiser mes parties » passe par l’action explicite C03 avant relecture.
Aucune lecture ou activité ne renouvelle GameAccess. États vides/erreur/pending/confirmé/suspendu/révoqué/
expiré, clavier/mobile ; noms longs repliés sans débordement. Aucun secret en stockage navigateur.

## Recette et limites

Suites Game/Portal : doublons concurrents, désordre, contradiction, scopes/FK, rollback, révisions et
générations, fan-out, receipt perdu/invalide et réconciliation. Frontend : états réels de projection,
rafraîchissement explicite, erreurs privées masquées et Chromium 320/1440 ; API interceptée distincte
de la recette de transport réel.

`python3 scripts/smoke_control_compose.py` crée deux bases *_test, un listener Game et un réseau privés
temporaires. Fixtures de compte uniquement dans Accounts de test ; **le processus client Portal ne
se connecte jamais à Game DB**. Vérifie mTLS valide, client absent/mauvaise CA/certificat non épinglé
(même CA)/nom serveur incorrect/header forgé refusés ; contrat invalide/corps trop grand refusés ;
livraison réelle provisionnement/accès, réponse perdue, résultat récupéré, ancien grant sans résurrection,
révocations et réconciliation. Retire uniquement ses bases/conteneur/réseau/volume de test, conserve
les volumes courants. Smokes Game et Portal/TLS restent distincts. Résultats exacts dans progress/CI.

Pas de handoff/GameSession, commande Colony, navigateur complet HTTPS→partie, PKI/rotation production,
charge hostile ou reprise après perte physique de données attestés. C07 puis C08/C09 restent nécessaires ;
Q48/Q49/Q55 et règles des modes/partage conservés. **5C non terminé, 5D non commencé, PR #7 non fusionnée.**

Références primaires : [Uvicorn TLS](https://www.uvicorn.org/settings/#https),
[Python SSL](https://docs.python.org/3.12/library/ssl.html),
[HTTPX SSL](https://www.python-httpx.org/advanced/ssl/),
[Cryptography X.509](https://cryptography.io/en/latest/x509/tutorial/).
Les décisions produit restent celles des contrats 5B, non celles de ces bibliothèques.
