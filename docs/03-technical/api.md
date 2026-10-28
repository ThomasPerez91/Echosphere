# Contrats API

**Statut : sondes implémentées ; gameplay futur.**


| Endpoint backend | Succès | Échec attendu | Utilité |
| --- | --- | --- | --- |
| GET /health | 200, `{"status":"ok"}` | Échec processus/HTTP | Liveness sans accès DB |
| GET /ready | 200, `{"status":"ready"}` | 503, `{"detail":"Database unavailable"}` | Connexion PostgreSQL et SELECT 1 |
| GET /docs | Documentation OpenAPI FastAPI | — | Développement local |

`/ready` utilise un délai de connexion de 3 secondes et un statement timeout de 3 secondes.
Les détails de connexion ne sont pas renvoyés. Aucune authentification ni donnée personnelle.
Le frontend appelle `/api/ready`, relayé par Vite sur `/ready`.

## Futurs contrats

Les routes métier ne sont pas créées à l'étape 0. Elles valideront identité, droits sur l'empire,
appartenance à l'univers et état des commandes. Ne jamais accepter les stocks, coûts, taux ou dates
de fin calculés par le client comme autorité. Définir pagination, erreurs structurées et clé
idempotente des commandes avant les premières mutations. Format d'erreur global : Q16.

Les réponses seront des projections filtrées selon la connaissance. Aucun endpoint « carte entière »
exposé puis masqué côté UI. L'affichage d'échéances nécessite des timestamps absolus UTC avec offset,
convertibles localement. WebSockets hors étape 0 ; polling futur seulement si besoin établi.


## Références

- [Architecture](architecture.md) · [Modèle](data-model.md) · [Temps](event-engine.md)
- [API](api.md) · [Qualité](../04-quality/testing-strategy.md) · [Questions ouvertes](../05-project/open-questions.md)
