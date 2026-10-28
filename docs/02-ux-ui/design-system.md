# Direction du design system

**Statut : responsive validé ; détails UI orientatifs.**


Direction artistique : dark sci-fi, bleu/cyan, accents or ponctuels, cartes et panneaux lisibles.
Éviter les fonds complexes qui nuisent au contraste et les effets coûteux. Typographie système pour
le bootstrap ; les familles finales restent à choisir à l'étape 4.

## Fondation envisagée

Tokens sémantiques pour fond, surface, texte, bordure, focus, alerte et accent ; échelle d'espacement
et de tailles ; composants bouton, carte, statut, champ, tableau, dialogue et file. La première étape
ne crée pas une bibliothèque de composants abstraite avant d'avoir plusieurs usages réels.

Les états chargement, vide, erreur, désactivé et succès font partie du composant. Associer icône
éventuelle et texte au statut plutôt que la couleur seule. Prévoir les libellés longs et les grands
nombres sans fixer à l'avance des valeurs de gameplay.

Le CSS actuel pose des couleurs lisibles, une largeur fluide et un focus visible ; il n'est pas le
design system final. Les mockups donnent le ton mais ne définissent ni ressources ni règles métier.


## Références

- [Index](../README.md) · [Questions ouvertes](../05-project/open-questions.md)
