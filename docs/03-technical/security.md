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

Définir auth et politique de session, contrôle d'accès objet, TLS, protections CSRF selon le mode
d'authentification, limites de requêtes, stockage des secrets, sauvegardes et restauration.
CORS restreint si des origins distincts sont nécessaires ; le proxy local évite ce besoin au bootstrap.
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

## Portal/Game — décisions validées, protections futures non implémentées

[Contrats 5B](identity-contracts.md) : décisions utilisateur du 2026-10-29 sur le login MVP
email/mot de passe avec Argon2id, email vérifié avant premier handoff, récupération courte/unique,
identité globale indépendante des méthodes et limites temporelles. Portal : 7 j absolus/72 h
d’inactivité ; Game : 8 h absolues/2 h d’inactivité ; ticket : 60 s/unique. Droits Game au plus 8 h
depuis confirmation Portal, non glissants, sans reset en panne ; révocation/suspension reçue immédiate.
Renouvellement avec Portal disponible et nouvelle confirmation/handoff valide, refus à valid_until.
Seules les interactions explicites classées côté serveur réinitialisent l’inactivité ; polling et
autres trafics automatiques exclus, aucun timestamp navigateur faisant autorité. Les limites
absolues et valid_until restent inchangées.
Ces décisions restent non implémentées ; mécanismes de session, crypto, interface interne et
protections conservent leur statut Proposition/Question ouverte.

[ADR 0008](../adr/0008-control-plane-game-data-plane.md) : compte global multi-parties, deux backends
isolables et deux bases distinctes/séparables. Portal gère credentials et sessions de compte ; Game
ne possède que l’identité minimale et les autorisations de partie nécessaires, jamais les credentials.
Aucun accès SQL direct Portal→Game DB ; interface Game interne authentifiée et idempotente.
Les requêtes gameplay passent directement à Game avec sa session propre après ticket court/unique.
La validation Game doit rester locale au plan Game, sans contacter Portal/Auth à chaque commande.

Portal est exposé aux bots/brute force/scraping/spam/DDoS applicatif ; protections futures possibles :
CDN/WAF, rate limiting IP/compte, anti-bot/challenge/CAPTCHA si nécessaire, email verification et
Redis temporaire. Aucun outil/protocole/fournisseur n’est choisi ou installé ici. Redis/WAF ne sont
jamais source de vérité gameplay. Game protège aussi son ingress, objets, univers et fog.
Isolation CPU/RAM/pools/scaling/DB/réseau à éprouver ; ne pas promettre une protection DDoS par le seul
fait d’avoir deux applications sur une machine partagée.

Q45 validée, non implémentée : retour lobby sans logout ; déconnexion Game d’une seule session ;
logout Portal de la session courante et de toutes les GameSessions du compte sur cet appareil ;
action distincte pour toutes les sessions du compte sur tous les appareils/univers. Conservation
des memberships/empires/états et de la progression/actions acceptées. Révocation globale persistée,
rejouée jusqu’à acquittement ; UI terminée/en attente, aucune instantanéité si Game injoignable.
Regroupement appareil Q41/Q43 et protocoles Q53/Q54 restent ouverts. Un epoch commun à tous les
appareils ne peut servir au logout d’un seul appareil sans violer sa portée validée.

Q16 est **partiellement cadrée**. Seules les parties listées de Q40–Q44 sont closes ;
cookies/stockage, CSRF, MFA, fournisseur email, anti-abus, format/crypto du ticket, protocoles de
renouvellement/révocation/logout, S2S, rôles/membership/synchronisation et politiques de modes
restent ouverts. Q46–Q56 ne sont pas fermées ; pas de JWT/OAuth/mTLS sélectionné.
Autonomie d’une session pendant panne Portal ne signifie pas ignorer toute révocation indéfiniment :
fenêtre de huit heures validée, mécanismes restant à définir et tester avant API interactive.
Aucun compte fictif global.
