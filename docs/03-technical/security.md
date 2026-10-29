# Sécurité

**Statut : contraintes validées ; protection production future.**


Backend autoritaire et PostgreSQL source de vérité. Ne jamais faire confiance aux identifiants,
stocks, coûts ou timestamps envoyés par le navigateur. Les futures commandes vérifient identité,
propriété, univers et visibilité avant tout effet.

## Protections locales conservées depuis l’étape 0

Pas de gestion d'utilisateurs, paiement ou administration. Ports frontend/backend liés à 127.0.0.1,
aucun port PostgreSQL publié. L'exemple .env contient seulement des valeurs publiques de développement ;
.env est ignoré. Ne pas réutiliser ces valeurs en production. Aucun secret dans un `VITE_*`.
Les erreurs de readiness sont génériques ; les conteneurs applicatifs utilisent un utilisateur non-root.

## Avant un accès distant

Implémenter et tester les [contrats 5B](identity-contracts.md) : identité/session, contrôles objet,
TLS/CSRF, limites et stockage des secrets ; compléter sauvegardes/restauration avant production.
Chaque frontend appelle son API même origine. CORS credentials refusé par défaut ; aucune origine
cross-origin sans besoin explicite et allowlist minimale.
La publication du serveur Vite sur internet n'est pas un déploiement supporté.

## Revue continue

Contrôler les dépendances et le lockfile, les logs et payloads contre les fuites de fog of war,
les courses de dépenses et le rejeu de commandes. Les vulnérabilités découvertes font l'objet d'une
correction ; ne pas ajouter de permissions GitHub ou de services cloud pour ce bootstrap local.


## Frontière d'instance et future participation

Universe isole les données de partie ; ne pas supposer un univers par utilisateur ou par processus.
Toute future API authentifiée contrôle User → Membership → Universe → permissions → Empire/Entity,
puis filtre aussi les informations selon le fog of war. Aucune donnée d'un autre univers ne doit
être lisible/modifiable via un identifiant d'entité fourni par le client. Un UUID opaque n'est pas
une autorisation. Les primitives génériques de stream exigent universe_id et vérifient son scope ;
les adaptateurs internes de colonie ne sont pas des routes HTTP et n'authentifient pas un joueur.

Account/User ↔ UniverseMembership ↔ éventuellement Empire ↔ rôle/permissions reste conceptuel ;
aucun compte, membership ou owner_user_id n'est ajouté maintenant. controller_type human/ai n'est
pas un droit d'accès. Règles gameplay futures par instance/ruleset ; aucune présence de navigateur
nécessaire à la progression. Notifications/WebSockets futurs restent des projections, jamais autorité.
[Modes](../01-game-design/game-modes.md) · [ADR 0006](../adr/0006-universe-game-instance.md).

## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Domaine interne Étape 5A

Aucune API gameplay, même read-only : l’absence de contrat de participation autorisé pourrait
créer une fuite. Les commandes internes reçoivent univers/empire/colonie explicites, vérifient la
propriété avant consultation puis sous le lock et dédupliquent les clés. Ces paramètres de confiance
ne sont pas un substitut à une session HTTP. La future API 5D vérifiera identité/membership/permissions avant
appel des mêmes services humains/IA/headless. Pas de faux user global ou bypass de Q16.

## Portal/Game — contrats 5B validés, protections futures non implémentées

[Canonique identité](identity-contracts.md) et [ADR 0008](../adr/0008-control-plane-game-data-plane.md) :
Accounts DB/Portal et Game DB/Game isolables. Aucun credential Accounts en Game DB, aucun SQL direct
Portal→Game. Interface interne privée mTLS avec autorisation ; outbox, effets idempotents et révisions
pour livraisons, renouvellements et révocations. Game contrôle localement ses droits sans appel Portal
par commande. Les choix ne valent ni implémentation ni preuve de sécurité production.

Contrats clos pour 5B selon le [registre Q40–Q56](../05-project/open-questions.md) :

- Email/mot de passe Argon2id, 15–128 caractères, refus des mots de passe courants/compromis sans
  transmission brute ; vérification initiale 24 h/unique avant tout handoff.
- Portal 7 j absolus/72 h inactif ; Game 8 h absolues/2 h inactif ; activité explicite classée
  serveur seulement. Accès Game au plus 8 h depuis confirmation Portal, jamais glissant ni relancé
  par panne ; reçu révoqué immédiatement, expiré refusé ; workers et univers continuent.
- Ticket signé asymétriquement 60 s/unique, pré-auth navigateur 5 min, consommation atomique ;
  clés prédistribuées, clé inconnue refusée localement, aucun secret URL/log/localStorage.
- Sessions opaques serveur, cookies Secure/HttpOnly/host-only, rotation à transition auth ; APIs
  même origine, CSRF, CORS credentials refusé par défaut ; exceptions explicites minimales seulement.
- Appareil = profil navigateur ; caps initiaux configurables 10 appareils/compte et 10 univers
  Game actifs/appareil ; jamais plafonds de memberships. Une GameSession compte/appareil/univers.
- Logout Game seul, compte sur appareil ou compte entier distincts ; révocations persistées/rejouées
  jusqu’à acquittement, UI en attente fidèle, aucune fenêtre de huit heures redémarrée.
- Reset 30 min/unique/dernier lien, changement volontaire du mot de passe et changement d’email
  réussi : révocation globale et connexion normale sans auto-login ; notifications sans credential.
  Email pending, demande unique 1 h et preuves non mélangeables ; liens invalidés entre flux selon
  canonique. Mot de passe seul ne contourne ni ancienne adresse inaccessible ni MFA.
- MFA facultative joueurs ; TOTP actif unique/cinq WebAuthn nommables ; WebAuthn privilégié requis,
  deux authentificateurs avant privilèges production. Step-up par action 5 min/unique lié session et
  paramètres ; catalogue inclut logout tous appareils, déconnexion ordinaire possible sans step-up.
- Révocation globale après activation/désactivation MFA, réduction/remplacement de protection ou
  récupération/reset MFA. **Aucune révocation globale imposée** après ajout d’authentificateur ou
  régénération volontaire de secours avec step-up via facteur déjà enregistré ; audit/notification.
- Dix secours ≥128 bits, uniques/affichés à génération seulement, stockage non réversible ;
  récupération 15 min sans Game/admin, facteur rétabli puis connexion normale et nouveaux secours.
  Perte totale bloquée sans procédure renforcée approuvée, jamais email/mot de passe seuls.
- Anti-abus compte/IP/opération, ralentissement progressif et quotas email/inscription, réponses
  non énumérables ; aucun verrouillage permanent provoqué par tiers, CAPTCHA tiers non obligatoire.
- Audit sécurité 90 jours avec accès restreint, aucun secret ; protection anti-rejeu conservée
  séparément. Secrets TOTP chiffrés avec clés séparées, WebAuthn sans secret privé côté serveur.

Détails techniques délégués : bibliothèques/paramètres mesurés, schémas, crypto, RP, verrous, retry,
rotation et tests. Fournisseur email/domaines/configuration avant production ; procédures support
joueur/privilégié différées, comptes bloqués sans procédure ; règles privées/persistantes dans leurs
lots. Aucun bypass ou service payant introduit par cette délégation.

Isolation CPU/RAM/pools/scaling/DB/réseau à éprouver. Deux applications sur le même hôte ne prouvent
pas la résistance à une saturation réseau ou DDoS. Aucun WAF/Redis installé ou utilisé comme autorité
gameplay. Les scénarios de refus, concurrence, reprise et panne sont des obligations de 5C/5D,
non des tests déjà exécutés. 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`) ; contrats toujours non implémentés.
5C est le lot courant autorisé, sans début de 5D.
