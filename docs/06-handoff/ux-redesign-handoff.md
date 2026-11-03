# Passation — refonte UX/UI (pour ChatGPT Work ou tout autre agent)

**Statut : passation écrite par Claude le 03/11/2026 en fin de première session. Règles communes :
[AGENTS.md](../../AGENTS.md). Plan et décisions : [refonte UX/UI](../02-ux-ui/redesign/README.md).**

## Où en est le chantier

| Champ | Valeur |
| --- | --- |
| Branche | `work/ux-redesign`, créée depuis `b97bd0e` (tête de `work/step-13b-first-contact`) |
| PR | [#19](https://github.com/ThomasPerez91/Echosphere/pull/19) **Draft**, base `work/step-13b-first-contact` (dépend de #17, elle-même de #16) |
| Tête et CI | Voir le bloc « Reprise rapide — refonte UX » de [progress](../../progress.md) |
| Écrivain actif | Aucun après cette passation ; **un seul agent à la fois** sur cette branche |
| Hors périmètre | master, branches de #16/#17/#18, backend, migrations, `game_data`, règles |

## Ce qui est livré

- UX00 audit, UX01 navigation et 8 wireframes, UX02 trois directions + tokens + architecture des
  composants et cosmétiques, UX03 prototype React isolé et testé.
- Le prototype n’appelle aucune API : adaptateur `MissionApi` alimenté par `src/prototype/fixtures.ts`.

## Ce qui attend l’utilisateur

1. Choisir la direction artistique (D-UX-1) **avant** toute refonte graphique des écrans réels.
2. Décider UX-API-01 (D-UX-2) : chemin de mission exposé par l’API (changement backend, à faire dans
   un lot autorisé, pas dans cette PR).
3. Valider le parcours du prototype (critère : un nouveau joueur envoie une flotte sans aide).

## Comment reprendre

```bash
git fetch origin && git switch work/ux-redesign   # vérifier d'abord : git status propre, SHA = PR #19
cd frontend && npm ci && npm run prototype         # http://localhost:5173/prototype/
npm run lint && npm test && npm run build
```

Règles à garder :

- Ne pas importer `src/prototype/` depuis `src/main.tsx` ni le pousser en production sans décision.
- Aucune règle métier côté client : trajets, coûts, durées, refus = réponses serveur.
- Fog of War : n’afficher que les projections de l’Empire ; aucune donnée inventée dans l’application.
- Garder la parité clavier/mobile (cibles 44 px, pas de survol seul) et les tests Chromium multi-largeurs.
- Ne jamais présenter un test comme exécuté sans run réel ou CI vérifiée sur le SHA.

## Prochaine tâche recommandée

« Incrément réel 1 » du plan : dans la route Galaxie, derrière un interrupteur explicite, composer
`CommandMap` avec `readGalaxy` + `readFleets`, `previewMission`, `fleetCommand(…"/missions"…)`,
relecture de la projection après commande ; tests Vitest (mocks `fetch` comme `Galaxy.test.tsx` /
`Fleet.test.tsx`) et Chromium ; l’ancien parcours reste disponible jusqu’à validation. Extraire au
passage le moteur de zoom/déplacement de `GalaxyView.tsx` pour `StarMap`.

## Pièges connus

- Les projections Galaxie (coordonnées, routes) et Flottes (systèmes, flottes, missions) sont
  séparées : joindre par identifiant de système, même Empire.
- `MissionView` et `Quote` n’ont pas de chemin : sans UX-API-01, afficher le nombre de sauts et une
  ligne indicative (mode « contrat actuel » du prototype).
- La Fast CI ne se déclenche pour cette PR que grâce à l’entrée temporaire `work/step-13b-first-contact`
  dans `.github/workflows/ci.yml` ; la retirer au rebase sur master.
- Fast CI sur `6ba6d89` : lint sans avertissement, 114 tests Vitest (dont 14 du prototype), build.
