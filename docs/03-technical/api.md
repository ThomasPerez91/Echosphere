# Contrats API

**Statut : sondes implémentées ; gameplay futur.**


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
idempotente des commandes avant les premières mutations. Format d'erreur global : Q16.

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
aucun compte, membership ou owner_user_id n'est ajouté maintenant. controller_type human/ai n'est
pas un droit d'accès. Règles gameplay futures par instance/ruleset ; aucune présence de navigateur
nécessaire à la progression. Notifications/WebSockets futurs restent des projections, jamais autorité.
[Modes](../01-game-design/game-modes.md) · [ADR 0006](../adr/0006-universe-game-instance.md).

## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Contrats Portal/Game à définir en 5B — non implémentés

Les [contrats 5B](identity-contracts.md) distinguent les décisions utilisateur du 2026-10-29
(login MVP, principes de récupération, limites Portal/Game/ticket et validité des droits)
des objets, opérations internes, erreurs et échanges encore proposés. Aucune route livrée.
Q40–Q44 sont partiellement closes, Q45 close pour le comportement produit, Q16/Q46–Q56 restent ouvertes ; aucune validation de protocole
ou de sécurité implémentée n’est déduite de ces arbitrages.

Décisions validées dans [ADR 0008](../adr/0008-control-plane-game-data-plane.md) : Portal expose
futurs services de compte/lobby, Game porte les commandes autoritaires et leurs projections.
Après handoff, GameSession autorise l’accès direct à Game sans proxy/consultation Portal par commande.
Game vérifie session → accès/membership/univers → permissions/empire → propriété et visibilité.
Login MVP fixé dans le canonique : email/mot de passe ; aucune nouvelle URL, forme de token/cookie
ou enveloppe d’erreur n’est fixée ici.

Les opérations internes provision universe, grant/revoke access, join et association membership/empire
passent exclusivement par Game, authentifiées service-to-service et idempotentes ; jamais par SQL
Portal→Game DB ni via une API publique normale. Clés d’idempotence, authentification, ordre/retry,
réconciliation et révocation restent à contractualiser (Q46/Q53/Q54). Un accès interne réseau seul
ne suffit pas à prouver une identité de service. Aucun endpoint interne ou public ajouté dans ce lot.
