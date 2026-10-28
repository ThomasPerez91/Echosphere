# Design system

**Statut : première version implémentée à l’étape 4 ; choix visuels ajustables (Q15).**

Dark sci-fi sobre, panneaux bleu nuit, cyan pour sélection et action primaire, or pour avertissement
et focus. Typographie système locale, sans chargement externe. Illustration orbitale purement
CSS et décorative, masquée aux technologies d’assistance. Pas d’asset ou valeur de jeu simulée.

## Tokens et composants utilisés

| Token CSS | Valeur | Usage |
| --- | --- | --- |
| fond global | #080e19 | Application |
| --surface | #101a2a | Panneaux/cartes |
| --border | #2c3c51 | Séparateurs décoratifs |
| texte principal | #e2eaf4 | Contenu |
| --muted | #a8b8ce | Texte secondaire |
| --accent | #83e3e8 | Liens/sélection |
| --gold | #f1d18f | Focus/avertissement |
| --radius | 12px | Panneaux |
| --space | 24px | Espacement principal |

Button : natif, hauteur minimum 44 px, état désactivé et chargement. Badge : texte et ton sémantique,
jamais couleur seule. Panel : section avec titre h2. EmptyState : explication sans commande inactive
factice. Resource cards : noms des trois ressources et stocks non disponibles, sans chiffres.
Ne pas créer de champ/dialogue/table générique avant une utilisation réelle.

États réseau : vérification, disponible, indisponible, retry explicite. Un état « disponible » ne
signifie pas qu’une partie existe. Vues de domaine : « À venir » et explication du périmètre.
Un seul statut live global évite les annonces dupliquées ; badges secondaires sans aria-live.

## Responsive et accessibilité

Sidebar au-delà de 800 px ; barre basse avec quatre destinations et Plus sur mobile/tablette.
Panneaux empilés, ressources en liste sous 520 px. Safe area basse réservée, pas de hover obligatoire.
Focus or visible, lien d’évitement, titres structurés, commandes natives ; pas d’animation essentielle.
Aucun objectif de certification d’accessibilité atteint sur la seule base des tests automatisés.

## Références

- [Navigation](information-architecture.md) · [Accessibilité](accessibility.md)
- [Frontend](../03-technical/frontend.md) · [Questions ouvertes](../05-project/open-questions.md)
