# UX00 — Audit UX/UI de l’existant

**Statut : audit réalisé le 03/11/2026 par Claude (session cloud) sur le code de `b97bd0e`
(tête de la PR #17). Lecture du code et des tests frontend ; aucune session de jeu réelle observée
par l’auditeur. Les constats de l’utilisateur après sa première partie sont la source du besoin.**
Plan général : [refonte UX/UI](README.md).

## 1. Inventaire des écrans

| Écran | Route | Composant (lignes) | Contenu réel | Données |
| --- | --- | --- | --- | --- |
| Shell | `#universe/<id>/…` | `App.tsx` (170) | Sidebar 7 entrées (4 + « Plus » sur mobile), barre haute avec les stocks d’**une** colonie, titre/paragraphe par section | Session Game, Colony |
| Accès partie | dans Empire | `GameAccess.tsx` | États d’entrée/expiration GameSession | Handoff |
| Empire | `empire` | dans `App.tsx` | Stocks d’une colonie, construction en cours, lien Colonie. Pas de flottes, recherche, alertes ni échéances globales | Colony |
| Colonie | `colony/overview·infrastructure·orbit·defense` | `ColonyScreen.tsx` (233) | Ressources, secteurs, file, options de construction, menace annoncée ; Orbite et Défense « futurs » | Colony |
| Recherche | `research` | `ResearchView.tsx` (464) | Catalogue par domaine, active + suivante, dialogue de confirmation | Research |
| Galaxie | `galaxy` | `GalaxyView.tsx` (540) | Carte SVG (zoom, déplacement clavier), détail du système, liste ; bouton « Envoyer une flotte ici » qui **quitte la carte** | Galaxy (Knowledge) |
| Système | `galaxy/system/<empire>/<system>` | `SystemView.tsx` (118) | Structure, mondes, présences, routes ; liens « Coloniser… », « Attaquer… » vers Flottes | System |
| Flottes | `fleets`, `fleets/send|colonize|attack/…` | `FleetView.tsx` (626, un seul composant) | Production par colonie, flottes stationnées, missions, menaces, rapports de combat, rapports récents, Frontière ; un `<dialog>` à 7 modes | Fleets |
| Rapports | `reports` | aucun | Panneau « À venir » | — |
| Relations | `relations` | `RelationsView.tsx` (136) | Alertes diplomatiques, civilisations connues, actions de pacte, historique | Relations |
| Portal / lobby | application séparée `portal/frontend` | `account/…` | Compte, sessions, MFA, lobby, entrée dans une partie (handoff) | Accounts |

Les rapports existent bien côté serveur mais sont **dispersés** : missions et combats dans Flottes,
Frontière dans Flottes, historique diplomatique dans Relations, menace annoncée dans Colonie.

## 2. Pourquoi envoyer une flotte est si compliqué (priorité absolue)

Parcours actuel le plus court depuis la carte (lu dans `GalaxyView.tsx` et `FleetView.tsx`) :

1. Galaxie → sélectionner un système → bouton **« Envoyer une flotte ici »**.
2. Changement d’écran vers Flottes ; un dialogue s’ouvre avec **une flotte choisie automatiquement**
   (la première flotte stationnée ailleurs, garnison comprise) et un type déduit
   (Cartographie si signal, sinon Déploiement).
3. Le joueur doit comprendre cinq types de mission présentés en boutons radio sans explication
   contextuelle (Déploiement, Cartographie, Retour, Colonisation, Attaque).
4. Les unités engagées partent **à 0** : il faut saisir des nombres dans des champs numériques,
   sinon le serveur refuse.
5. La destination est une **liste déroulante de noms** (« Signal détecté — structure inconnue »
   répété pour chaque signal) ; aucun lien visuel avec la carte quittée.
6. Bouton « Calculer le devis », puis lecture d’un bloc de texte (sauts, durée, carburant,
   arrivée), puis le même bouton devient « Confirmer ».
7. Après l’envoi : la mission n’apparaît que dans une liste textuelle « Flottes en mission » ;
   **la carte n’affiche ni flottes ni missions**.

Causes racines :

| # | Cause | Effet joueur |
| --- | --- | --- |
| F1 | Parcours **centré sur la flotte** (commencer par une carte de flotte) alors que la décision part d’un lieu | Il faut savoir quelle flotte peut faire quoi avant de savoir où aller |
| F2 | La carte et les flottes sont deux écrans et deux projections sans lien visuel | Impossible de « voir » ses flottes, leur position, leur destination |
| F3 | Formulaire technique unique pour sept intentions (`send`, `split`, `merge`, `load`, `unload`, `cancel`, `recall`) | Charge cognitive, vocabulaire interne (TASK/GARRISON, devis, sauts) |
| F4 | Unités à 0 par défaut, champs numériques | Refus serveur `invalid_request` affiché « Action invalide. Actualisez la page. » au premier essai |
| F5 | Choix de la flotte automatique et silencieux depuis la carte | Le joueur ne sait pas quelle flotte part ni pourquoi |
| F6 | Destination par nom, signaux indiscernables | Erreurs de cible, aller-retour carte ↔ formulaire |
| F7 | Devis en deux temps et sans trajet visible | Le joueur ne voit pas *par où* passe la flotte ; risques mal compris |
| F8 | Aucune explication de ce que fait chaque action ni de pourquoi elle est indisponible | Boutons absents plutôt que désactivés avec une raison |
| F9 | Suivi uniquement textuel, barres « estimation locale » | Pas de sentiment de mouvement, pas de repère spatial |
| F10 | Le serveur ne transmet pas le chemin d’une mission (seulement `hops`) | Même une bonne UI ne peut pas dessiner les étapes sans extension d’API (voir UX-API-01) |

## 3. Défauts par gravité

| Gravité | Défaut | Écrans |
| --- | --- | --- |
| **Bloquante** (joueur coincé ou perdu) | F1–F7 ci-dessus ; flottes absentes de la carte ; rapports introuvables (section Rapports vide) | Galaxie, Flottes, Rapports |
| **Majeure** | Écran Flottes en une longue page de 8 sections (production, stationnées, missions, menaces, combats, rapports, Frontière) ; actions de gestion (diviser, fusionner, charger, décharger, protocole) mélangées à l’envoi ; Empire sans vue d’ensemble (ni flottes, ni recherche, ni alertes) ; alertes dispersées (menace dans Colonie, diplomatie dans Relations, détections dans Flottes) ; barre haute limitée à une colonie | Flottes, Empire, shell |
| **Majeure** | Textes d’état techniques (« Échéance atteinte, traitement du serveur attendu », « estimation locale », « instant logique ») et longs paragraphes explicatifs en tête d’écran | Tous |
| **Mineure** | Carte sans filtres ni recherche ; noms de systèmes « Signal détecté » non distingués ; légende séparée de la carte ; liste des systèmes en double de la carte sans lien de mise en évidence | Galaxie |
| **Mineure** | Protocoles 13B dans chaque carte de flotte (sélecteur + aide), lourd en lecture | Flottes |
| **Mineure** | Recherche : bonne base (domaines, active/suivante) mais pas de vue d’arbre ni de dépendances visuelles | Recherche |
| **Remarque** | Accessibilité déjà soignée (focus, `aria-current`, cibles 44 px, dialogues clavier, tests Chromium à 4 largeurs) : à conserver | Tous |

## 4. Parcours actuels ↔ capacités backend

| Capacité serveur (API Game) | Présente dans l’UI | Écart |
| --- | --- | --- |
| Knowledge galaxie (systèmes, routes, positions) | Carte Galaxie | Pas de couche flottes/missions |
| Missions Flottes : DEPLOY, SURVEY, RETURN, COLONIZE, ATTACK, devis, rappel | Dialogue Flottes | Parcours inversé (F1), aucun trajet affiché (F10) |
| Division, fusion, chargement, déchargement, annulation de production | Dialogue Flottes | Mélangés à l’envoi |
| Protocoles frontaliers, détections, rencontres, replis (v0.9) | Section Frontière | Non reliés à la carte (où ont eu lieu les détections) |
| Combat : alertes défenseur, rapports | Flottes, Colonie | Rapports non centralisés |
| Relations : contacts, pactes, historique, alertes | Relations | Correct, isolé du reste |
| Recherche : catalogue, active, suivante | Recherche | Correct |
| Colonie : constructions, file, annulation | Colonie | Correct ; Empire ne l’agrège pas |
| Chemin d’une mission (calculé par `known_path`) | — | **Non exposé par l’API** : proposition UX-API-01 |

## 5. Priorités de refonte

1. **P1 — Carte de commandement** (UX03) : parcours Galaxie → action → flotte → unités → résumé
   serveur → confirmation → suivi sur la carte ; flottes et missions visibles sur la carte.
2. **P2 — Flottes « gestion »** : production, composition, protocoles et rapports séparés de
   l’envoi ; une flotte = une fiche avec ses actions.
3. **P3 — Empire + centre d’alertes** : vue d’ensemble (colonies, recherche, flottes, menaces,
   échéances) et un fil d’événements unique.
4. **P4 — Rapports** : écran unique (missions, combats, frontière, diplomatie) avec filtres.
5. **P5 — Design system** : tokens sémantiques et composants partagés (UX02) avant toute refonte
   graphique générale, après validation d’une direction.
6. **P6 — Extensions d’API** strictement nécessaires (UX-API-01 chemin de mission), à décider.
