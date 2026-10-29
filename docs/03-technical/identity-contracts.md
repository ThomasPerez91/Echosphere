# Identité et contrats Portal/Game — préparation 5B

**Statut : décisions utilisateur validées pour le compte, les limites temporelles et l’activité explicite ; mécanismes
techniques encore proposés ; ensemble non implémenté.** Date : 2026-10-29.
Source : arbitrage utilisateur explicite pour poursuivre PR #6, synthétisé ci-dessous.
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) reste la décision de plateforme acceptée.
Seules les parties précisées de [Q40–Q44](../05-project/open-questions.md) sont closes ; ces Q restent
partiellement ouvertes. Q16 et Q45–Q56 ne sont pas fermées par ces arbitrages.
Aucune route, table, dépendance, migration ou application Portal n’est livrée par ce document.

## Arbitrages validés — 2026-10-29

Les lignes suivantes sont des **Décisions validées, non implémentées**. Les autres mécanismes
de ce document gardent leur statut Proposition, notamment ticket signé, sessions opaques,
cookies par univers, compteurs de révision/epoch, mTLS, outbox et synchronisation.

| Partie close | Décision utilisateur | Reste ouvert |
| --- | --- | --- |
| Q40 — login et principes de récupération | MVP email/mot de passe, email vérifié avant premier handoff, récupération par jeton court/unique, hash Argon2id via bibliothèque maintenue ; global_user_id indépendant de l’email et de la méthode de login | Bibliothèque, paramètres Argon2id et politique détaillée de récupération, dont durée exacte et effets sur sessions |
| Q41 — durées et activité Portal | Maximum absolu 7 jours, inactivité maximum 72 h ; interaction explicite classée côté serveur seule comptabilisée, sans prolongation de l’absolu | Stockage/cookies et rotation |
| Q42 — durée et unicité du ticket | 60 secondes, usage unique | Format/crypto, audience/nonce, liaison navigateur et mécanisme atomique de consommation |
| Q43 — durées et activité Game | Maximum absolu 8 h, inactivité maximum 2 h, expiration anticipée possible par GameAccess ; interaction explicite classée côté serveur seule comptabilisée, sans prolongation de l’absolu | Stockage, rotation, limites de sessions simultanées et nettoyage |
| Q44 — limites en panne et renouvellement | Droits au plus 8 h depuis confirmation Portal, non glissants ; révocation/suspension reçue appliquée immédiatement ; nouvelle confirmation/handoff valide avec Portal disponible pour renouveler | Protocole de renouvellement et synchronisation/propagation, concurrence avec révocation, logout Q45 |

Google/OIDC pourra être ajouté plus tard comme méthode supplémentaire du même compte global,
sans remplacement de l’identité et sans dépendance MVP. Fournisseur email, MFA et paramètres
opérationnels restent ouverts dans leurs Qxx. Aucun détail de Q46–Q56 n’est accepté implicitement.

## 1. Périmètre et séparation des autorités

Les exigences déjà validées sont : compte global multi-parties, Membership distincte d’Empire,
deux backends/bases isolables, aucun SQL Portal→Game DB, interface interne authentifiée/idempotente,
ticket court à usage unique, session Game autonome, gameplay direct et worker indépendant du Portal.
Les sections suivantes proposent leur traduction technique ; seuls les choix listés dans les
arbitrages ci-dessus sont validés. Les autres noms, formats et politiques restent à valider.

| Propriétaire proposé | Données et responsabilités | Limite |
| --- | --- | --- |
| Portal / Accounts DB | User, credentials, sessions Portal, état souhaité des memberships et journal de livraison des changements | Aucun accès SQL Game, aucune décision économique |
| Game / Game DB | État des univers, droits effectivement appliqués, rattachements aux empires, tickets consommés et GameSessions | Aucun email, hash de mot de passe, secret MFA ou cookie Portal |
| Navigateur | Choix de partie et intentions de commande | Aucun calcul autoritaire de droit, coût, date ou production |

Portal exprime une intention de participation ; Game valide son application et en accuse réception.
Le lobby distingue donc `pending` et `applied` : un appel réseau envoyé ne prouve pas un accès accordé.
Game conserve son autorité sur l’existence d’un Empire et son appartenance à Universe.
Un UUID global est une référence externe opaque, sans FK inter-bases ni compte factice de backfill.

## 2. Modèle logique et contrôles proposés

Ces contrats de données ne sont pas des schémas SQL à créer maintenant.

| Objet | Champs conceptuels minimaux | Règle proposée |
| --- | --- | --- |
| User (Portal) | `global_user_id`, état du compte | Identité indépendante des parties |
| UniverseMembership (Portal) | `membership_id`, `global_user_id`, `universe_id`, état souhaité, `access_revision` | Une participation par utilisateur/univers dans la fondation proposée |
| GameAccess (Game) | mêmes références, état effectif, `access_revision`, `session_epoch`, `valid_until`, autorisations locales | Clé de participation stable ; références User/Universe non réassignables |
| EmpireBinding (Game) | participation, empire, permissions | Empire du même univers ; association distincte de la participation |
| GameSession (Game) | empreinte du secret, utilisateur, univers, participation, `session_epoch` et échéances | Une session est limitée à un univers et ne porte pas de droit auto-signé par le client |

États d’accès proposés : `active`, `suspended`, `revoked`. Une réactivation explicite exige une
nouvelle révision ; elle ne ressuscite jamais une ancienne session. Une expiration de `valid_until`
refuse l’accès même si l’état enregistré est encore `active`. Les tombstones de révocation empêchent
un ancien grant d’être rejoué comme première création. Politique de rétention à fixer avant purge.

Deux compteurs proposés évitent de déconnecter tous les appareils à chaque renouvellement :
`access_revision` ordonne chaque livraison ; `session_epoch` invalide les sessions lors d’une
suspension, révocation, réactivation, modification de permissions/bindings ou logout global.
Un simple renouvellement de validité, à identité/droits/état inchangés, conserve l’epoch.
Game refuse tout recul d’epoch et tout changement de sécurité qui ne l’augmente pas. Une session
compare son epoch à l’accès courant et utilise les permissions locales, jamais un ancien snapshot.

Q21 reste ouverte : le modèle n’impose ni partage ni propriété humaine unique d’un Empire.
La fondation peut limiter ses opérations publiques sans créer une contrainte globale irréversible.
Les permissions proposées pour 5D sont `colony.read`, `colony.construct`, `colony.cancel`, chacune
associée à un empire autorisé. Aucun rôle administrateur universel ou spectateur omniscient implicite.
Créer une partie ne donne pas automatiquement tous les droits sur ses entités.

Chaque requête Game suit :

1. Secret de session valide, non expiré, non révoqué ; lecture en Game DB.
2. Correspondance utilisateur/participation/univers, accès `active`, epoch courant et validité.
3. Permission de l’opération et rattachement à l’Empire demandé.
4. Entity appartenant à cet Empire et à cet univers ; projection filtrée selon la connaissance.
5. Pour une mutation, revalidation des droits dans la transaction qui applique l’effet.

Proposition de concurrence : une commande verrouille d’abord l’accès local, puis son stream métier.
Une suspension prend le même verrou d’accès. La première transaction à obtenir ce verrou définit
l’ordre : après commit de suspension, aucune nouvelle mutation sous cet accès n’est acceptée.
Les handlers temporels ne prennent jamais ce verrou ; une suspension ne stoppe pas la production
ou les constructions déjà acceptées. Aucun appel Portal dans une transaction gameplay.
Les futures mutations multi-streams restent Q13, sans contrat improvisé ici.

## 3. Interface interne proposée : livraison et convergence

Opérations logiques, **sans URL exposée ni OpenAPI ajouté** :

| Opération | Intention | Application Game proposée |
| --- | --- | --- |
| `ProvisionUniverse` | Demander une instance avec référence de configuration validable | Résultat stable par clé ; pas de génération/colonie implicite ajoutée à 5B |
| `SetUniverseAccess` | Appliquer grant, suspension, révocation ou renouvellement | État complet versionné, validation des références et bindings ; révocation invalide les sessions locales |
| `GetOperationResult` | Reprendre après timeout | Résultat autorisé pour le même service et scope |
| `GetAccessRevision` | Réconcilier l’état connu | Métadonnées de synchronisation minimales ; aucune projection gameplay globale |

Join est un cas d’orchestration Portal : vérifier les règles du mode, demander l’accès et attendre
l’acquittement. Il ne devient pas une écriture SQL ni une route qui contourne les règles de partie.
Les règles privées/persistantes Q19–Q29/Q55 ne sont pas inventées pour rendre ce contrat exécutable.

Enveloppe proposée : `contract_version`, `operation_id`, `operation_type`, `universe_id`,
`membership_id` si concerné, `access_revision`, `session_epoch` pour un accès, payload complet,
`issued_at` et identifiant de trace.
La version initiale serait `1`. Champs inattendus, types incorrects et version inconnue sont refusés.
Game calcule l’empreinte canonique du contenu ; il ne fait pas confiance à une empreinte client.

- Authentifier puis autoriser le service pour l’opération et l’univers avant toute déduplication.
- Stocker résultat, clé d’opération et effet dans la même transaction Game.
- Même service/clé/contenu : résultat enregistré, sans deuxième effet ; contenu différent : conflit.
- Une révision supérieure remplace l’état complet ; une inférieure est périmée et ne modifie rien.
  Même révision/contenu identique : replay ; même révision/contenu différent : conflit.
- Les révisions sont allouées par Portal sous transaction par membership, y compris les renouvellements.
  Les états complets permettent de recevoir une révocation avant un ancien grant sans ressusciter l’accès.
- Portal persiste intention et livraison à effectuer dans sa propre transaction (outbox proposée).
  Il réessaie après panne/timeout avec la même clé et le même contenu, jamais une nouvelle intention.
  Aucun commit distribué supposé entre Accounts DB et Game DB.
- Acquittement perdu après commit Game : consultation/rejeu rend le résultat ; le lobby reste en
  attente tant qu’il ne le connaît pas. La réconciliation n’abaisse jamais une révision Game.
- Les droits arrivés à expiration ne sont pas prolongés par un retry d’un ancien message.

Proposition S2S : TLS mutuel sur ingress interne séparé, identité de service extraite d’un certificat
validé et allowlist d’opérations/scopes. Rotation, CA, expiration et déploiement restent à spécifier
avant implémentation ; le réseau privé seul n’authentifie rien. Aucun header d’identité client n’est
fiable. Si TLS termine sur un proxy, Game n’accepte les assertions que de ce proxy authentifié,
avec suppression des headers entrants et accès direct backend interdit. Alternative plus simple à
évaluer : credential de service rotatif sur TLS, avec exposition accrue en cas de fuite. Q46 reste ouverte.

## 4. Handoff navigateur proposé

Proposition recommandée : ticket signé asymétriquement, vérifiable localement par Game, et secret
de session opaque conservé côté Game. Alternative : code opaque à échanger auprès de Portal ; elle
simplifie la révocation avant échange mais rend chaque nouvelle entrée dépendante de Portal.
Aucune bibliothèque ni algorithme n’est choisi par cette proposition.

Déroulement proposé sur deux origines HTTPS distinctes du **même site**, toutes deux contrôlées :

1. Le navigateur ouvre l’entrée Game, qui crée un état de pré-authentification aléatoire, court et
   lié à un cookie host-only. Game génère l’identifiant de handoff ; il n’accepte pas un état fixé
   par un lien client. Retour Portal et retour Game sont des destinations configurées en allowlist.
2. Portal reçoit la demande, contrôle sa session et sa protection CSRF avant émission. Il vérifie
   compte actif, membership souhaitée active et révision déjà acquittée par Game. Le ticket lie
   utilisateur, participation, univers, révision/epoch, audience Game et identifiant de handoff.
3. Le retour transmet le ticket par POST vers l’échange Game, sans token en query/fragment,
   historique, localStorage, analytics ou logs. Réponses `Cache-Control: no-store` et politique
   de referrer restrictive ; aucune ressource tierce sur les pages de transfert.
4. Game vérifie schéma, signature, émetteur, audience, type, dates, état de pré-authentification
   et cookie lié. Une allowlist serveur fixe les algorithmes ; `kid` ne déclenche aucune URL réseau
   choisie par le ticket. Le ticket ne suffit pas à créer des droits absents de Game DB.
5. Sous transaction, Game verrouille l’accès local, vérifie état/révision/epoch/validité, consomme
   l’identifiant unique du ticket et l’état de handoff, puis crée la session. Un index unique sur
   émetteur/identifiant de ticket assure qu’un seul échange concurrent réussit.
6. Game pose son cookie puis redirige vers une URL propre. Une réponse perdue après commit ne
   permet pas de réutiliser le ticket ; un nouveau parcours d’entrée est nécessaire.

Claims proposés : `contract_version`, `iss`, `aud`, `sub` (global user id), `universe_id`,
`membership_id`, `access_revision`, `session_epoch`, `handoff_id`, `jti`, `iat`, `exp`, type explicite de ticket.
Ni email, ni credential, ni catalogue de permissions faisant autorité. Signature seule ne fournit
ni usage unique ni liaison au navigateur : ces deux garanties exigent l’état local ci-dessus.

**Validé Q42 :** ticket valide au maximum **60 secondes**, utilisable une seule fois.
La pré-authentification de **5 minutes** et la tolérance `iat` de **5 secondes** restent proposées.
La règle de frontière est un refus dès `now >= exp` ; aucune tolérance technique ne doit prolonger
les 60 secondes acceptées. Formats de dates et mécanismes de contrôle restent à contractualiser.
Un autre univers, une mauvaise audience, une révision ancienne ou un cookie pré-auth absent sont
refusés. Une session existante n’est jamais remplacée silencieusement par un ticket d’un autre
utilisateur ; afficher un conflit et demander un parcours de changement de compte explicite.

Game conserve un jeu local de clés publiques autorisées, distribué avant usage d’une nouvelle clé.
Clé inconnue : refus sans découverte synchrone Portal ; clé compromise : retrait local et procédure
de révocation des sessions concernées. Recouvrement de rotation et rétention des tickets consommés
couvrent au minimum leur durée d’acceptation et la dérive retenue. Pas de secret de signature Portal
en Game. La PKI S2S et les clés de ticket ont des usages distincts.

## 5. Sessions et autonomie validées ; stockage/cookies proposés

Les limites ci-dessous sont des **Décisions utilisateur validées le 2026-10-29**, non implémentées.
Elles remplacent la proposition initiale Portal à 24 h d’inactivité par **72 h**.
Le stockage opaque, les cookies et leur rotation restent des propositions techniques distinctes.

| Paramètre | Limite validée | Conséquence |
| --- | --- | --- |
| Session Portal | Absolu 7 jours, inactivité 72 h | L’activité ne prolonge pas le maximum absolu |
| Session Game | Absolu 8 h, inactivité 2 h | L’activité ne prolonge pas le maximum absolu ; GameAccess peut expirer plus tôt |
| Validité d’un accès Game confirmé | Au plus 8 h depuis sa confirmation Portal | Borne des droits périmés si une révocation ne peut plus être livrée |
| Renouvellement | Portal disponible et nouvelle confirmation/handoff valide | Aucun renouvellement autonome illimité par Game |

Une session expire au plus tôt de ses propres limites et de `GameAccess.valid_until`.
La validité des droits n’est jamais glissante sur l’activité Game et ne repart pas à zéro au
début d’une panne. Un message ancien livré tard ne donne jamais huit heures supplémentaires à
compter de sa réception ; l’ancrage est la confirmation par Portal. Le protocole proposé transmet
une échéance absolue que Game doit borner à cette confirmation, mais son format et sa validation
restent ouverts sous Q44/Q53. L’activité ne prolonge ni la limite absolue de session ni les droits.
Une nouvelle session créée juste avant l’expiration d’accès ne gagne pas huit heures de droits.

Expression des limites validées (dates serveur UTC ; aucune implémentation ici) :

```text
portal_deadline = min(portal_created_at + 7 jours, portal_last_activity_at + 72 heures)
access_valid_until <= portal_confirmed_at + 8 heures
game_deadline = min(game_created_at + 8 heures, game_last_activity_at + 2 heures,
                    access_valid_until)
```

À l’échéance, une nouvelle commande est refusée. Une révocation/suspension reçue peut refuser
l’accès avant ces dates ; elle n’attend jamais l’expiration des huit heures. Les délais ne
garantissent donc pas huit heures d’accès indépendamment des autres limites.

### Activité explicite — Q41/Q43, décision utilisateur validée le 2026-10-29

Seules les interactions explicites de l’utilisateur réinitialisent l’inactivité Portal ou Game.
Le serveur classe les types de requêtes/actions ; le navigateur ne fournit jamais un timestamp
faisant autorité pour `last_activity_at`. Un indicateur client ne suffit pas à classifier l’action.

| Catégorie | Effet sur l’inactivité |
| --- | --- |
| Navigation volontaire, action/commande utilisateur, modification ou sauvegarde d’un réglage, actualisation explicitement demandée | Réinitialisation sur la base de l’heure serveur |
| Autre requête explicitement classée comme interaction utilisateur par le serveur | Même règle |
| Polling automatique, refresh périodique, heartbeat, réception WebSocket, reconnexion automatique, prefetch, télémétrie ou simple onglet ouvert | Aucune réinitialisation |

Le traitement automatique doit rester distinct d’une actualisation volontaire dans la classification
serveur, même si les deux lisent les mêmes données. Le catalogue concret des actions/routes appartient
aux futurs contrats d’API ; aucune route ni mécanisme de détection navigateur n’est implémenté ici.
La classification n’est pas une preuve qu’un humain plutôt qu’un automate envoie la requête ;
les protections anti-abus Q50 restent ouvertes.

Conséquence des échéances validées : contrôler l’expiration avant de prendre en compte une activité ;
une interaction à l’échéance ou après ne ressuscite pas une session expirée. Une activité admissible
ne modifie que l’ancrage d’inactivité, jamais la création de session, sa limite absolue ou
`GameAccess.valid_until`. Laisser un onglet ouvert avec du polling ne maintient pas la session.
Le protocole exact de renouvellement reste à décider sous Q44.

Exemples déduits des limites acceptées, **illustrations contractuelles sans tests exécutés** :

| Situation (UTC) | Résultat exigé |
| --- | --- |
| Droits confirmés à 08:00, message reçu à 10:00 | valid_until au plus 16:00, jamais 18:00 |
| Panne Portal à 15:00 pour ces droits | Limite toujours 16:00, jamais 23:00 |
| Activité Game à 15:59 | N’étend ni valid_until, ni la limite absolue de session |
| Session créée à 15:00, droits valides jusqu’à 16:00 | Nouvelles commandes refusées dès 16:00, même si la session absolue permettrait d’aller à 23:00 |
| Suspension reçue avant 16:00 | Application immédiate ; le solde de validité ne permet pas de continuer |

Proposition technique conservée : à epoch inchangé, un renouvellement d’accès ne modifie pas les
échéances propres des sessions existantes et permet un nouveau handoff. L’epoch et les opérations
correspondantes ne sont pas acceptés par la validation de la fenêtre de huit heures.

Secrets de session proposés : aléatoires cryptographiques de 256 bits, seule leur empreinte en DB.
Cookies distincts Portal/Game, host-only, `Secure`, `HttpOnly`, `Path=/`, préfixe `__Host-`,
`SameSite=Lax` explicite. Les cookies ne sont pas isolés par port : le futur développement local
devra définir des hôtes distincts ou une politique dédiée, sans désactiver la sécurité production.
Pour plusieurs univers simultanés sur une même origine Game, proposer un nom de cookie par univers
(`__Host-GameSession-<universe_id>`) ; choisir un univers ne remplace pas la session des autres onglets.
Game sélectionne le cookie du scope demandé puis vérifie le scope enregistré côté serveur.
La limite de cookies/sessions simultanés et leur nettoyage restent à fixer sous Q43 avant 5C/5D ;
elle ne doit pas devenir une limite implicite du nombre de memberships d’un compte.

Chaque frontend appelle sa propre API de même origine ; pas de CORS credentialed global.
Toutes les mutations à cookie vérifient Origin et jeton CSRF lié à la session, avec refus par défaut.
L’échange de ticket a sa politique particulière : Origin Portal exact, état à usage unique et cookie
pré-auth Game lié. Un déploiement réellement cross-site exige une nouvelle recette cookies/handoff ;
il n’est pas couvert par cette proposition. Une attaque XSS reste un risque malgré HttpOnly.

| Situation | Comportement et statut |
| --- | --- |
| Portal arrêté, Game/DB disponibles | **Validé** : worker et sessions encore valides continuent dans leurs limites, sans appel Portal par commande |
| Session ou validité d’accès échue pendant panne Portal | **Validé** : nouvelle commande refusée ; univers et workers continuent de progresser |
| Révocation/suspension reçue | **Validé** : application immédiate, sans attendre l’échéance ; révision/epoch et sérialisation proposés en sections 2–3 |
| Révocation non livrable | **Validé** : ancien droit utilisable jusqu’à son échéance locale, au maximum 8 h depuis confirmation, sans redémarrage de fenêtre lors de la panne |
| Logout Game | **Proposé Q45** : révocation de la session locale concernée, sans arrêter le monde ou les autres univers |
| Logout global | **Proposé Q45** : révocation des sessions Portal, propagation d’invalidation vers Game avec accusés ; UI distingue terminé et en attente |
| Game DB indisponible | **Proposé** : refus des accès/sessions et commandes ; aucun fallback cache permissif |

La proposition de logout global conserve les memberships, mais invalide les anciennes sessions et tickets via une
nouvelle révision et un nouvel epoch de chaque accès. Une reconnexion peut ouvrir une nouvelle session si les droits
restent actifs. Pour tous les accès déjà connus de Game, une confirmation en vol avant le logout
ne peut produire une validité au-delà de sa propre échéance absolue. La borne choisie s’applique
aux sessions échappant temporairement à la propagation. Suspension de compte utilise la même
livraison durable, avec suspension des accès, pas une simple suppression du cookie navigateur.

**Arbitrage clos sur la fenêtre :** l’utilisateur accepte le maximum de huit heures depuis la
dernière confirmation Portal, y compris le risque de révocation non livrable pendant cette fenêtre.
Cela ne clôt ni Q54 (protocole/propagation), ni Q52 (cycle de membership), ni Q45 (logout).

## 6. Compte et protections à cadrer avant 5C

**Validé Q40 :** MVP email/mot de passe, hash Argon2id via bibliothèque maintenue,
vérification de l’adresse email obligatoire avant le premier handoff vers Game, récupération
de compte par jeton court à usage unique. `global_user_id` est indépendant de l’email et de la
méthode d’authentification : changer d’email ou ajouter une méthode ne crée pas une autre identité.
Google/OIDC pourra être ajouté ultérieurement comme méthode supplémentaire du même compte,
sans être requis pour le MVP et sans remplacer cette identité globale.

Restent ouverts : bibliothèque et paramètres Argon2id, durée exacte et politique de récupération
(réémission, invalidation et effets sur sessions), règles de changement d’email et d’association
d’une méthode supplémentaire. Aucun mécanisme OIDC n’est ajouté à 5C par anticipation.
Le fournisseur email et ses paramètres restent Q49 ; MFA et sa récupération restent Q48 ;
les protections anti-abus et leurs seuils restent Q50. Aucune inscription publique livrée ici.

Q48 : cadrer MFA et récupération avant exposition distante ; proposer son implémentation dans un
lot explicite selon le mode d’exposition, sans prétendre qu’elle est livrée par 5C. Q50 : limites
sur login/récupération/émission de ticket, réponses non énumérables et métriques d’abus ; seuils
et éventuel challenge à mesurer/décider, aucun CAPTCHA/WAF/Redis ajouté par principe.
Un outil email local de test ne devient ni faux utilisateur ni bypass de la vérification en production.

## 7. Erreurs, observabilité et isolation proposées

Enveloppe future : `error.code`, `error.request_id`, indicateur de retry ; texte UI distinct,
aucun détail DB, token, claim privé ou statut d’une entité hors scope.
Codes proposés : `unauthenticated` (401), `access_denied` (403), `not_found` pour une entité hors
projection (404), `idempotency_conflict`/`revision_conflict` (409), `invalid_contract` (422),
`rate_limited` (429), `temporarily_unavailable` (503). Les refus d’échange de ticket exposent un
motif public générique ; les motifs précis restent dans un audit interne sans ticket brut.
Ne pas retenter automatiquement une mutation avec une nouvelle clé après un timeout.

Observer retard de livraison/révocation, échecs de handoff, clés inconnues et opérations en attente.
Tracer les identifiants nécessaires avec accès et rétention limités ; jamais mot de passe,
ticket, cookie, jeton CSRF ou contenu privé des payloads dans les logs.
Réconciliation et purge de déduplication doivent préserver les tombstones/révisions ; pas de TTL
arbitraire qui permette de rejouer un provisionnement oublié. Politique à fixer avant implémentation.

Recette opérationnelle future : secrets/DB/pools/CPU/RAM séparables, ingress interne filtré,
budgets de connexions et requêtes indépendants. Saturer Portal sans épuiser Game ; mesurer aussi
les limites de l’hôte/réseau commun. Aucun chiffre de charge ou garantie anti-DDoS établi en 5B.

## 8. Matrice d’acceptation future

**Scénarios à implémenter dans les lots concernés, aucun exécuté par ce document.**

| Contrat | Preuve attendue | Lot |
| --- | --- | --- |
| Identité et scope | UUID d’une autre participation/univers/empire refusé, sans fuite de projection | 5C/5D |
| Droits et concurrence | Suspension vs commande : ordre transactionnel démontré ; aucune nouvelle dépense après suspension appliquée | 5D |
| Handoff | Signature/type/audience/émetteur/dates/révision invalides et état/cookie absent refusés | 5C/5D |
| Rejeu | Deux échanges concurrents : une seule session ; crash avant/après commit et réponse perdue | 5C/5D |
| Liaison navigateur | Ticket d’un attaquant injecté dans un autre navigateur refusé ; changement d’identité non silencieux | 5C/5D |
| Interface interne | Appel public, certificat invalide, service hors scope et header forgé refusés | 5C |
| Livraison | Timeout après commit, doublons, messages désordonnés et même révision contradictoire sans double effet | 5C |
| Compte MVP | Email non vérifié refusé au premier handoff, récupération courte consommée une seule fois, identité globale indépendante des méthodes | 5C |
| Limites validées | Portal : refus à 7 j ou 72 h d’inactivité ; Game : refus à 8 h, 2 h d’inactivité ou échéance d’accès antérieure ; ticket refusé à 60 s | 5C/5D |
| Activité explicite | Chaque catégorie automatique conserve last_activity_at ; navigation/commande/réglage/actualisation volontaire le réinitialisent selon classification serveur ; timestamp client falsifié sans effet ; interaction à expiration refusée ; maxima absolus et valid_until inchangés | 5C/5D |
| Panne et dates | Confirmation retardée, panne commencée tard et activité Game ne déplacent pas valid_until ; suspension reçue avant échéance appliquée immédiatement | 5C/5D |
| Session autonome | Portal coupé : lecture/mutation Game valide et échéance métier progressent ; aucun appel Accounts | 5D |
| Renouvellement et multi-parties | Renouvellement sans déconnexion des sessions encore valides ; deux onglets d’univers différents sans écrasement de cookie | 5C/5D |
| Révocation dégradée | Droit expiré refusé, grant retardé non prolongé, réactivation ne restaure pas les sessions | 5C/5D |
| Logout | Logout local/global, propagation partielle et retour Portal explicitement testés | 5C/5D |
| Clés | Rotation préchargée pendant panne Portal, clé inconnue refusée, procédure de compromission | 5C/5D |
| Navigateur | Cookies/CSRF/origines, absence de token dans URL/logs, mobile et clavier | 5C/5D |
| Isolation | Charge/panne Portal avec budgets Game mesurés et limites de l’hôte partagé consignées | 5D puis 17 |

## 9. Arbitrages et passage au lot suivant

| Questions | État après arbitrage du 2026-10-29 | Travail restant |
| --- | --- | --- |
| Q40 | **Parties closes** : login MVP, Argon2id, email vérifié avant handoff, récupération courte/unique et identité indépendante | Bibliothèque/paramètres et protocole de récupération ; email Q49, MFA Q48 restent ouverts |
| Q41 | **Parties closes** : 7 j absolus / 72 h d’inactivité, interactions explicites classées côté serveur | Stockage/cookies et rotation |
| Q42 | **Parties closes** : 60 s et usage unique | Format, protection contre rejeu, audience, liaison navigateur et consommation |
| Q43 | **Parties closes** : 8 h absolues / 2 h d’inactivité et limite anticipée par GameAccess, interactions explicites classées côté serveur | Stockage, rotation et nombre de sessions |
| Q44 | **Parties closes** : validité non glissante 8 h depuis confirmation, panne sans reset, refus à échéance, renouvellement via Portal et nouvelle confirmation/handoff | Protocole de renouvellement, concurrence et mécanismes de révocation |
| Q45 | Logout local et propagation globale distincts | UX et limites de confirmation validées |
| Q46 | mTLS interne recommandé, alternative credential TLS | Topologie et authentification opérables choisies |
| Q47 | Deux origines même site, cookies host-only, CSRF | Hôtes local/production et parcours testables définis |
| Q48/Q49/Q50 | MFA, email, anti-abus | Périmètre et contrôles minimaux avant exposition décidés |
| Q51/Q52 | Accès local versionné et bindings explicites | Permissions, transitions et règles de réactivation acceptées |
| Q53 | Intention Portal, application Game, outbox et révisions | Propriétaires, retry/réconciliation/rétention acceptés |
| Q54 | Fenêtre de 8 h actée sous Q44 ; **question toujours ouverte** | Transport/propagation de révocation et application concurrente à contractualiser |
| Q55 | Préserver les règles privées/persistantes ouvertes | Aucun join public ajouté avant règles du mode |
| Q56 | Ticket signé et clés locales toujours proposés ; **question ouverte** | Format/algorithme/rotation et recette de validation autonome |

5B progresse avec les décisions ci-dessus, sans être déclarée achevée. L’activité explicite Q41/Q43 est désormais arbitrée.
La prochaine décision produit/sécurité à examiner est Q45 : portée des déconnexions Portal, Game
et globale, notamment sur les autres parties. La proposition de logout ci-dessus reste à valider. Les autres propositions restent révisables, sans
fermeture de Q46–Q56. Les bibliothèques et paramètres cryptographiques se choisissent
avant l’implémentation dépendante, sans solution de démonstration permissive en attendant.
5C reste un lot séparé, à autoriser après les arbitrages nécessaires ; 5D dépend du contrat de
session/autorisation et des preuves de résilience. Les systèmes de modes et de gameplay futurs
restent hors de cette préparation.

## 10. Sources techniques et provenance

Sources primaires consultées le 2026-10-29 ; elles appuient les mécanismes de sécurité, pas les
choix produit Echosphere ni les durées proposées. Aucune conversation privée exportée.

- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) : cookies et cycle de vie des sessions.
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) : défense CSRF complémentaire à SameSite.
- [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) : refus par défaut et contrôle par requête.
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) : option Argon2id si mot de passe retenu.
- [RFC 8725](https://www.rfc-editor.org/rfc/rfc8725.html) : validation des JWT, audience, algorithmes et séparation des usages si ce format est retenu.

Références projet : [modèle](data-model.md), [sécurité](security.md), [API](api.md),
[ADR 0008](../adr/0008-control-plane-game-data-plane.md), [roadmap](../05-project/roadmap.md).
