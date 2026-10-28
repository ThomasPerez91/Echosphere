# Documentation Echosphere

L'étape 0 définit le produit et prépare un lancement local. Elle ne livre aucune boucle jouable.

## Lire dans cet ordre

1. [Vision et limites](00-product-vision.md).
2. [Modes et instances futures](01-game-design/game-modes.md), [Sessions](01-game-design/player-session.md), [boucle](01-game-design/core-loop.md) et [économie](01-game-design/resources-economy.md).
3. [Architecture](03-technical/architecture.md), [modèle conceptuel](03-technical/data-model.md), [temps](03-technical/event-engine.md).
4. [Roadmap](05-project/roadmap.md), [backlog](05-project/backlog.md) et [questions ouvertes](05-project/open-questions.md).
5. [Definition of Done](04-quality/definition-of-done.md).

Les fichiers de chaque domaine sont indexés depuis la vision, l'architecture et la roadmap.

## Statuts des décisions

| Marque | Sens | Modification |
| --- | --- | --- |
| Validé | Contrainte du projet acceptée dans le brief | Proposition explicite, docs et ADR si structurel |
| Orientation | Direction de travail actuelle | Peut évoluer avec justification et tests |
| Provisoire | Nom ou valeur de travail, aucune garantie d'équilibrage | Changement documenté |
| Question ouverte | Choix encore indéterminé, référencé par Qxx | Arbitrage enregistré avant implémentation |
| Futur | Hors étape 0, parfois hors MVP | Ne pas implémenter par anticipation |

Le brief est traduit ici sans transformer les chiffres indicatifs en règles figées. Le code actuel
est décrit dans le README et les contrats API ; les autres mécanismes métier sont **à construire**.
Une proposition technique ajoutée à la documentation n'est pas automatiquement une décision de gameplay.
