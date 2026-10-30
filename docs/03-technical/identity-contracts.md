# Identité et contrats Portal/Game — étape 5B

**Statut : contrats 5B validés ; C02–C05 comptes/sessions/opérations sensibles et MFA implémentés sur PR #7.** Consolidation : 2026-10-29.
Source : arbitrages utilisateur explicites pour PR #6, puis validation du bloc complet en quatorze
points avec trois corrections : effets MFA ciblés, plafonds de sessions configurables et CORS refusé
par défaut. Cette synthèse conserve les décisions, sans transcript privé.
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) porte la séparation des plans ; le présent
contrat la précise. Les décisions closes, détails techniques délégués et reports sont distingués
pour chaque Q40–Q56 dans le [registre](../05-project/open-questions.md).

5B documentaire terminé et intégré à master via PR #6, merge `63bb7d1` le 2026-10-29. Aucune route,
table, migration, dépendance, application Portal, MFA ou GameSession n’est livrée par 5B. 5C est le
lot courant autorisé ; premier checkpoint documentaire avant code. 5D reste distinct et non commencé.

État d’implémentation : [C02](portal-registration.md) livre inscription/Argon2id/vérification initiale
et email durable local ; [C03](portal-sessions.md) ajoute sessions/CSRF et intentions de logout.
[C04](portal-account-security.md) et [C05](portal-mfa.md) livrent les opérations sensibles, MFA et
récupération limitée ; lobby, livraison Game et handoff restent futurs. Ce statut ne modifie aucune décision 5B.

## 1. Autorités et modèle logique validés — Q51/Q52/Q53

| Propriétaire | Données et responsabilités | Frontière |
| --- | --- | --- |
| Portal / Accounts DB | User, credentials, MFA, récupération, sessions Portal, intention de membership, livraisons et révocations à effectuer | Aucun SQL Game DB ni décision économique |
| Game / Game DB | Univers et gameplay, accès effectifs, bindings d’Empire, GameSessions, consommation des tickets et résultats idempotents | Aucun email, hash de mot de passe, secret MFA ou cookie Portal |
| Navigateur | Intentions et choix de partie | Aucun calcul autoritaire de droit, coût, production ou date |

Compte global → UniverseMembership → Universe → éventuellement Empire/rôle/permissions. Le
`global_user_id` ne dépend jamais de l’email, de la méthode de connexion ou d’un facteur MFA.
Une participation par compte/univers dans la fondation MVP ; aucun plafond de memberships déduit
des limites de sessions. Identifiants externes opaques, sans FK SQL entre les bases.

Portal possède l’intention d’accès ; Game son application locale. Le lobby distingue `pending` et
`applied`, et ne confond jamais envoi et acquittement. Game vérifie l’existence et le scope des empires.

| Objet conceptuel | Contrat | Détail technique délégué |
| --- | --- | --- |
| User | Identité globale et état de compte côté Portal | Tables et schémas Accounts |
| UniverseMembership | Participation stable compte/univers et état souhaité | Révisions et allocation transactionnelle |
| GameAccess | État effectif, validité, références de participation et permissions locales | Champs, index et compteurs de sécurité |
| EmpireBinding | Association explicite à un Empire du même univers | Stockage et représentation des permissions |
| GameSession | Compte, appareil, participation/univers, preuve de session et échéances | Identifiants, empreintes et contrôles de génération |

Accès `active`, `suspended` ou `revoked` ; l’expiration de `valid_until` refuse l’accès même si l’état
reste actif. Une suspension appliquée interdit nouveaux handoffs et commandes, sans détruire l’Empire
ni arrêter la simulation. Une réactivation exige une nouvelle décision Portal et un nouveau handoff ;
elle ne ressuscite aucune ancienne session. Les traces minimales de révocation empêchent un ancien
grant de rétablir un accès après purge ou livraison retardée.

La fondation distingue consultation, construction et annulation (`colony.read`, `colony.construct`,
`colony.cancel` comme noms techniques). Aucun privilège gameplay implicite pour un administrateur
plateforme ou le créateur d’une partie. Partage d’Empire et spectateurs non livrés par implication :
Q21 et les questions de modes restent ouvertes, sans contrainte `Empire.owner_user_id` unique.

Chaque requête Game contrôle : session → accès actif/membership/univers → permissions/binding →
propriété et visibilité de l’entité. Pour une commande, les droits sont revérifiés dans la transaction
d’acceptation. Le détail de sérialisation est délégué : verrou d’accès avant EventStream métier,
même verrou pour la révocation, sans appel Portal dans la transaction. Les handlers temporels ne
prennent pas ce verrou d’accès ; transactions déjà acceptées et progression suivent leur contrat.
Les futures mutations multi-streams restent Q13.

## 2. Interface interne, convergence et révocation — Q44/Q46/Q53/Q54

Décisions validées : réseau interne privé, authentification **mTLS** et autorisation par service et
opération. Un réseau privé seul ne prouve pas une identité. Si TLS termine sur un proxy, seules ses
assertions authentifiées sont admises, les headers clients sont supprimés et l’accès direct est
interdit. CA, certificats, rotation, limites et topologie concrète sont des détails délégués avant usage.

Portal persiste intention et livraison dans une transaction Accounts (outbox). Game persiste effet,
clé de déduplication et résultat dans une transaction Game. Aucun commit distribué ni SQL Portal→Game.

Contrat technique délégué pour matérialiser ces garanties :

- opérations logiques `ProvisionUniverse`, `SetUniverseAccess`, `RevokeSessions`,
  `GetOperationResult` et `GetAccessRevision` ; URLs et schémas seront définis avant implémentation ;
- enveloppe versionnée, identifiant d’opération stable, scope et contenu strictement validés ;
- authentification et autorisation avant consultation d’un résultat idempotent ;
- même service/clé/contenu : même résultat, sans nouvel effet ; contenu différent : conflit ;
- états d’accès complets et révisions monotones allouées sous transaction Portal, renouvellements inclus ;
  révision inférieure ignorée, identique contradictoire refusée ;
- retry après timeout avec même identifiant et même contenu ; acquittement perdu récupérable par
  consultation ou rejeu ; réconciliation sans abaissement des révisions ;
- un ancien renouvellement arrivé tard ne décale jamais son échéance absolue.

Les portées de révocation sont distinctes : une GameSession, un appareil du compte, tout le compte,
ou un membership. Le ciblage et ses compteurs sont délégués : une génération globale de compte,
une génération d’appareil et une génération d’accès peuvent matérialiser les portées, avec révocation
directe d’une session. Une génération de membership commune à tous les appareils ne peut pas servir
au logout d’un seul appareil. Révisions de livraison et générations de sécurité ont des fonctions
distinctes ; un renouvellement à droits inchangés ne révoque pas les autres sessions valides.

Handoff, renouvellement et révocation sont sérialisés : un ancien ticket ou message ne rétablit pas
une session après une révocation déjà appliquée. Les générations requises et leur diffusion sont
vérifiées localement par Game. Les courses exactes, schémas et preuves de concurrence sont délégués.

Toute révocation distante est persistée et retentée jusqu’à acquittement. L’UI indique terminée ou
encore en attente sur certains services. Aucun succès distant instantané n’est annoncé si Game est
injoignable. Une session non informée reste bornée par ses échéances existantes, au maximum huit
heures depuis la dernière confirmation Portal ; la révocation ne relance jamais cette fenêtre.

Join reste une orchestration respectant les règles du mode : aucun join privé/persistant public
ajouté pour rendre les opérations internes exécutables.

## 3. Handoff et clés — Q42/Q56

Décision validée : ticket signé asymétriquement, validable localement par Game, au plus **60 secondes**,
à usage unique. Pré-authentification Game liée au navigateur : **cinq minutes maximum**.
Format, bibliothèque, algorithme, claims détaillés et tolérance d’horloge sont délégués ; aucune
tolérance ne peut prolonger les 60 secondes ni l’échéance d’accès.

1. Game crée un état aléatoire de pré-authentification lié à un cookie host-only. L’état ne peut pas
   être fixé par un lien client ; destinations Portal/Game en allowlist serveur.
2. Portal vérifie session, CSRF, compte actif, email vérifié et membership active déjà acquittée.
   Le ticket lie compte, appareil, participation, univers, destination, validité et état navigateur,
   ainsi que les révisions/générations nécessaires contre les anciens droits.
3. Retour par POST vers l’échange Game ; aucun ticket dans query/fragment, historique, localStorage,
   analytics ou logs. Réponses `no-store`, referrer restrictif, aucune ressource tierce au transfert.
4. Game contrôle schéma, signature, émetteur, audience, type, dates, état et cookie lié ; algorithmes
   autorisés côté serveur, aucune URL de découverte choisie par le ticket. Le ticket ne crée pas de
   droits absents de Game DB et ne remplace pas silencieusement une session d’un autre compte.
5. Sous transaction et verrou d’accès : vérification des droits courants, consommation atomique de
   l’identifiant unique et de l’état navigateur, création de session. Un seul échange concurrent réussit.
6. Cookie Game puis redirection vers URL propre. Réponse perdue après commit : nouveau parcours,
   jamais réutilisation du ticket consommé.

Ni email ni credential Accounts ni permissions client faisant autorité dans le ticket.
Refus dès `now >= exp`. Le choix des claims et index réalise ces garanties sans API permissive.

Les clés publiques sont prédistribuées à Game avant usage. Clé inconnue : refus local, sans appel
synchrone Portal. Rotation avec recouvrement suffisant ; clé compromise retirée et sessions affectées
traitées par procédure de révocation. Clés de ticket et identités/certificats S2S séparés.

Portal en panne après émission : un ticket déjà émis reste consommable dans ses 60 secondes si tous
les contrôles locaux sont satisfaits ; une révocation reçue prime. Aucun nouveau ticket ni
renouvellement sans Portal disponible. Game DB indisponible : aucun fallback cache permissif.

## 4. Sessions, appareil, navigateur et échéances — Q41/Q43/Q47

Sessions opaques côté serveur ; secrets cryptographiquement aléatoires, empreintes seules en base.
Cookies Portal et Game distincts, `Secure`, `HttpOnly`, host-only ; aucun secret dans localStorage.
Rotation des identifiants aux transitions d’authentification, sans repousser les limites absolues.
Le choix concret de `__Host-`, `SameSite`, nommage par univers et hôtes locaux est délégué et doit
préserver CSRF, liaison navigateur et isolation. Les cookies ne sont pas isolés par port.

Chaque frontend appelle **sa propre API de même origine**. CORS avec credentials est refusé par
défaut ; aucune origine cross-origin autorisée sans besoin explicite. Une exception exige une
allowlist minimale et explicite. Deux origines Portal/Game distinctes du même site, sous contrôle,
constituent la cible. Le POST de navigation du handoff n’ouvre pas une API CORS avec credentials :
son contrôle d’origine Portal exact, état à usage unique et cookie pré-auth Game sont spécifiques.
Toutes les mutations à cookie vérifient leur protection CSRF et leur origine attendue. Un autre
site de déploiement nécessiterait une recette adaptée avant activation, sans désactiver ces garanties.

### Appareil et simultanéité

« Cet appareil » désigne **un profil de navigateur**, rattaché côté serveur de manière sécurisée.
Deux navigateurs sur le même ordinateur sont deux appareils ; les onglets d’un profil partagent le
rattachement. Ni empreinte matérielle ni adresse IP seule. Effacer les cookies ne révoque pas les
anciennes sessions serveur, qui restent visibles et révocables dans la gestion des sessions.

Paramètres techniques initiaux **configurables**, jamais invariants produit : **10 appareils connectés
par compte**, **10 univers Game simultanément ouverts par appareil**. Ils comptent les sessions
actives, jamais les memberships ou univers auxquels le compte appartient. Une GameSession active
par compte/appareil/univers, partagée entre ses onglets. À la limite : demander explicitement de
fermer une session, aucune déconnexion silencieuse. Comptage concurrent, nettoyage des cookies et
des sessions expirées, rattachement inter-origines et stockage sont délégués à 5C/5D.

### Limites et autonomie

| Objet | Limite validée |
| --- | --- |
| PortalSession | 7 jours absolus ; 72 heures d’inactivité |
| GameSession | 8 heures absolues ; 2 heures d’inactivité ; GameAccess peut expirer plus tôt |
| GameAccess | Au plus 8 heures depuis la dernière confirmation Portal |
| Renouvellement | Portal disponible et nouvelle confirmation/handoff valide |

```text
portal_deadline = min(portal_created_at + 7 jours, portal_last_activity_at + 72 heures)
access_valid_until <= portal_confirmed_at + 8 heures
game_deadline = min(game_created_at + 8 heures, game_last_activity_at + 2 heures,
                    access_valid_until)
```

UTC et dates serveur. Seules les interactions explicites réinitialisent l’inactivité : navigation
volontaire, commande/action, réglage modifié/sauvegardé, actualisation demandée ou autre type classé
explicitement par le serveur. Polling, refresh périodique, heartbeat, réception WebSocket, reconnexion
automatique, prefetch, télémétrie et onglet ouvert ne comptent pas. Timestamp ou indicateur client
seul ne fait pas autorité ; la classification serveur ne constitue pas une preuve anti-bot.
Vérifier l’expiration avant activité : aucune résurrection d’une session expirée.

Aucune activité ne prolonge l’absolu ni `valid_until`. Un renouvellement des droits ne modifie pas les
échéances propres d’une session existante. Les droits ne repartent ni à leur réception ni au début
d’une panne. À échéance, nouvelles commandes refusées ; univers et workers continuent.

Exemples contractuels non testés : confirmation 08:00, livraison 10:00 → échéance au plus 16:00 ;
panne à 15:00 ou activité 15:59 → toujours 16:00. Session créée à 15:00 sous ces droits → refus à
16:00 au plus tard. Révocation/suspension reçue avant → application immédiate.

## 5. Déconnexions — Q45

| Action | Portée validée |
| --- | --- |
| Retour lobby / quitter l’écran de partie | Aucune déconnexion ; session conservable dans ses limites |
| Déconnexion Game | Seule GameSession concernée, univers et appareil/session courants ; autres sessions Game et Portal préservées |
| Se déconnecter du compte sur cet appareil | PortalSession courante et toutes les GameSessions du compte sur ce profil navigateur ; autres appareils préservés |
| Déconnecter tous les appareils | Action de sécurité distincte : toutes PortalSessions et GameSessions du compte, tous univers/appareils |

Le logout ordinaire n’exige pas de step-up. Le logout tous appareils suit la section 7. Effacer le
seul cookie Portal ne satisfait pas le logout appareil ; l’état en attente de Game est affiché.
Ces actions conservent memberships, empires et état gameplay, sans arrêter univers, workers ou
actions déjà acceptées. Mécanismes et courses suivent la section 2.

## 6. Compte, mot de passe et emails — Q40/Q49

MVP email + mot de passe ; Argon2id via bibliothèque maintenue. Politique validée : **15 à 128
caractères**, espaces autorisés, sans composition artificielle ni renouvellement périodique imposé.
Refuser les mots de passe courants ou compromis, sans en transmettre le texte brut à un tiers.
Bibliothèque, paramètres mesurés, corpus/mécanisme de vérification et transactions sont délégués.
Google/OIDC reste une méthode supplémentaire future du même compte, sans dépendance MVP.

### Vérification initiale

Lien unique **24 heures**, réémission invalidant les précédents. Compte non vérifié : fonctions
Portal nécessaires à la vérification accessibles, aucun handoff Game. Demande/renvoi sans révélation
publique de l’existence d’un compte. Consommation et concurrence contrôlées côté serveur.

### Reset et changement de mot de passe

Récupération : jeton **30 minutes** maximum depuis émission, usage unique, expiration serveur.
Nouvelle émission : tous les anciens jetons encore valides du compte invalidés immédiatement ;
seul le dernier parcours peut aboutir. Demander un lien n’est pas réussir le reset.

Reset réussi : toutes PortalSessions invalidées, révocation de toutes GameSessions demandée, tous
appareils/univers ; tous jetons de récupération invalidés. Nouvelle connexion normale sans auto-login,
notification email de modification, aucun mot de passe envoyé. La MFA activée n’est pas contournée
ou désactivée par le reset. Game injoignable suit la reprise durable et la borne de huit heures.

Changement volontaire : réauthentification, avec MFA si activée ; après succès mêmes effets de
révocation et notification que le reset. Reset/changement de mot de passe ou récupération MFA
invalident les demandes de changement d’email en attente. Invalidation et émission/consommation
concurrentes doivent être atomiques, effets distants durablement repris.

### Changement d’adresse

Sans MFA : PortalSession valide, mot de passe actuel ressaisi, confirmation ancienne **et** nouvelle
adresses. Avec MFA : mot de passe actuel + step-up TOTP ou WebAuthn remplacent la confirmation de
l’ancienne adresse ; compte privilégié : WebAuthn requis. Confirmation de la nouvelle toujours
obligatoire. Un code de secours seul n’autorise pas directement ce changement : terminer d’abord
la récupération MFA. Sans accès à l’ancienne adresse ni preuve indépendante disponible, blocage ;
aucun contournement par mot de passe seul ou reset.

Une seule demande active par compte, **1 heure absolue depuis création**, échéance commune à ses
preuves, sans glissement. Nouvelle demande : ancienne demande, liens et confirmations acquis
invalidés ; aucune combinaison entre demandes. Le flux sans MFA exige deux nouvelles confirmations ;
le flux avec MFA exige les preuves de sa variante, sans héritage de l’ancienne demande.

La nouvelle adresse reste pending jusqu’à toutes les preuves et conditions satisfaites. Elle devient
ensuite active, sans changer global_user_id. Toutes PortalSessions et GameSessions révoquées,
session courante incluse, tous appareils/univers ; connexion normale avec nouvelle adresse.
Les anciens liens de récupération et de vérification du compte sont invalidés.
Notifier ancienne et nouvelle adresses sans credential/token sensible dans les notifications finales
(distinctes des emails de confirmation). Moyen de signalement « Ce changement n’est pas de moi » :
parcours de sécurité, aucun rétablissement automatique de l’ancienne adresse sur le seul lien reçu.
Memberships, empires et états conservés ; Game injoignable : reprise jusqu’à acquittement, pas de
révocation distante instantanée annoncée ni remise à zéro de la fenêtre de huit heures.

### Livraison et décisions différées

Fournisseur de production non choisi : contrat indépendant du fournisseur, livraisons persistées et
retentées, état d’envoi fidèle ; aucun faux succès. Choix du fournisseur, domaines et configuration
opérationnelle avant déploiement ; aucune souscription dans 5B. Un outil local de test ne dispense
jamais de la vérification en production. OIDC et récupération support renforcée restent des lots
séparés, sans méthode d’authentification ou de récupération inventée.

## 7. MFA, step-up et récupération — Q48

MFA facultative pour joueurs standards MVP, activable dans les paramètres ; exigée aux connexions
normales après activation. Aucun changement d’identité, memberships, empires, univers ou gameplay.

| Facteur / population | Règle validée |
| --- | --- |
| Joueur | TOTP, WebAuthn/passkey ou les deux |
| TOTP | Un seul secret actif par compte ; remplacement de l’ancien, aucune accumulation |
| WebAuthn | Jusqu’à cinq credentials par compte, chacun nommable |
| Administration/opération plateforme | WebAuthn obligatoire, aucune exemption interne ; TOTP seul insuffisant |
| Production privilégiée | Deux authentificateurs WebAuthn obligatoires avant activation des privilèges |
| Opération administrative sensible | Preuve WebAuthn avec vérification de l’utilisateur obligatoire |

Les rôles gameplay d’Empire ne sont pas des privilèges plateforme. TOTP reste un complément possible
pour un compte privilégié. Aucun endpoint ou console admin livré par ce contrat.

### Step-up

Une preuve **par action sensible**, **cinq minutes maximum**, à usage unique, liée côté serveur à la
session, à l’action et à ses paramètres importants. Ne prolonge ni session ni valid_until.
Catalogue obligatoire : changement d’email/mot de passe, ajout/suppression/remplacement/désactivation
MFA, régénération des secours et « Déconnecter tous les appareils ». Joueur équipé : mot de passe
actuel + facteur enregistré ; opération administrative sensible : WebAuthn avec vérification de
l’utilisateur. Sans MFA, réauthentification par mot de passe et preuves email applicables.
L’activation initiale ne peut exiger un facteur déjà enregistré absent ; la vérification du nouveau
facteur et la réauthentification doivent être garanties par le protocole d’enrôlement délégué.
La récupération après perte dispose du parcours limité ci-dessous.

### Effets MFA sur les sessions — correction utilisateur prioritaire

| Opération réussie | Effet sur PortalSessions / GameSessions |
| --- | --- |
| Activation initiale de la MFA | Révocation globale, session courante incluse |
| Désactivation MFA | Révocation globale |
| Remplacement ou suppression d’un facteur réduisant ou remplaçant la protection existante | Révocation globale |
| Récupération MFA après perte ou reset MFA par procédure de récupération | Révocation globale |
| Ajout d’un authentificateur supplémentaire avec step-up valide via facteur déjà enregistré | Aucune révocation globale imposée |
| Régénération volontaire des secours avec step-up valide via facteur déjà enregistré | Aucune révocation globale imposée ; anciens codes invalidés |

Toutes ces opérations sont sensibles, auditées et notifiées. Aucun effet global indistinct pour les
deux dernières lignes. Le traitement technique d’une modification ne doit pas utiliser un compteur
qui déconnecterait implicitement tous les comptes/appareils dans ces cas. Les révocations requises
suivent la section 2 et imposent une connexion normale après le parcours.

### Secours et récupération

**Dix codes**, au moins **128 bits aléatoires chacun**, usage unique, affichés uniquement à génération.
Génération à activation MFA ; régénération explicite invalidant tous les anciens. Stockage vérifiable
non réversible, aucun secret exploitable en clair, jamais journalisés. Autre facteur enregistré :
réauthentification normale permettant de remplacer celui qui est perdu.

Mot de passe + code de secours : **session de récupération limitée à quinze minutes**, sans accès
Game ni privilèges administratifs ; permet de rétablir un authentificateur, puis impose connexion
normale. Remplacement du jeu de secours après récupération et invalidation des anciens. Cette session
limitée ne maintient pas une session de jeu et ne prolonge aucune échéance précédente.

Perte de tous les facteurs et codes : aucun déblocage automatique ou support improvisé au MVP.
Compte bloqué jusqu’à une procédure renforcée distincte explicitement approuvée. L’email et le mot
de passe seuls ne contournent pas la MFA. Procédure finale support différée : décision ouverte hors
5B, à résoudre avant de proposer cette récupération.

Un compte privilégié en récupération ne retrouve jamais automatiquement ses droits : WebAuthn valide
réenregistré **et** procédure privilégiée approuvée satisfaite, avec exigences de production applicables.
Sans procédure disponible, pas de restauration des privilèges ; jamais bascule automatique TOTP seul.

Secrets TOTP chiffrés avec clés séparées de la base ; pour WebAuthn seulement les éléments nécessaires
à la vérification, aucun secret privé d’authentificateur. Crypto, bibliothèques, RP/origines, stockage,
anti-rejeu et schémas sont des détails techniques délégués ; configuration production avant déploiement.

## 8. Anti-abus, audit et isolation — Q50/Q53/Q54/Q56

Limites combinées par compte, IP et opération ; ralentissement progressif des échecs login/MFA,
quotas inscription et emails, réponses non énumérables. Aucun verrouillage permanent automatique
qu’un tiers peut provoquer. Aucun CAPTCHA tiers obligatoire au lancement ; ajout d’un prestataire
ultérieur = choix distinct. Seuils initiaux configurables, documentés et testés avant exposition
publique ; aucun WAF, Redis ou service payant ajouté implicitement.

Auditer authentification, changements de facteurs, récupérations et révocations ; jamais mot de passe,
secret TOTP, code de secours, ticket, cookie ou jeton CSRF. Rétention initiale sécurité **90 jours**,
accès restreint. Informations minimales empêchant le rejeu d’anciens droits conservées séparément,
sans purge automatique à 90 jours. Politiques de sauvegarde/purge détaillées avant production.

Observer retards de livraison/révocation, handoffs refusés, clés inconnues et opérations en attente.
Erreurs techniques déléguées : enveloppe structurée avec identifiant de requête et retry explicite,
401 session invalide, 403 accès refusé, 404 entité hors projection, 409 conflit, 422 contrat invalide,
429 limite et 503 indisponibilité. Refus publics de ticket génériques, motifs internes sans secrets.
Une mutation en timeout ne doit pas être retentée avec une nouvelle clé sans connaître son résultat.

CPU/RAM/pools/scaling/DB/réseau séparables ; budgets et recette opérationnelle avant exposition.
Saturer Portal sans épuiser Game doit être démontré, avec limites de l’hôte/réseau partagé consignées.
Aucun résultat de charge ni protection DDoS attesté par ce document.

## 9. Clôture documentaire et travaux délégués

Le [registre Q40–Q56](../05-project/open-questions.md) fait foi pour chaque clôture : contrat 5B clos
ne signifie jamais code livré ou sécurité testée. Q48 conserve la procédure support différée,
Q49 le fournisseur/configuration de production, Q55 les règles des modes futurs. Q16 a son cadrage
identité/autorisation couvert ; l’implémentation et les règles futures de Q21/Q19–Q29 restent distinctes.

Délégation validée : bibliothèques maintenues, paramètres Argon2id mesurés, schémas/messages,
algorithmes de signature, configuration WebAuthn, verrouillage, délais de reprise, rotation, erreurs
et matrice de tests. Les préciser et les justifier dans 5C/5D avant le code dépendant, sans nouveau
questionnaire par détail. Aucun changement produit, bypass ou service payant autorisé par cette
latitude. Toute décision produit nouvelle reste à faire arbitrer, regroupée avec ses dépendances.

5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`), contrats partiellement implémentés par C02–C05 sur PR #7, lobby/S2S/handoff futurs.
5C devient le lot courant sur une nouvelle branche issue de ce merge : synchronisation documentaire,
puis cadrage présenté avant implémentation substantielle. Aucun début de 5D, déploiement ou nouvelle
fusion autorisé par cette transition. Les décisions 5B ci-dessus restent inchangées.

## 10. Matrice d’acceptation future — aucun scénario exécuté par cette rédaction

| Domaine | Preuves requises | Lot dépendant |
| --- | --- | --- |
| Identité/permissions | Autre compte, membership, univers ou Empire refusé ; fog serveur ; aucun droit gameplay administrateur implicite | 5C/5D |
| Membership | Suspension vs commande ordonnée ; réactivation sans anciennes sessions ; univers/workers continuant | 5C/5D |
| S2S | Réseau public, certificat invalide, service hors scope, header forgé refusés | 5C |
| Livraison | Doublons/désordre/timeout après commit ; conflit de contenu ; réconciliation sans retour arrière ni double effet | 5C/5D |
| Révocations | Portées session/appareil/compte/membership, tickets en vol et renouvellements concurrents ; reprise jusqu’à acquittement et UI fidèle | 5C/5D |
| Handoff | Mauvais scope/signature/type/dates/clés/cookie/état refusé ; consommation concurrente unique ; réponse perdue non rejouable | 5C/5D |
| Dégradé/clés | Ticket déjà émis consommable dans 60 s sous contrôles locaux ; clé inconnue refusée ; rotation prédistribuée et compromission | 5C/5D |
| Sessions | Frontières 7 j/72 h et 8 h/2 h ; valid_until antérieure ; activité automatique sans effet et explicite classée serveur ; aucune résurrection | 5C/5D |
| Appareils | Profils distincts/onglets partagés ; caps configurables 10/10 en concurrence ; memberships non limités ; aucune éviction silencieuse | 5C/5D |
| Logout | Retour lobby sans logout ; Game seule ; appareil ; tous appareils ; progression préservée ; état en attente si Game injoignable | 5C/5D |
| Navigateur | API même origine, CORS credentials refusé par défaut ; CSRF et exceptions minimales ; cookies protégés par univers ; aucun secret URL/log/localStorage | 5C/5D |
| Compte | Politique mot de passe ; vérification unique 24 h/réémission ; aucun handoff avant vérification ; non-énumération | 5C |
| Mot de passe | Reset 30 min unique/dernière émission en concurrence ; changement volontaire protégé ; révocation globale sans auto-login, sans bypass MFA ; notification | 5C/5D |
| Email | Demande unique 1 h ; aucun mélange/glissement ; double confirmation sans MFA et variante MFA ; pending ; révocation globale et liens invalidés | 5C/5D |
| Flux concurrents | Reset/changement mot de passe ou récupération MFA invalident demande email ; courses consommation/réémission sans preuve réutilisable | 5C |
| MFA | TOTP unique, cinq WebAuthn nommables ; privilèges WebAuthn et deux authentificateurs production ; aucun rôle Empire assimilé | 5C selon cadrage compte/MFA |
| Step-up | Preuve cinq minutes/action/usage unique/paramètres ; catalogue obligatoire ; admin avec vérification utilisateur ; déconnexion ordinaire possible | 5C |
| Effets MFA | Global sur activation/désactivation/réduction/remplacement/récupération ; pas de global sur ajout ou régénération volontaire protégés ; audit/notification | 5C/5D |
| Secours | Dix codes 128 bits minimum, affichage unique, double consommation refusée ; récupération quinze minutes sans Game/admin ; renouvellement des secours | 5C |
| Perte totale | Blocage sans procédure approuvée ; aucun email/mot de passe contournant MFA ; aucun privilège restauré par code seul | Lot support/administration à cadrer |
| Audit/email | Aucun secret en logs/notifications ; 90 j sécurité sans purge des protections anti-rejeu ; envois persistés et statut fidèle | 5C puis production |
| Anti-abus | Limites configurables testées compte/IP/opération, non-énumération, pas de verrouillage permanent provoqué par tiers | 5C avant exposition |
| Résilience | Portal coupé : Game valide et événements continuent ; refus aux échéances ; charge/isolation mesurées | 5D puis 17 |

## 11. Sources et références

Les sources primaires déjà consultées pendant 5B appuient les mécanismes ; elles ne valident ni
les durées ni les choix produit Echosphere, dont la provenance est l’arbitrage utilisateur explicite.

- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
- [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html), si format JWT retenu par le détail délégué.

[Modèle](data-model.md) · [Sécurité](security.md) · [API](api.md) ·
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) · [Roadmap](../05-project/roadmap.md).
