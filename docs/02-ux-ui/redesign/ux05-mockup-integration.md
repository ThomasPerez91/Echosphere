# UX05 — Intégration de la maquette HTML/CSS/JS (Portal, Empire, Colonie, Galaxie)

**Statut : implémenté sur `work/ux-redesign` (PR #19, Draft), non validé en univers réel.**
Demande utilisateur du 05/11/2026 : reprendre les éléments visuels et les assets de la maquette
« echosphere-dashboard » (accueil, connexion, inscription, mes parties, tableau de bord, colonie, vue
galaxie animée), adapter le frontend aux données réelles et afficher « Implémentation backend
nécessaire » pour toute fonctionnalité absente du backend. La maquette reste une référence visuelle :
son contenu métier (chiffres, noms, alliances, tours) n’est jamais repris comme donnée.

## Commits

| Commit | Contenu |
| --- | --- |
| `8922b7a` | Pack visuel : assets (icônes, illustrations, planètes, bâtiments, logos, fonds) dans `frontend/public/assets` et `portal/frontend/public/assets`, police Inter auto-hébergée (OFL), styles de la maquette portés (`frontend/src/theme/`) avec préfixe `d-` |
| `73e8409` | Nouvelle coquille de jeu (barre haute, ressources estimées, barre latérale, onglets mobiles) et tableau de bord Empire sur les projections réelles |
| `2c409e2` | Écran Colonie dans la mise en page de la maquette (stocks, secteurs, files, cartes de construction, annulation avec aperçu, alertes de combat) |
| `5c4f2df` | Galaxie : carte de commandement par défaut, fond animé, légende, menu contextuel, panneau système |
| `b8e1a43` | Portal : accueil, carte de compte, espace joueur « Mes parties », compte et sécurité |

## Ce qui vient du serveur

- **Coquille** : nom d’univers et lien Portal (GameSession), colonies et stocks (projection Colony ;
  stocks estimés entre deux lectures par taux × temps écoulé, plafonnés par la capacité, à titre
  d’affichage), état des services (readiness).
- **Empire** : stocks et productions, constructions et recherche actives, systèmes connus et mini-carte
  (Knowledge), flottes en mission, événements datés (missions terminées, recherches acquises, faits
  de relations), alertes dérivées de ces données.
- **Colonie** : projection Colony complète, construction/amélioration/annulation via l’API existante.
- **Galaxie** : projections Galaxy et Fleets du même Empire ; actions (déplacer, coloniser, attaquer,
  cartographier) proposées selon la Knowledge et les flottes, résumé serveur avant confirmation,
  rappel. Le fond animé (nébuleuse, territoire, brouillard) est calculé à partir de la Knowledge seule.
- **Portal** : session de compte, participations du lobby (statut, entrée, renouvellement, date de
  confirmation et de validité), reçus de déconnexion, MFA et opérations sensibles inchangés.

## Galaxie : « je clique = je découvre » adapté au backend

Dans la maquette, cliquer révèle un système. Ici, un clic sélectionne un système **connu de
l’Empire** : un menu contextuel ancré sur le système (bureau, ≥ 961 px) ou la feuille du bas (mobile)
liste les actions réellement possibles. La découverte passe par la mission serveur « Cartographier »
envoyée avec une sonde, jamais par le clic. La carte de commandement devient la vue par défaut ; la
carte classique reste disponible en un clic (choix mémorisé par navigateur). Les specs Playwright qui
pilotent la carte classique la sélectionnent explicitement.

## Rapports (D-UX-6) et historique des constructions (PR #21)

L’écran Rapports compose côté client un fil daté, filtrable par catégorie (Constructions, Missions,
Combats, Frontière, Recherche, Diplomatie) et groupé par jour, à partir de ce que le serveur conserve :
historique paginé des constructions terminées de chaque colonie (`GET …/colonies/{id}/construction-history`,
contrat de la PR #21, curseur exclusif `before_sequence`, séquences en texte décimal validées), missions
terminées, rapports de bataille et faits de frontière de la projection Flottes, recherches acquises,
historique diplomatique. Aucune entrée n’est prédite côté client. Un serveur Game sans la route (PR #21
non déployée) répond 404 : l’historique des constructions est signalé indisponible, le reste du fil
fonctionne. « Actualiser » repart de la première page ; les pages suivantes s’ajoutent sans doublon.
Le tableau de bord Empire réutilise les mêmes fonctions d’événements et renvoie vers Rapports.

## Implémentation backend nécessaire (backlog)

| Écran | Fonctionnalité affichée en attente |
| --- | --- |
| Coquille | Messages, notifications, emblème et devise d’Empire, profil |
| Empire | Classement / puissance, objectifs, diplomatie hors pactes |
| Rapports | Cloche d’alertes, rapports non lus, recherche et export du fil ; historique au-delà de ce que conserve la projection Flottes |
| Colonie | Accélération de construction, Orbite (emplacements orbitaux, routes), Défense (modules), objectifs, population/moral si décidés |
| Galaxie | Distance entre systèmes, onglet « Données » (ressources, anomalies, historique d’observation), filtres Alliés/Neutres/Hostiles, systèmes hostiles dans la légende, régions, vue « Influence » |
| Portal | Invitations, actualités, statistiques publiques, catalogue d’univers ouverts, création de partie, Empire / mode / tour par partie, journal d’activité des parties, notifications |

Ces éléments ne reçoivent aucune valeur inventée : bloc pointillé ambre, « N/D » ou contrôle désactivé.

## Vérifications

- Fast CI : `2c409e2` run 42096869835 success, `5c4f2df` run 42097919962 success ; `b8e1a43` : voir PR.
- En session (sans registre npm) : bundles esbuild du jeu et du Portal ; parcours Chromium (Playwright
  Python) avec API interceptées à 390 et 1440 px — Empire, Colonie, Galaxie (sélection, menu
  contextuel, planification), Portal public et connecté : sans débordement horizontal ni erreur de
  console ; vérification de types partielle (tsc strict avec déclarations React minimales).
- **Non exécuté** : specs Playwright `e2e/` avec Vite (Full CI sur master uniquement), recette en
  univers réel (Compose), lecteurs d’écran réels.

## Recette locale

Procédure pas à pas : [recette locale UX05](ux05-recette-locale.md) (branche `recette/ux-weekend`).

## Limites connues

- Le fond animé de la galaxie suit la vue de la carte mais ne remplace pas la recette visuelle sur
  appareils réels (performance mobile à mesurer).
- Les illustrations de partie du Portal sont choisies de façon stable par identifiant d’univers
  (décoratives) : le Portal ne connaît pas encore l’illustration d’un univers.
- `missions[].path` (UX-API-01, PR #20) n’est pas encore consommé par le frontend.
