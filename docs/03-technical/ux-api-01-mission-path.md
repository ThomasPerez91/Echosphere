# UX-API-01 — Trajet réel d’une mission exposé par l’API Game

**Statut : principe validé par l’utilisateur le 03/11/2026 (D-UX-2). Contrat et plan rédigés par
Claude ; non implémenté. Changement backend à livrer dans une PR technique séparée de la PR #19.**
Contexte : [refonte UX/UI](../02-ux-ui/redesign/README.md), [Flottes API](fleets-api-ui.md).

## Besoin

La carte de commandement doit montrer par où passe une flotte. Aujourd’hui le serveur calcule le
chemin (`galaxy.known_path` sur les routes connues de l’Empire, persisté en `fleet_mission_legs`) mais
ne renvoie que `hops`. Le client ne doit pas recalculer ce chemin (règle de gameplay côté serveur).

## Contrat proposé

Champ additif `path`, liste ordonnée d’identifiants de systèmes : départ, systèmes intermédiaires,
destination. Longueur = `hops + 1` ; `[origine]` seul pour une mission de 0 saut.

| Endpoint | Ajout |
| --- | --- |
| `POST /game/{universe}/fleets/{empire}/missions/preview` | `path: [uuid, …]` dans le devis |
| `GET /game/{universe}/fleets/{empire}` → `missions[]` | `path: [uuid, …]` pour l’aller (le retour est le chemin inverse) |

Règles :

- Calculé exclusivement depuis le chemin déjà décidé par le serveur (`plan_mission` pour le devis,
  les `fleet_mission_legs` du snapshot pour une mission) ; aucune nouvelle requête de monde.
- Fog of War : seulement des systèmes déjà présents dans la Knowledge de l’Empire (le chemin passe
  par ses routes connues) ; aucun nom ni structure n’est ajouté (le client joint `path` à ses
  propres projections ; un système seulement détecté reste anonyme).
- Droits : mêmes que l’endpoint concerné ; aucun droit nouveau.
- Rétrocompatibilité : champ optionnel côté client. Le frontend accepte `path` absent (affichage
  « indicatif ») ou présent et valide (identifiants UUID, `length === hops + 1`) ; un `path`
  incohérent est ignoré, jamais « réparé ».
- Pas de changement de schéma ni de migration : les legs existent déjà (étape 9).

## Plan d’implémentation

1. `backend/app/fleet/service.py` : fonction pure `systems_along(session, universe_id, origin_id,
   route_ids)` (marche des routes, équivalente à `frontier.crossed_systems` mais disponible pour
   tous les rulesets ≥ v0.4), utilisée par `preview` (`path = [origin, *systèmes]`).
2. `backend/app/fleet/api.py` : `mission_view` ajoute `path` reconstruit depuis les legs ordonnés
   (`verified_path`) ; projection en lecture seule, aucun rattrapage.
3. Tests : purs (marche des routes, 0 saut) et PostgreSQL (devis et mission : `len(path) == hops+1`,
   départ = système de la flotte, destination = `destination_id`, aucun système hors Knowledge).
4. Frontend (après fusion backend) : validation de `path` dans `previewMission` et `validFleets`
   (déjà tolérée pour le devis dans la PR #19), affichage des étapes dans `MissionPlanner` et tracé
   sur `StarMap` ; position estimée le long du chemin.
5. Documentation : `fleets-api-ui.md`, ce document passé à « implémenté ».

Branche suggérée : `work/ux-api-01-mission-path` depuis la base qui contient les Flottes et 13B au
moment du travail (aujourd’hui la PR #17, comme la PR #19), Fast CI puis validation PostgreSQL locale.
