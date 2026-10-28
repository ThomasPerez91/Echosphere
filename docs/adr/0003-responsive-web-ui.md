# 0003 — Deux présentations responsive du même produit

- Statut : acceptée (brief projet).
- Date de transcription : 2026-10-28.

## Contexte

La préparation quotidienne doit être possible sur téléphone comme desktop. Les mockups spatiaux
cinématiques ne définissent ni l'ergonomie mobile ni les règles du jeu.

## Décision

Application web React responsive. Desktop avec navigation latérale envisagée, mobile avec navigation
basse et panneaux contextuels adaptés. Aucune action importante réservée au hover. Backend autoritaire.

## Conséquences et alternatives

Composants sémantiques, états réseau et vérification tactile/clavier dès les premiers écrans.
Effort de conception spécifique au mobile ; pas de simple réduction du dashboard desktop, ni deux
produits métier divergents. Le bootstrap livre un panneau fluide, pas la navigation complète.

[Architecture](../03-technical/architecture.md) · [Index ADR](README.md)

## Portée et évolution documentaire

Note d’évolution : le panneau décrit est historique étape 0 ; shell responsive livré depuis
PR #4, sous-navigation Colony depuis #5. Le parcours compte/Portal reste futur dans [ADR 0008](0008-control-plane-game-data-plane.md).
