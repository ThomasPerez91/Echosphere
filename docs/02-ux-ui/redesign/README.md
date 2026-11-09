# Refonte UX/UI — plan de travail

**Statut : chantier ouvert le 03/11/2026 sur demande de l’utilisateur ; décisions D-UX-1 à D-UX-7
validées le même jour (ci-dessous). Premier intervenant : Claude
(session cloud) ; reprise prévue : ChatGPT Work. Branche `work/ux-redesign` (depuis `b97bd0e`,
tête de la PR #17) ; [PR #19](https://github.com/ThomasPerez91/Echosphere/pull/19) Draft vers
`work/step-13b-first-contact`. Aucune modification des règles, du backend ni des migrations.
Les propositions de ce dossier ne sont pas des décisions validées tant que l’utilisateur ne l’a pas dit.**

Objectif : transformer l’interface fonctionnelle en expérience de stratégie spatiale intuitive.
Critère de réussite : **un nouveau joueur comprend comment envoyer une flotte depuis la carte
galactique, sans documentation.**

## Livrables

| Lot | Contenu | État |
| --- | --- | --- |
| [UX00 — Audit](ux00-audit.md) | Inventaire, causes du parcours Flottes, défauts par gravité, écarts backend, priorités | Fait |
| [UX01 — Navigation](ux01-navigation.md) | Architecture, parcours cibles, 8 wireframes SVG, besoins de données | Ordre validé (D-UX-3) |
| [UX02 — Design system](ux02-design-system.md) | 3 directions, A retenue (D-UX-1), tokens sémantiques, composants, cosmétiques | Validé (D-UX-1) |
| [UX04 — Carte de commandement réelle](ux04-live-command-map.md) | Intégration dans la Galaxie réelle derrière un interrupteur | Implémenté (PR #19), testé sur API interceptée, recette en univers réel à faire |
| [UX03 — Prototype](ux03-prototype.md) | Prototype React isolé Galaxie → Flotte → Mission, tests | Publié |
| [Passation](../../06-handoff/ux-redesign-handoff.md) | Reprise par un autre agent | Fait |

## Décisions prises dans ce lot (réversibles, techniques)

- Prototype dans une entrée Vite séparée (`frontend/prototype/index.html`), jamais importé par
  l’application ; fixtures typées avec les types réels et contrôlées par les validateurs de production.
- Parcours **centré sur le lieu** : carte → action → flotte → unités → résumé serveur → confirmation.
- Tokens **sémantiques** et trois directions sur le même balisage (`data-direction`).
- Fast CI ajoutée temporairement pour les PR ciblant `work/step-13b-first-contact` (même principe
  que l’exception déjà autorisée pour #17), à retirer après la fusion de #17.

## Décisions validées par l’utilisateur — 03/11/2026

| Id | Décision |
| --- | --- |
| D-UX-1 | **Direction A « Console orbitale »**, avec la grille cartographique discrète de B et les chiffres tabulaires de C, sur les tokens sémantiques UX02. Base graphique de l’interface gratuite standard, compatible avec les collections d’illustrations standard et premium (PR #18) |
| D-UX-2 | **UX-API-01 validé dans son principe** : le serveur exposera le trajet réel (systèmes traversés, départ → étapes → destination). Changement backend **séparé de la PR #19** : [contrat et plan](../../03-technical/ux-api-01-mission-path.md). En attendant, l’interface n’affiche ni étape inventée ni ligne présentée comme trajet réel |
| D-UX-3 | Navigation : **Empire → Galaxie → Colonies → Recherche → Flottes → Rapports → Diplomatie** |
| D-UX-4 | Unités par défaut : Cartographie = **une sonde** ; Colonisation = **exactement un colonisateur** ; Déplacement = présélection adaptée, affichée et modifiable ; Attaque = unités militaires seulement, **composition choisie explicitement** ; une garnison n’est **jamais** engagée automatiquement. Aucun choix automatique ne doit dégarnir une colonie |
| D-UX-5 | Garnisons proposées quand un détachement est possible, **identifiées comme telles** ; le joueur choisit explicitement les unités détachées |
| D-UX-6 | Écran Rapports centralisé et cloche d’alertes **validés**, après le parcours Galaxie/Flottes |
| D-UX-7 | Refonte du Portal/lobby **reportée** ; priorité à Game |

## Composants : conserver, extraire, remplacer, supprimer

| Action | Éléments |
| --- | --- |
| **Conserver** | Clients API et validateurs (`*/api.ts`), hooks de données (`useFleets`, `useGalaxy`…), `colony/format.ts`, primitives `ui.tsx`, schémas d’accessibilité (focus de titre, `aria-current`, dialogues clavier), tests Chromium multi-largeurs |
| **Extraire** | De `FleetView.tsx` (626 lignes) : `Clock`, `Composition`, `Cargo`, `Losses`, `FrontierPanel`, `reportTitle`, dictionnaire des messages, un composant par dialogue ; de `GalaxyView.tsx` : moteur de carte (cadrage, zoom, déplacement clavier/pointeur) en `MapViewport` réutilisé par `StarMap` |
| **Remplacer** | Mode `send` du dialogue Flottes → `MissionPlanner` depuis la carte ; section Empire de `App.tsx` → tableau de bord ; panneau Rapports « À venir » → écran Rapports ; lien « Envoyer une flotte ici » → panneau d’actions de la carte |
| **Supprimer** (après remplacement et tests) | Routes de pré-remplissage `fleets/send|colonize|attack/…` et leur logique de choix automatique de flotte ; paragraphes explicatifs longs en tête d’écran |

## Ordre proposé pour la suite

1. Validation utilisateur : D-UX-1 (direction) et D-UX-2 (UX-API-01).
2. Incrément réel 1 : carte de commandement branchée sur l’API dans Galaxie (interrupteur), tests
   Vitest + Chromium, sans retirer l’ancien parcours.
3. Incrément 2 : dock flottes + suivi sur la carte réels ; rappel depuis la carte.
4. Incrément 3 : Flottes gestion (extraction des composants, fiche de flotte).
5. Incrément 4 : Empire + cloche + Rapports.
6. Déploiement graphique de la direction validée, écran par écran, avec captures avant/après.

## Commandes

```bash
cd frontend && npm ci
npm run prototype                         # prototype UX03
npm run lint && npm test && npm run build # mêmes contrôles que la Fast CI
npx playwright install chromium && npx playwright test e2e/prototype.spec.ts
python3 ../scripts/check_docs.py
```
