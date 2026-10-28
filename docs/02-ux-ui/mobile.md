# Présentation mobile

**Statut : responsive validé ; détails UI orientatifs.**


Mobile obligatoire dès le départ. Navigation basse implémentée à l’étape 4 (quatre sections et bouton Plus) ; priorités du jour dans le premier
écran, détails dans des drawers/modals accessibles. Ne pas compresser le dashboard desktop.
Aucune action importante disponible uniquement au hover.

## Parcours cible

Lire les alertes, consulter les ressources, remplir une petite file, programmer une recherche et
lancer une mission. La carte devra permettre sélection tactile, zoom et une alternative en liste
pour les informations essentielles. Les tableaux doivent devenir des vues adaptées à la décision.

## Critères de recette

À 320 et 390 pixels de large : pas de débordement horizontal du contenu principal ; boutons tactiles
visant 44 pixels ; actions accessibles au clavier et au lecteur d'écran ; statut réseau explicite.
Un drawer restaure le focus à sa fermeture et ne masque pas la confirmation d'action. Les détails de
navigation restent Q15. L’étape 4 vérifie le shell aux tailles 320/390/768/1440. Plus révèle les destinations secondaires
sans dialogue ; Échap referme et rend le focus au bouton. Le contenu conserve l’espace de la barre
basse et de la safe area. Les drawers de gameplay restent futurs.


## Références

- [Index](../README.md) · [Questions ouvertes](../05-project/open-questions.md)
