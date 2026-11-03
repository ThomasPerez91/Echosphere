# Refonte UX/UI — plan de travail

**Statut : chantier ouvert le 03/11/2026 sur demande de l’utilisateur. Premier intervenant : Claude
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
| [UX01 — Navigation](ux01-navigation.md) | Architecture, parcours cibles, 8 wireframes SVG, besoins de données | Proposé |
| [UX02 — Design system](ux02-design-system.md) | 3 directions, recommandation A, tokens sémantiques, composants, cosmétiques | Proposé, **validation requise** |
| [UX03 — Prototype](ux03-prototype.md) | Prototype React isolé Galaxie → Flotte → Mission, tests | Publié |
| [Passation](../../06-handoff/ux-redesign-handoff.md) | Reprise par un autre agent | Fait |

## Décisions prises dans ce lot (réversibles, techniques)

- Prototype dans une entrée Vite séparée (`frontend/prototype/index.html`), jamais importé par
  l’application ; fixtures typées avec les types réels et contrôlées par les validateurs de production.
- Parcours **centré sur le lieu** : carte → action → flotte → unités → résumé serveur → confirmation.
- Tokens **sémantiques** et trois directions sur le même balisage (`data-direction`).
- Fast CI ajoutée temporairement pour les PR ciblant `work/step-13b-first-contact` (même principe
  que l’exception déjà autorisée pour #17), à retirer après la fusion de #17.

## Choix ouverts (arbitrage utilisateur)

| Id | Question | Proposition |
| --- | --- | --- |
| D-UX-1 | Direction artistique de l’interface | A — Console orbitale, avec grille de carte (B) et chiffres tabulaires (C) |
| D-UX-2 | **UX-API-01** : exposer le chemin (`path`) dans l’aperçu et dans les missions | Oui : seule façon d’afficher les étapes sans recalculer le trajet côté client |
| D-UX-3 | Ordre et noms des domaines (Q15) | Empire, Galaxie, Colonies, Recherche, Flottes, Rapports, Diplomatie |
| D-UX-4 | Unités engagées par défaut | Toutes les unités adaptées à l’action (ajustables) |
| D-UX-5 | Garnison proposée comme expéditrice (détachement) | Oui, signalée « garnison » |
| D-UX-6 | Écran Rapports unique et cloche d’alertes | Oui, composés côté client d’abord |
| D-UX-7 | Refonte du Portal/lobby | Hors de ce premier lot ; audit léger seulement |

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
