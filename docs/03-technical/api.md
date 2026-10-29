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
aucun compte, membership ou owner_user_id n'est ajouté maintenant. controller_type human/ai n'est
pas un droit d'accès. Règles gameplay futures par instance/ruleset ; aucune présence de navigateur
nécessaire à la progression. Notifications/WebSockets futurs restent des projections, jamais autorité.
[Modes](../01-game-design/game-modes.md) · [ADR 0006](../adr/0006-universe-game-instance.md).

## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)

## Contrats Portal/Game validés en 5B — non implémentés

[identity-contracts](identity-contracts.md) porte les autorités, opérations internes, handoff,
sessions, erreurs et règles compte/MFA validés le 2026-10-29. Le [registre Q40–Q56](../05-project/open-questions.md)
distingue contrats clos, détails techniques délégués et reports. Aucun endpoint livré ; les sondes
restent les seules routes Game actuelles. C01 ajoute les sondes Portal séparées,
[documentées ici](portal-foundation.md), aucune route de compte ou gameplay. 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`) ; contrats toujours non implémentés.

Portal expose les futurs services compte/lobby. Après ticket signé 60 s/unique lié au navigateur,
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
POST de handoff et activité explicite classée côté serveur sont des obligations du contrat, pas
des protections déjà présentes dans le runtime. Aucun secret localStorage.

5C compte/lobby est le lot courant autorisé ; cadrage avant code substantiel. 5D API Colony/UI
protégée reste hors lot et nécessitera son instruction distincte. Tests futurs
et prérequis opérationnels sont référencés dans la matrice du canonique ; aucun test d’auth réalisé
par la rédaction. [ADR 0008](../adr/0008-control-plane-game-data-plane.md).
