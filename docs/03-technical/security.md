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


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
