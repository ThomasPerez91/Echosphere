# Philosophie d’équilibrage

**Statut : principes validés ; ratio orientatif.**


La spécialisation change la manière de jouer sans produire des multiplicateurs absurdes.
Orientation : environ 80 % de la puissance vient du socle commun, au plus environ 20 % des
spécialisations. Ce n'est ni une statistique mesurée ni une formule de dégâts validée.
Des avantages early/mid/late sont possibles, pas de branche dix fois plus forte ou faible.

## Méthode future

Séparer règles et paramètres versionnés dans `game_data/`. Exécuter des simulations headless
avec seeds, version du moteur et version des données enregistrées. Comparer croissance économique,
accès à la colonisation, temps de recherche, résultats militaires et trajectoires des profils IA.
Définir les métriques de puissance et seuils de tolérance en Q12 avant de conclure à l'équilibre.

## Scénarios de contrôle

Départ comparable et traits différents ; empires proches et éloignés ; agressif contre prudent ;
stratégie spécialisée contre socle diversifié ; absence prolongée. Surveiller les boucles de
snowball, les stratégies dominantes et la possibilité de rattrapage. Aucune balance jouable ne
peut être revendiquée avec le bootstrap actuel.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)
