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
accordés (`{"universe_id", "name", "created_at", "state"}`). Ils disparaissent de la
liste dès que la participation existe. `state` (09/11/2026) est lu sur le dernier message de
contrôle non livré de l’univers (`creation_state`) :

| `state` | Condition | Affichage « Mes parties » |
| --- | --- | --- |
| `starting` | rien en échec, ou un seul échec réseau | « Création en cours », relecture toutes les 4 s |
| `delayed` | Game injoignable après 3 tentatives (`control_unavailable`, `unknown_target`) | « Création retardée » : demande conservée, renvoi automatique |
| `refused` | Game a répondu par un refus (`remote_conflict`, `remote_refused`, `invalid_receipt`) | « Création bloquée », sans relecture rapide ; journaux du worker de contrôle |

L’outbox reste « au moins une fois » : un refus continue d’être réessayé avec recul, il n’est jamais
abandonné en silence. Aucun corps de réponse distant n’est exposé, seulement l’état.

Chaque participation à un univers démarré porte aussi `started_at` (date du reçu Game) : « Mes
parties » affiche mode, joueurs et date de démarrage ; le nom d’Empire reste affiché en jeu
seulement (le Portal ne connaît que l’identifiant de la place).

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

## UX-API-03 — Parties multijoueurs (PRIVATE) et invitations

**Statut : implémenté sur `work/multi-private` (PR Draft vers `recette/ux-weekend`), non fusionné ;
tests PostgreSQL écrits, exécutés seulement par la Full CI après fusion.** Décisions : Q59.

- **Création** : `family: "private"` avec `humans` (2 à 4) et `invite` (`"link"` ou `"email"`, choisi
  une fois par le créateur) ; humains + IA ≤ 4 tant que la galaxie est `galaxy-v1` (4 points de
  départ maximum, vérifiés par ses règles). Les 10 joueurs et ~30 IA de Q59 attendent la future
  génération de carte (tailles, placement). Erreur `too_many_empires` au-delà.
- **Game** : `start_universe` accepte `family: "private"` et `humans` ; le démarrage atomique crée
  un Empire humain par place sur les premiers points de départ, puis les IA. Le reçu ajoute
  `human_empire_ids` (ordre des places, celle du créateur en premier). Les reçus SOLO existants ne
  changent pas (`humans` absent de l’intention quand il vaut 1).
- **Places** : Portal mémorise les places (`universe_references.seats`) ; le créateur reçoit la
  première. Une place libre est un Empire humain sans participation ; il évolue comme un Empire
  dormant jusqu’à l’arrivée de son joueur.
- **Lien** : `POST /api/lobby/universes/{id}/invite-link` (créateur) renvoie une fois
  `https://…/rejoindre#invite=<jeton>` ; seul le condensat du jeton est stocké, l’ancien lien est
  révoqué ; valable 7 jours, réutilisable jusqu’à ce que les places soient prises.
- **Email** : `POST /api/lobby/universes/{id}/invitations {"email"}` (créateur, limite horaire) ;
  invitation liée à une adresse, à usage unique, 7 jours ; jamais plus d’invitations ouvertes que de
  places libres ; envoi par le worker email (charge utile chiffrée, annulé si l’invitation n’est plus
  ouverte). Retrait : `POST /api/lobby/invitations/{id}/revoke`.
- **Rejoindre** : `POST /api/lobby/invitations/accept` avec `{"token"}` (page `/rejoindre`) ou
  `{"invitation_id"}` (invitation email listée dans « Mes parties ») ; refus `/decline`. Sous le
  verrou du compte puis de l’univers, la première place libre est accordée par le chemin
  membership/accès habituel (17 permissions). Codes : `invitation_not_found`,
  `invitation_other_account`, `game_starting`, `game_full` ; déjà membre → `member`.
- **Lobby** : chaque participation indique `family`, `creator`, `seats_total`/`seats_taken` et, pour
  le créateur, `invite_mode` et les invitations email envoyées ; `invitations` liste celles reçues.

Limites : pas de nom d’affichage des joueurs ni de liste des membres ; pas de départ/expulsion ;
un joueur qui s’inscrit depuis le lien doit rouvrir le lien après la confirmation de son adresse.
Migration Accounts `p0007_invitations`.

Vérifications UX-API-03 : tests purs Game `test_control_contract.py` (4/4) exécutés en session,
Ruff Game/Portal ; tests purs Portal et Vitest via Fast CI ; **non exécutés** :
`backend/tests/integration/test_control.py` (multi), `portal/backend/tests/integration/test_multiplayer.py`,
`test_migrations.py` (tête `p0007_invitations`) — Full CI après fusion ; recette Compose à faire.

## Q60 — Nom d’Empire, quitter une partie multi, archiver une partie SOLO (09/11/2026)

Décisions : [Q60](../01-game-design/game-modes.md#décisions-utilisateur-du-09112026--vie-dune-partie-q60).

| Action (Portal) | Route | Effet Game (outbox de contrôle) |
| --- | --- | --- |
| Nommer à la création | `empire_name` facultatif dans `POST /api/lobby/universes` (conservé dans la demande) | `name_empire` après le reçu `start_universe`, pour la place du créateur |
| Nommer en rejoignant | `empire_name` facultatif dans `POST /api/lobby/invitations/accept` | `name_empire` pour la place accordée |
| Renommer | `POST /api/lobby/universes/{id}/empire-name` `{"name"}` | `name_empire` |
| Archiver (SOLO, créateur) | `POST /api/lobby/universes/{id}/leave` | accès réduit aux droits `*.read` (consultation seule), rien d’effacé |
| Quitter (multi) | même route | accès `revoked`, puis `hand_over_empire` (profil `economic_cautious`) |

- Nom : 2 à 40 caractères visibles après réduction des espaces, sans caractère de contrôle ; même
  règle des deux côtés. Game refuse de renommer un Empire dirigé par une IA.
- `hand_over_empire` : Game refuse (`empire_still_bound`, réessai automatique) tant qu’une liaison
  humaine existe sur l’Empire, puis passe l’Empire en `ai` et active un `AIController` par le même
  chemin que le bootstrap (aucune ressource, unité ni connaissance offerte). Idempotent ; un autre
  profil pour le même Empire est un conflit. Un Empire IA ne peut plus être accordé à un humain.
- Portal : la place quittée est mémorisée (`left_seats`) et jamais reproposée ; la participation
  quittée apparaît sous « Parties quittées ». Migration Accounts `p0008_game_life`.
- Reçus vérifiés par le worker : univers, Empire et valeur appliquée (nom ou profil) en écho.

## Bascule v0.10, galaxie v2 et tailles de carte (A5 et Q61, 09/11/2026)

Décision utilisateur A5 : **toute nouvelle partie est en v0.10** (aucune partie existante à
préserver). `start_universe` exige `ruleset: "v0.10"` et accepte `size` ∈ {100, 300, 500, 1 000,
2 000} (100 par défaut), `humans` 1–10 et jusqu’à 30 profils IA ; Game vérifie le plafond
d’Empires de la taille contre le ruleset épinglé (`invalid_bootstrap_configuration` sinon) et
génère exactement un départ par Empire (galaxy-v2, placement Équitable). Portal : `size` facultatif
dans `POST /api/lobby/universes`, conservé dans la demande (idempotence), pré-contrôle des plafonds
(`too_many_empires`) ; « Nouvelle partie » propose la taille, 2–10 joueurs et deux compteurs d’IA
(prudentes, expansionnistes) bornés par le plafond. Les rulesets v0.6–v0.9 gardent leurs limites
(4 Empires, galaxy-v1) pour les tests et l’opérateur.
