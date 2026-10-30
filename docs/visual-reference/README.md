# Références visuelles — Echosphere

**Statut : direction visuelle cible validée par l’utilisateur le 2026-10-30.** Ces images guident
l’apparence de l’interface ; elles ne sont pas des spécifications fonctionnelles. Elles ne déclarent
aucun écran ou composant déjà implémenté. Le [design system actuel](../02-ux-ui/design-system.md)
décrit les tokens et composants réellement présents ; leur évolution vers cette cible demande un
travail UI autorisé et vérifié, sans remplacement automatique du shell.

## Rôle et correspondance

[design-system.png](design-system.png) est l’ancre générale pour les composants, couleurs,
typographie et patterns. Les autres images donnent des références d’écran et de composition.

| Fichier | Référence de composition |
| --- | --- |
| [empire-dashboard.png](empire-dashboard.png) | Dashboard Empire / vue synthétique |
| [colony-infrastructure.png](colony-infrastructure.png) | Colony / navigation interne / infrastructures |
| [galaxy-map.png](galaxy-map.png) | Carte Galaxie |
| [system-view.png](system-view.png) | Vue détaillée d’un système |
| [research-view.png](research-view.png) | Recherche |
| [design-system.png](design-system.png) | Composants, couleurs, typographie et patterns généraux |

Ces références couvrent palette, densité d’information, hiérarchie visuelle, navigation desktop/mobile,
top bar, sidebar, cartes et panneaux, onglets, alertes, tableaux et listes, boutons, iconographie,
espacements, ambiance science-fiction et comportement responsive attendu.

## Principes à préserver

- Fond bleu nuit / navy très sombre, surfaces légèrement plus claires et bordures discrètes.
- Cyan/bleu pour les interactions primaires ; vert pour le succès et la production positive ;
  ambre/or pour avertissements et accents stratégiques ; rouge pour le danger ; violet réservé
  à certains domaines secondaires. Les états restent compréhensibles sans la seule couleur.
- Typographie claire, moderne et lisible ; glow subtil, jamais excessif.
- Interface dense mais structurée, privilégiant la lisibilité et l’utilité.
- Rendu réaliste et implémentable en React/CSS ; les illustrations ne justifient pas une interface
  cinématique qui gênerait les actions ou la lecture.

Les couleurs et mesures dessinées dans l’image sont une cible visuelle, pas une obligation de
remplacer immédiatement chaque token existant. Réutiliser et faire évoluer les composants en
cohérence avec le shell ; ne pas dériver vers un autre langage graphique sans décision explicite.

## Autorité et contenu illustratif

L’ordre d’autorité est :

1. Décisions produit validées et ADR, dans leur portée et leur statut.
2. Documentation canonique.
3. Code et `game_data`, selon leur statut implémenté ou provisoire.
4. Références visuelles.
5. Contenu décoratif ou illustratif des mockups.

Une contradiction entre les trois premières sources doit être signalée ; une image ne la tranche
jamais. Textes, chiffres, fonctionnalités, bâtiments, technologies, flottes, défenses, populations,
noms et mécaniques dessinés ne deviennent pas des décisions validées.

Exemples concrets visibles dans ces images :

- La population et la stabilité affichées ne créent pas de système de population/stabilité.
- Un bâtiment, une technologie ou une défense absents du catalogue validé ne doivent pas être
  implémentés depuis le dessin. Les piles de canons/missiles illustrées ne remplacent pas la
  [défense future par réseau limité de modules persistants](../01-game-design/planetary-defense.md).
- Stocks, coûts, productions, durées, niveaux et capacités sont illustratifs. `game_data` fait foi
  pour les valeurs implémentées, avec leur statut de balance provisoire. Les capacités 16/6 dessinées
  ne remplacent pas le départ de référence 12 secteurs/2 orbitaux et ne fixent aucune capacité future.
- Les boutons « Accélérer », niveaux de profil, noms d’Empire et recherches représentées n’autorisent
  ni accélération payante, ni progression ou catalogue supplémentaires.
- Un écran futur guide uniquement la composition ; il n’autorise pas son développement ni des
  données fictives dans l’application. Les onglets illustratifs ne remplacent pas la navigation
  canonique Colony Vue d’ensemble / Infrastructures / Orbite / Défense.

Voir [vision](../00-product-vision.md), [économie](../01-game-design/colony-economy-v0.1.md),
[questions ouvertes](../05-project/open-questions.md) et [ADR](../adr/README.md).

## Utilisation par les agents

Avant de créer ou modifier substantiellement une UI :

1. Lire ce README.
2. Consulter `design-system.png`.
3. Consulter l’écran de référence du domaine concerné, lorsqu’il existe.
4. Lire les documents produit/UX et ADR associés.
5. Préserver le shell visuel existant et réutiliser les composants/tokens présents.
6. Ne coder aucune mécanique sur la seule foi d’une image.
7. Signaler toute contradiction image/documentation avant de modifier le comportement produit ;
   conserver l’autorité canonique en attendant un arbitrage nécessaire.

Une nouvelle UI doit rester reconnaissable comme faisant partie d’Echosphere. Aucune de ces
références n’autorise à élargir le lot en cours.

## Responsive et accessibilité

Les mockups desktop définissent surtout une hiérarchie et une direction. Le responsive respecte
les contraintes [mobile](../02-ux-ui/mobile.md) et [accessibilité](../02-ux-ui/accessibility.md)
validées : ne jamais réduire le mobile à un desktop compressé. Adapter, réordonner ou condenser
le contenu, maintenir les commandes tactiles et clavier, les états et le focus. Les comportements
réels et les contraintes UX priment sur les approximations graphiques des images, notamment la
navigation mobile dessinée. Aucun fonctionnement uniquement au hover.
