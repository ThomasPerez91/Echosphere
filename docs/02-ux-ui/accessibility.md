# Accessibilité

**Statut : responsive validé ; détails UI orientatifs.**


Objectif de conception : WCAG 2.2 AA, à vérifier progressivement, sans revendiquer de certification.
Structure HTML sémantique, titres ordonnés, contrôles natifs et noms accessibles. Contraste visé :
4,5:1 pour le texte courant, 3:1 pour les gros textes et éléments graphiques essentiels.

## Interactions

Tout le parcours quotidien est utilisable au clavier. Focus visible, aucun piège, retour du focus
après dialogue. Les changements asynchrones importants sont annoncés sans lire un compteur chaque
seconde. Les erreurs sont liées au champ concerné et ne reposent pas uniquement sur une couleur.
Animations non essentielles réduites selon les préférences utilisateur lorsqu'elles seront ajoutées.

La carte est un risque spécifique : prévoir navigation structurée/listes et résumé textuel d'un
système au lieu de rendre le canvas indispensable. Zoom 200 %, mise en page étroite, lecteur d'écran
et contrôle tactile complètent les outils automatiques.

Au bootstrap : langue française, viewport, heading, bouton natif, statut live et focus CSS.
Une vérification automatisée seule ne vaut pas recette d'accessibilité complète.


## Références

- [Index](../README.md) · [Questions ouvertes](../05-project/open-questions.md)
