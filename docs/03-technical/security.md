# Sécurité

**Statut : contraintes validées ; protection production future.**


Backend autoritaire et PostgreSQL source de vérité. Ne jamais faire confiance aux identifiants,
stocks, coûts ou timestamps envoyés par le navigateur. Les futures commandes vérifient identité,
propriété, univers et visibilité avant tout effet.

## Étape 0

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
