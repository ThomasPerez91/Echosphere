# Historique des constructions terminées — W-UX-05

**Statut : extension technique additive autorisée par la demande UX du 05/11/2026 ; PR dédiée,
Draft, depuis `b97bd0e` (PR #17). Aucun changement de gameplay ou de migration.**

L’écran Rapports doit pouvoir consulter les achèvements déjà persistés. `ConstructionOrder`
conserve `completed_at` à la date logique de l’événement, le secteur, le type et le niveau atteint.
La nouvelle projection expose ces faits sans inventer de journal ni de mécanique de notification.

## Contrat

`GET /api/game/{universe_id}/colonies/{colony_id}/construction-history`
(API FastAPI sans le préfixe `/api` du proxy). En-tête `X-Game-Request: bootstrap` et GameSession.
Paramètre optionnel unique `before_sequence` : entier strictement positif ≤ BIGINT signé maximal.
Les autres paramètres et les doublons sont refusés (422).

| Champ | Contenu |
| --- | --- |
| `server_time` | Instant de lecture UTC |
| `colony_id`, `empire_id` | Colonie autorisée et son Empire |
| `entries` | Au plus 50 constructions `completed`, par `sequence` décroissante |
| `entries[].id` | Identifiant de l’ordre |
| `entries[].sequence` | Entier décimal en texte (pas de perte JavaScript) |
| `infrastructure_type`, `sector_index`, `target_level` | Faits de l’ordre, pas de recalcul depuis le catalogue courant |
| `completed_at` | Date logique persistée, pas l’heure d’ouverture de l’écran |
| `next_before_sequence` | Dernière séquence de la page si une autre page existe ; sinon `null` |

La page suivante demande `before_sequence=<next_before_sequence>`. La comparaison est exclusive.
Les nouveaux achèvements ne déplacent pas ce curseur ; actualiser revient à la première page.
L’index existant `(colony_id,status,sequence)` sert cette lecture bornée. Aucun snapshot,
clé d’idempotence, coût confidentiel, ordre actif ou annulé n’est sérialisé.

## Sécurité et chronologie

Même chaîne que Colony : GameSession → GameAccess effectif → EmpireBinding `colony.read` →
colonie du même univers. Colonie inconnue, autre Empire, autre univers, absence de lecture : 404
indistinguable. Session expirée/révoquée : refus existant. Le Portal n’est pas appelé.

Aucun catch-up économique, nouveau ScheduledEvent, écriture de gameplay ou prolongation de session.
Une construction en retard mais non traitée reste absente jusqu’au worker ou à une commande/lecture
Colony qui règle réellement sa chronologie. L’historique n’annonce jamais lui-même une fin.

## Validation et consommation

Tests PostgreSQL : dates logiques, absence de catch-up et d’activité, isolation, permission,
pagination 50+4 sans recouvrement, refus des curseurs invalides, absence de snapshot.
La suite Colony API complète reste incluse. Le frontend de la PR #19 consomme ce contrat optionnel,
affiche une indisponibilité partielle avec les anciens serveurs et propose les pages précédentes.
Aucune fusion des branches backend dans la branche UI.

Recette : base PostgreSQL dédiée `*_test`, `RUN_DB_TESTS=1`, puis
`pytest -q tests/integration/test_construction_history.py tests/integration/test_colony_api.py`.
Les validations réellement exécutées et leur environnement figurent dans [progress](../../progress.md).
