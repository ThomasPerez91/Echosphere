# UX01 — Nouvelle architecture de navigation et parcours joueur

**Statut : proposition de Claude du 03/11/2026 ; ordre des domaines validé par l’utilisateur le même
jour (D-UX-3 : Empire → Galaxie → Colonies → Recherche → Flottes → Rapports → Diplomatie).** Les
routes de production ne changent qu’au fil des incréments. Elle conserve les sept domaines Game existants et la sous-navigation canonique Colonie (Vue d’ensemble /
Infrastructures / Orbite / Défense). Audit : [UX00](ux00-audit.md) ; plan : [README](README.md).

## 1. Principes

1. **Partir du lieu, pas de l’outil** : on décide d’abord *où* agir (carte, colonie, rapport), puis
   *comment* ; l’outil (flotte, file, recherche) est proposé dans le contexte.
2. **Une action = un panneau contextuel progressif** (étapes visibles, une décision par étape,
   valeurs par défaut sûres) plutôt qu’un formulaire à sept modes.
3. **Toujours dire pourquoi** : une action impossible reste visible, désactivée, avec la raison et
   le moyen d’y remédier (« Aucune sonde stationnée : produisez une Sonde »).
4. **Le serveur répond, l’interface explique** : trajets, coûts, durées, refus viennent de l’API ;
   l’interface reformule en langage joueur, sans recalculer.
5. **Tout ce qui bouge se voit sur la carte** (flottes stationnées, missions, menaces annoncées
   connues, détections) ; chaque élément de liste peut être « localisé ».
6. **Un seul fil d’événements** (alertes + rapports) accessible partout par la cloche.
7. **Mobile d’abord pour les décisions courtes** (feuille d’actions en bas, cibles 44 px, clavier
   et lecteur d’écran à parité : pas de survol seul).

## 2. Architecture proposée

| Domaine (ordre proposé) | Rôle | Contenu principal | Changement par rapport à l’existant |
| --- | --- | --- | --- |
| **Empire** | « Que dois-je faire maintenant ? » | À faire (menaces, propositions, files vides, recherche finie), colonies, flottes, recherche, derniers rapports, frise des échéances | Aujourd’hui une seule colonie : devient l’agrégat de l’Empire |
| **Galaxie** (carte de commandement) | Agir dans l’espace | Carte + panneau contextuel + dock « Vos flottes » ; Système en panneau ou en page de détail | Absorbe l’envoi de flottes et le suivi des missions |
| **Colonies** | Gérer ses mondes | Sélecteur de colonie, sous-navigation canonique, grille de secteurs cliquable, file, menaces | Même contenu, accès par secteur |
| **Recherche** | Progresser | Arbre par domaine, active/suivante, détail | Vue arbre (même catalogue) |
| **Flottes** (gestion) | Organiser | Liste + fiche de flotte, production, protocoles, historique | L’envoi part de la carte ; la gestion reste ici |
| **Rapports** | Comprendre ce qui s’est passé | Fil filtrable : missions, combats, frontière, diplomatie, colonies | Écran aujourd’hui vide ; regroupe les rapports dispersés |
| **Diplomatie** (Relations) | Négocier | Propositions en attente, civilisations, fiche, historique | Inchangé sur le fond ; libellé à arbitrer |

Barre haute : univers et Empire, **stocks de la colonie active** (sélecteur), cloche d’alertes
(compteur + panneau), commandant/compte. Mobile : quatre entrées (Empire, Galaxie, Flottes, Plus) ;
la cloche reste en haut. Les noms « Colonies » (pluriel) et « Diplomatie » sont des propositions.

## 3. Parcours joueur cibles

| Parcours | Étapes |
| --- | --- |
| **Envoyer une flotte** (critère de réussite) | Galaxie → toucher un système → lire « ce qu’on sait » et « actions possibles » → choisir l’action → choisir une flotte éligible (présélection si une seule) → unités (toutes par défaut, − / +) → résumé serveur (étapes, durée, arrivée, carburant, bataille, « à savoir ») → Confirmer → la mission apparaît sur la carte et dans le dock |
| Cartographier un signal | Signal (anonyme) → « Cartographier » → sonde présélectionnée → résumé → confirmer → arrivée puis analyse visibles |
| Coloniser | Système connu → monde libre connu → « Coloniser » → Pionnier présélectionné, cargo engagé → minimum du paquet rappelé → confirmer |
| Attaquer | Monde connu → « Attaquer » → flottes militaires seulement → bataille ≥ 24 h affichée, défense inconnue rappelée → confirmer |
| Retrouver ses flottes | Dock « Vos flottes » ou Flottes → « Localiser » → la carte sélectionne le système, le panneau montre la flotte |
| Rappeler | Mission sur la carte ou dans le dock → « Rappeler » (si encore possible selon le serveur) → aperçu du retour → confirmer |
| Réagir à une alerte | Cloche → alerte → objet concerné (colonie, système, rapport) → décision |
| Construire | Colonies → secteur → action proposée (construire/améliorer) → coût/durée serveur → confirmer |
| Négocier | Empire « À faire » ou Diplomatie → proposition → accepter/refuser |

## 4. Wireframes (basse fidélité, structure seulement)

| Écran | Fichier |
| --- | --- |
| Galaxie — carte de commandement (bureau) | [01-galaxie-commandement.svg](wireframes/01-galaxie-commandement.svg) |
| Galaxie — mobile, feuille d’actions | [02-galaxie-mobile.svg](wireframes/02-galaxie-mobile.svg) |
| Empire — tableau de bord | [03-empire.svg](wireframes/03-empire.svg) |
| Flottes — gestion | [04-flottes-gestion.svg](wireframes/04-flottes-gestion.svg) |
| Colonie | [05-colonie.svg](wireframes/05-colonie.svg) |
| Recherche — arbre | [06-recherche.svg](wireframes/06-recherche.svg) |
| Rapports et alertes | [07-rapports-alertes.svg](wireframes/07-rapports-alertes.svg) |
| Diplomatie | [08-diplomatie.svg](wireframes/08-diplomatie.svg) |

Régénération : `python3 docs/02-ux-ui/redesign/wireframes/generate.py docs/02-ux-ui/redesign/wireframes`.
Les noms, valeurs et technologies dessinés sont des espaces réservés, jamais des données de jeu.

## 5. Dépendances de données identifiées

| Besoin UX | Disponible aujourd’hui | Proposition |
| --- | --- | --- |
| Étapes du trajet d’une mission (aperçu et mission en cours) | Non (`hops` seulement) | **UX-API-01** : `path` (liste d’identifiants de systèmes, sur les routes connues de l’Empire) dans `POST …/missions/preview` et dans `MissionView` ; aucune information nouvelle hors Knowledge propre |
| Agrégat Empire (colonies, files, flottes, recherche, alertes) | Plusieurs projections séparées | Composer côté client d’abord ; un endpoint de synthèse seulement si la charge le justifie |
| Fil d’événements unifié | Rapports dispersés | Composer côté client ; endpoint dédié à évaluer plus tard |
| Positions des flottes sur la carte | Flottes : `system` ; Galaxie : coordonnées | Jointure client par identifiant de système (même Empire, même Knowledge) |
