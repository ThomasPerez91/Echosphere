# Identité et contrats Portal/Game — préparation 5B

**Statut : Proposition de contrats, non implémentée, à arbitrer.** Date : 2026-10-29.
L’utilisateur a autorisé la poursuite du prochain lot après la reprise de master intégrant #5.
Cette autorisation ouvre le cadrage 5B ; elle ne valide pas les choix nouveaux ci-dessous.
[ADR 0008](../adr/0008-control-plane-game-data-plane.md) reste la décision acceptée.
[Q16/Q40–Q56](../05-project/open-questions.md) restent ouvertes. Aucune nouvelle ADR acceptée,
route, table, dépendance, migration ou application Portal n’est livrée par ce document.

## 1. Périmètre et séparation des autorités

Les exigences déjà validées sont : compte global multi-parties, Membership distincte d’Empire,
deux backends/bases isolables, aucun SQL Portal→Game DB, interface interne authentifiée/idempotente,
ticket court à usage unique, session Game autonome, gameplay direct et worker indépendant du Portal.
Les sections suivantes proposent leur traduction ; noms, formats, durées et politiques sont à valider.

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

Valeurs proposées à arbitrer : ticket valide **60 secondes**, pré-authentification **5 minutes** ;
refus dès `now >= exp`, contrôle de `iat` avec une tolérance d’horloge maximale de **5 secondes**.
Un autre univers, une mauvaise audience, une révision ancienne ou un cookie pré-auth absent sont
refusés. Une session existante n’est jamais remplacée silencieusement par un ticket d’un autre
utilisateur ; afficher un conflit et demander un parcours de changement de compte explicite.

Game conserve un jeu local de clés publiques autorisées, distribué avant usage d’une nouvelle clé.
Clé inconnue : refus sans découverte synchrone Portal ; clé compromise : retrait local et procédure
de révocation des sessions concernées. Recouvrement de rotation et rétention des tickets consommés
couvrent au minimum leur durée d’acceptation et la dérive retenue. Pas de secret de signature Portal
en Game. La PKI S2S et les clés de ticket ont des usages distincts.

## 5. Sessions, cookies et autonomie proposées

Les chiffres suivants sont des **propositions Echosphere**, pas des exigences OWASP.

| Paramètre | Proposition initiale | Conséquence |
| --- | --- | --- |
| Session Portal | Secret opaque ; absolu 7 jours, inactivité 24 h | Réauthentification après limite, rotation au login et changement sensible |
| Session Game | Secret opaque ; absolu 8 h, inactivité 2 h | Date serveur ; aucune extension de l’absolu par simple activité |
| Validité d’un accès Game confirmé | Au plus 8 h depuis sa confirmation Portal | Borne des droits périmés si une révocation ne peut plus être livrée |
| Renouvellement Game | Nouveau handoff avec Portal actif et droits confirmés | Aucun refresh autonome illimité pendant panne Portal |

Une session expire au plus tôt de ses propres limites et de `GameAccess.valid_until`.
Le renouvellement d’accès ne prolonge aucune ancienne session ; à epoch inchangé il la laisse
valide jusqu’à ses propres limites et autorise un nouveau handoff.
Portal calcule une échéance absolue dans le message, que Game borne à la politique acceptée ;
un message ancien livré tard ne donne jamais huit heures supplémentaires à compter de sa réception.
Une nouvelle session créée juste avant l’expiration d’accès ne gagne pas huit heures de droits.

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

| Situation | Comportement proposé |
| --- | --- |
| Portal arrêté, Game/DB disponibles | Worker et gameplay des sessions encore valides continuent, sans appel Portal |
| Session ou validité d’accès échue pendant panne Portal | Nouvelle commande refusée ; état du monde continue de progresser |
| Révocation livrée | Game applique une nouvelle révision, invalide les sessions et refuse les nouveaux effets après commit |
| Révocation non livrable | Ancien droit utilisable jusqu’à son échéance locale, au maximum 8 h depuis confirmation ; aucune révocation instantanée promise |
| Logout Game | Révocation de la session locale concernée, sans arrêter le monde ou les autres univers |
| Logout global | Révocation des sessions Portal, propagation d’invalidation vers Game avec accusés ; UI distingue terminé et en attente |
| Game DB indisponible | Refus des accès/sessions et commandes ; aucun fallback cache permissif |

Logout global conserve les memberships, mais invalide les anciennes sessions et tickets via une
nouvelle révision et un nouvel epoch de chaque accès. Une reconnexion peut ouvrir une nouvelle session si les droits
restent actifs. Pour tous les accès déjà connus de Game, une confirmation en vol avant le logout
ne peut produire une validité au-delà de sa propre échéance absolue. La borne choisie s’applique
aux sessions échappant temporairement à la propagation. Suspension de compte utilise la même
livraison durable, avec suspension des accès, pas une simple suppression du cookie navigateur.

**Arbitrage principal :** accepter une fenêtre de droits périmés bornée à huit heures pour conserver
l’autonomie, ou réduire cette durée au prix d’une dépendance plus fréquente à Portal. L’isolation
ne peut garantir simultanément autonomie illimitée et révocation distante instantanée.

## 6. Compte et protections à cadrer avant 5C

Proposition initiale Q40 : email/mot de passe avec hash Argon2id via bibliothèque maintenue,
vérification email avant premier handoff, récupération à jeton court et usage unique. Alternative :
fournisseur OIDC, qui évite de porter le stockage du mot de passe mais ajoute une dépendance externe.
La sélection du login, de la bibliothèque, des paramètres, des durées de récupération et du
fournisseur email n’est pas faite ; aucune inscription publique avant ce cadrage.

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
| Session autonome | Portal coupé : lecture/mutation Game valide et échéance métier progressent ; aucun appel Accounts | 5D |
| Renouvellement et multi-parties | Renouvellement sans déconnexion des sessions encore valides ; deux onglets d’univers différents sans écrasement de cookie | 5C/5D |
| Révocation dégradée | Droit expiré refusé, grant retardé non prolongé, réactivation ne restaure pas les sessions | 5C/5D |
| Logout | Logout local/global, propagation partielle et retour Portal explicitement testés | 5C/5D |
| Clés | Rotation préchargée pendant panne Portal, clé inconnue refusée, procédure de compromission | 5C/5D |
| Navigateur | Cookies/CSRF/origines, absence de token dans URL/logs, mobile et clavier | 5C/5D |
| Isolation | Charge/panne Portal avec budgets Game mesurés et limites de l’hôte partagé consignées | 5D puis 17 |

## 9. Arbitrages et passage au lot suivant

| Questions | Proposition ou travail restant | Condition de sortie |
| --- | --- | --- |
| Q40 | Email/mot de passe vs OIDC, récupération | Choix utilisateur puis contrat détaillé avant compte |
| Q41 | Session Portal opaque et limites 7 j/24 h | Durées et stockage acceptés |
| Q42/Q56 | Ticket signé, 60 s, liaison navigateur, clés locales | Format/algorithme/rotation et recette validés avant handoff |
| Q43/Q44/Q54 | Session 8 h/2 h, validité de droits au plus 8 h, nouveau handoff | Fenêtre de révocation en panne explicitement acceptée |
| Q45 | Logout local et propagation globale distincts | UX et limites de confirmation validées |
| Q46 | mTLS interne recommandé, alternative credential TLS | Topologie et authentification opérables choisies |
| Q47 | Deux origines même site, cookies host-only, CSRF | Hôtes local/production et parcours testables définis |
| Q48/Q49/Q50 | MFA, email, anti-abus | Périmètre et contrôles minimaux avant exposition décidés |
| Q51/Q52 | Accès local versionné et bindings explicites | Permissions, transitions et règles de réactivation acceptées |
| Q53 | Intention Portal, application Game, outbox et révisions | Propriétaires, retry/réconciliation/rétention acceptés |
| Q55 | Préserver les règles privées/persistantes ouvertes | Aucun join public ajouté avant règles du mode |

La préparation de 5B est revue sur cette proposition ; 5B n’est pas déclarée achevée par sa seule
rédaction. Les choix acceptés devront être transcrits avec provenance dans les canoniques/Qxx
et une ADR dédiée si nécessaire. Les bibliothèques et paramètres cryptographiques se choisissent
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
