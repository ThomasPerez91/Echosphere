# UX-API-02 — Création de partie SOLO en libre-service

**Statut : implémenté sur `work/ux-api-02-solo-creation` (PR Draft vers `work/step-13b-first-contact`),
non fusionné ; tests PostgreSQL écrits, exécutés seulement par la Full CI après fusion.**
Provenance : demande utilisateur du 09/11/2026 après la recette du week-end (« pas moyen de créer
une partie ») et décisions [Q59](../01-game-design/game-modes.md#décisions-utilisateur-du-09112026--création-de-parties-q59).

## Parcours

1. Le joueur connecté remplit « Nouvelle partie » : nom (3 à 60 caractères, sans espace en bord),
   0 à 3 adversaires IA parmi les profils connus (`economic_cautious`, `expansionist`).
2. `POST /api/lobby/universes` (Portal) — session, origine, JSON et preuve CSRF obligatoires, limite
   horaire `universe_create` (20 par IP, 10 par compte, configurables). Corps :
   `{"request_id": UUID, "name": str, "family": "solo", "profiles": [...]}`. Le `request_id` est tiré
   une fois par formulaire : rejouer la même demande renvoie le même univers ; la même clé avec un
   autre contenu → 409 `creation_request_conflict`. `family` autre que `solo` → 422
   `family_unavailable` (multi et persistant : lots suivants). Aucune vérification d’adresse en plus
   (Q59) ; l’entrée dans l’univers garde sa règle existante (adresse vérifiée).
3. Une transaction Accounts enregistre l’intention (`universe_references` : `created_by`,
   `creation_request_id`, `start_request`) et la livraison `start_universe` dans l’outbox. La graine
   est tirée côté serveur (`secrets.token_urlsafe(24)`), jamais par le navigateur. Réponse
   `{"universe_id", "status": "starting"}`.
4. Le worker de contrôle livre `start_universe` à Game (mTLS, contrat `contracts/portal-game/v1`).
   Game exécute **le même démarrage atomique que la commande opérateur** (`app.ai.bootstrap`,
   ruleset épinglé `v0.9`) dans la transaction de l’opération : univers, galaxie, un Empire humain,
   0–3 Empires IA, reçu immuable. Une livraison rejouée relit le reçu ; une intention différente pour
   le même univers est refusée (`universe_content_conflict`), un univers déjà provisionné autrement
   aussi (`bootstrap_requires_empty_universe`).
5. Le reçu ne transporte que `universe_id`, `name`, `human_empire_id`, `started_at`. À son
   acceptation, Portal marque l’univers provisionné, mémorise l’Empire humain et accorde au
   créateur, **par le chemin membership/accès existant** (révision, époques, réconciliation), un
   binding sur cet Empire avec les 17 permissions. La partie apparaît alors dans « Mes parties ».

## Lecture du lobby

`GET /api/lobby/memberships` ajoute `creations` : les univers créés par le compte et pas encore
accordés (`{"universe_id", "name", "created_at", "state": "starting"}`). Ils disparaissent de la
liste dès que la participation existe.

## Limites connues

- Les IA ne jouent que si le processus `ai-worker` tourne (profil Compose `ai`) ; sans lui, leurs
  Empires restent inactifs, la partie reste jouable.
- Un refus définitif de Game (configuration invalide malgré la validation Portal) est retenté avec
  backoff, sans état « échec » visible : la création reste « en cours ». À traiter si observé.
- Ni suppression, ni abandon, ni pause de partie (Q59/Q27 : lots suivants).
- La migration Accounts `p0006_creation` n’ajoute que des colonnes nullables ; les univers créés
  par l’opérateur gardent ces champs vides.

## Vérifications

- Exécuté localement : tests purs Game `tests/test_control_contract.py` (3/3), Ruff Game et Portal.
- Fast CI : tests purs Portal `tests/test_universe_creation.py`, Game, lint, builds.
- **Non exécuté** (PostgreSQL indisponible ici, Full CI après fusion seulement) :
  `backend/tests/integration/test_control.py` (démarrage, rejeu, conflits),
  `portal/backend/tests/integration/test_control_outbox.py` (création, rejeu, accès du créateur,
  route HTTP) et `test_migrations.py` (tête `p0006_creation`). Recette Compose à faire.
