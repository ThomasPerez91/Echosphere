# UX03 — Prototype Galaxie → Flotte → Mission

**Statut : prototype React publié sur `work/ux-redesign` (PR #19, Draft). Données fictives
explicites, isolé du gameplay de production. Tests Vitest exécutés en Fast CI ; parcours vérifié
dans Chromium sur un bundle local (voir §5). Non branché sur l’API Game.**

## 1. Lancer

```bash
cd frontend && npm ci
npm run prototype            # ouvre http://localhost:5173/prototype/
npx vitest run src/prototype # tests du prototype
npx playwright test e2e/prototype.spec.ts   # préparé ; nécessite Chromium (npx playwright install chromium)
```

`npm run build` ne contient pas le prototype : Vite ne bâtit que `index.html`, et `src/main.tsx`
n’importe rien de `src/prototype/`.

## 2. Ce que montre le prototype

1. **Sélection** d’un système sur la carte (clic, toucher ou Tab + Entrée) ; une liste des systèmes
   sert d’alternative accessible.
2. **Ce qu’on sait** : signal anonyme (ni nom, ni structure) ou système cartographié (planètes
   connues, vos flottes présentes).
3. **Actions possibles** : Cartographier, Déplacer une flotte, Coloniser <monde>, Attaquer <monde>,
   désactivées avec une raison quand c’est impossible.
4. **Flotte** : cartes radio des flottes éligibles (lieu, unités adaptées) ; présélection si une seule.
5. **Unités** : toutes les unités adaptées par défaut, `−`/`+` ; colonisation = 1 colonisateur.
6. **Trajet** : tracé sur la carte et liste des étapes (mode « extension proposée »), ou ligne
   indicative et nombre de sauts (mode « contrat actuel »).
7. **Résumé serveur** : sauts, durée, arrivée, carburant (aller-retour pour une attaque), bataille,
   « à savoir » (risques connus, textes repris de l’écran Flottes actuel). Recalculé à chaque
   modification ; une réponse obsolète est annulée.
8. **Confirmation** puis **suivi** : message d’état, flotte en mouvement sur la carte (position
   estimée entre les dates du serveur), dock « Vos flottes » (où, quoi, vers où, Localiser). Après
   l’heure d’arrivée : « Arrivée — confirmation du serveur attendue », jamais un résultat inventé.

Contrôles de démonstration (bandeau) : direction artistique A/B/C, mode du trajet, horloge ×60/×600.

| Bureau (A) | Tablette | Mobile | Suivi |
| --- | --- | --- | --- |
| ![Bureau](img/ux02-direction-a-orbital.jpg) | ![Tablette](img/ux03-tablet-768.jpg) | ![Mobile](img/ux03-mobile-390.jpg) | ![Suivi](img/ux03-suivi-mission.jpg) |

## 3. Règles respectées

- **Aucune règle métier dupliquée** : trajets, durées, coûts, éligibilité finale et refus viennent de
  la réponse de l’API (ici des réponses fixes écrites à la main). Les actions *proposées* reprennent
  exactement celles de l’écran Flottes actuel (familles d’unités, mondes connus, droits).
- **Fog of War** : fixtures limitées à ce que le serveur enverrait à un Empire ; elles passent les
  validateurs de production `validFleets` et `validProjection` (test). Aucune flotte étrangère,
  aucun nom de signal, aucune route inconnue.
- **Contrats** : types réels (`FleetProjection`, `Projection`, `Quote`, `Plan`, `MissionView`) ; le
  seul ajout est `path` dans `FixtureQuote`, marqué comme proposition UX-API-01.
- **Accessibilité** : systèmes = boutons clavier, focus déplacé sur le titre du panneau, Échap pour
  annuler, `aria-live` sur le résumé, cibles ≥ 44 px, sans survol seul, mouvement réduit respecté.

## 4. Fichiers

| Fichier | Rôle |
| --- | --- |
| `frontend/prototype/index.html`, `src/prototype/main.tsx` | Entrée isolée |
| `src/prototype/PrototypeApp.tsx`, `directions.ts` | Bandeau de démonstration, directions |
| `src/prototype/CommandMap.tsx` | Conteneur carte + panneau + dock, machine d’états du parcours |
| `src/prototype/StarMap.tsx` | Carte SVG (systèmes, routes, flottes, missions, trajet) |
| `src/prototype/MissionPlanner.tsx`, `copy.ts` | Étapes flotte → unités → résumé → confirmation |
| `src/prototype/model.ts` | Fonctions pures de présentation (offres, éligibilité, positions, lignes) |
| `src/prototype/api.ts` | Adaptateur `MissionApi` (fixtures ; à remplacer par l’API réelle) |
| `src/prototype/fixtures.ts` | Données fictives typées |
| `src/prototype/prototype.css` | Tokens UX02 et styles, portée `.proto-root` |
| `src/prototype/*.test.ts(x)`, `e2e/prototype.spec.ts` | Tests Vitest, spec Playwright préparée |

## 5. Vérifications réellement effectuées

- Fast CI de la PR #19 : lint, Vitest (dont `model.test.ts` 8 tests, `CommandMap.test.tsx` 6 tests),
  `tsc -b` + build — voir les runs sur la PR.
- Session cloud : `model.test.ts` exécuté localement via esbuild ; parcours complet joué dans Chromium
  (Playwright Python) sur un bundle esbuild du prototype : clavier, présélection, recalcul, refus,
  Localiser, Fog, mode contrat, suivi ; aucune erreur console ; aucun débordement horizontal à 390,
  768 et 1440 px ; toutes les commandes ≥ 44 px.
- **Non exécuté** : `e2e/prototype.spec.ts` avec le serveur Vite (pas de registre npm dans la session).

## 6. Prochain incrément proposé (non fait)

Brancher `CommandMap` sur les vraies projections dans la route Galaxie existante derrière un
interrupteur explicite : `readGalaxy` + `readFleets` (même Empire), `previewMission`,
`fleetCommand(…"/missions"…)`, relecture de la projection après commande ; puis remplacer le
raccourci « Envoyer une flotte ici ». Prérequis : validation de l’utilisateur sur le parcours et
décision sur UX-API-01.
