# UX04 — Carte de commandement dans la vraie Galaxie

**Statut : implémenté sur la PR #19 (Draft) le 03/11/2026, derrière un interrupteur ; testé sur
API interceptée (Vitest, Chromium), non validé en univers réel.** Plan : [refonte UX/UI](README.md).
Décisions appliquées : D-UX-1 à D-UX-5 ([plan](README.md#décisions-validées-par-lutilisateur--03112026)).
Chemin de mission : [UX-API-01](../../03-technical/ux-api-01-mission-path.md) (contrat proposé, non servi).

## Ce qui change pour le joueur

L’écran Galaxie propose deux affichages, choisis par le joueur et mémorisés dans son navigateur :

| Affichage | Contenu |
| --- | --- |
| **Carte classique** (défaut) | `GalaxyView` inchangée : carte, système, expéditions, raccourcis vers Flottes |
| **Nouvelle carte de commandement** | Carte, système sélectionné, actions possibles, planificateur pas à pas, « Vos flottes » |

Parcours de la nouvelle carte, sans quitter la carte ni ouvrir le grand formulaire Flottes :

1. Le joueur touche un système : ce que l’Empire en sait (signal détecté, cartographié, surveillé,
   votre colonie), ses planètes et routes connues.
2. Actions possibles, avec la raison en clair quand une action est impossible (pas de sonde, pas de
   colonisateur, pas de flotte ailleurs, droits manquants).
3. Choix explicite de la flotte s’il y en a plusieurs ; une seule flotte de mission est présélectionnée,
   une garnison n’est jamais présélectionnée et porte le libellé « Garnison — détachement ».
4. Unités, présélectionnées selon D-UX-4/5 et modifiables : une sonde (Cartographie), exactement un
   colonisateur (Colonisation), la flotte de mission telle qu’elle est (Déplacement), aucune unité
   pour une Attaque (composition militaire explicite), aucune unité d’une garnison sans choix.
5. Résumé du serveur (`POST …/missions/preview`) : départ, destination, sauts, durée, arrivée,
   bataille, carburant, unités, risques. Toute modification rend le résumé obsolète et le redemande.
6. Confirmation explicite : la commande part (`POST …/missions`), puis la carte revient au premier
   plan, la flotte apparaît en mission depuis les projections relues et se retrouve dans « Vos flottes ».

« Vos flottes » liste chaque flotte : où elle est, ce qu’elle fait, où elle va, l’heure d’arrivée ou
de retour (serveur), un avancement **estimé**, « Localiser » (centre la carte sur le système, ou sur la
position estimée d’une flotte en route) et « Rappeler… » avec confirmation quand la règle de l’écran
Flottes l’autorise encore. Les missions terminées restent consultables.

## Données et garde-fous

| Sujet | Règle appliquée |
| --- | --- |
| Projections | `readGalaxy` + `readFleets` du même Univers ; la projection Flottes suit l’Empire de la carte, la jointure (par identifiant de système) n’est faite que si les deux concernent cet Empire |
| Commandes | `previewMission`, puis `useFleets().run` : CSRF de la session, une clé d’idempotence par intention (réutilisée après un résultat inconnu), une commande à la fois, relecture après refus |
| Après acceptation | Relecture des deux projections ; aucune mission construite côté client |
| Trajet | Sans `path` serveur : nombre de sauts et ligne départ–destination marquée « représentation indicative » ; un `path` futur n’est utilisé que s’il est cohérent (sauts + 1, départ, destination, systèmes connus), jamais réparé |
| Positions | Interpolées entre les dates du serveur, toujours libellées « position estimée » |
| Fog of War | Un signal détecté n’a ni nom ni structure ; la recherche ignore les signaux ; aucune donnée hors projection |
| Indisponibilités | Galaxie ou Flottes indisponibles, droits manquants, session expirée : message en clair, carte classique accessible |

Aucun calcul de chemin, de coût ou de durée dans React ; aucun changement backend ni migration.

## Code

| Fichier | Rôle |
| --- | --- |
| `frontend/src/command/` | `CommandMap` (contrôlé), `StarMap`, `MissionPlanner` (flotte → unités → résumé → confirmation), `FleetDock`, `model.ts` (fonctions pures, D-UX-4/5), `types.ts` (`MissionApi`), `command.css` (direction A + grille discrète de B + chiffres tabulaires de C) |
| `frontend/src/command/LiveCommandMap.tsx` | Conteneur de production : hooks réels, alignement d’Empire, horloge serveur, adaptateur `MissionApi` |
| `frontend/src/components/GalaxyScreen.tsx` | Interrupteur « Nouvelle carte de commandement » / « Carte classique » |
| `frontend/src/fleet/messages.ts` | Messages serveur partagés avec l’écran Flottes |
| `frontend/src/prototype/` | Prototype UX03 conservé pour comparaison : mêmes composants, fixtures et écho local de démonstration |

Mobile (≤ 960 px) : le panneau devient une feuille contextuelle en bas d’écran (52 % de la hauteur),
la carte reste visible au-dessus, une décision par étape, Retour/Continuer collants, retour à la carte
après succès. Clavier : systèmes focalisables (Entrée), Échap annule, titres d’étape focalisés.

## Tests

| Test | État au 03/11/2026 |
| --- | --- |
| `src/command/model.test.ts` (11) | Exécuté en session (esbuild + Node) et en Fast CI |
| `src/command/CommandMap.test.tsx` (11) | Fast CI (pas de jsdom dans la session cloud) |
| `src/LiveCommand.test.tsx` (8, fetch intercepté) | Fast CI : projections, Empire, sélection sans envoi, résumé, CSRF/idempotence, relecture, résultat inconnu, refus, `path` mal formé, Flottes indisponibles, session expirée |
| Parcours Chromium sur l’application de production (bundle esbuild, API interceptée) | Exécuté en session à 390/768/1440 px : envoi, CSRF, clé, suivi, cibles ≥ 44 px, sans débordement |
| `e2e/live-command.spec.ts`, `e2e/prototype.spec.ts` | Écrits ; non exécutés avec Vite (Full CI sur master ou poste local) |

## Recette en univers réel (à faire en local)

Pré-requis : pile Compose de développement, univers avec un Empire humain, une colonie, une sonde,
une flotte de mission et un colonisateur (cf. [reprise](../../06-handoff/work-codex-handoff.md)).

1. `cd frontend && npm ci && npm run lint && npm test && npm run build && npx playwright test e2e/live-command.spec.ts e2e/prototype.spec.ts`.
2. Entrer dans l’univers depuis le lobby, ouvrir Galaxie, choisir « Nouvelle carte de commandement ».
3. Cartographier un signal avec une sonde ; déplacer une flotte ; coloniser un monde libre ; préparer
   une attaque sans la confirmer, puis la confirmer sur une cible de test ; rappeler une mission.
4. Vérifier pour chaque envoi : résumé identique à l’écran Flottes, mission visible sur la carte et
   dans « Vos flottes » puis dans l’écran Flottes, aucune double commande après un réseau coupé.
5. Vérifier Fog of War (signal sans nom), un compte sans `fleet.command`, un Empire sans flottes,
   la session expirée, et la carte classique toujours fonctionnelle.

Le parcours ne sera « validé en univers réel » qu’après cette recette.

## Limites connues

- Colonisation depuis une garnison : le cargo n’est pas réglable sur la carte (le serveur refuse si
  le paquet initial manque) ; l’écran Flottes reste le moyen complet.
- Sans UX-API-01, ni étapes du trajet ni courbe réelle ; l’avancement d’une flotte en route suit
  le segment départ–destination.
- Rapports centralisés et cloche d’alertes (D-UX-6) : après ce lot.
