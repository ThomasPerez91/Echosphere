# Données de jeu versionnées

Étape 5A : `rulesets/v0.1/resources.json`, `colony.json`, `infrastructures.json`.
Les tests chargent ces fichiers réels. Format JSON/Pydantic strict, sans dépendance supplémentaire.
Fichier absent/invalide, extra, clé dupliquée, version incohérente, ressources manquantes, booléen à
la place d’un entier ou vitesse invalide : erreur explicite ; pas de fallback de gameplay.

`app.colony.rules.load_ruleset` charge les fichiers depuis ce répertoire en développement.
`ECHOSPHERE_GAME_DATA` change seulement l’emplacement des fichiers (image : /app/game_data), jamais
la vitesse globale. Le contexte Docker backend est désormais la racine du dépôt pour inclure les
données. L’image garde le même monolithe API/worker et ne télécharge pas de ruleset au démarrage.

Chaque univers reçoit une copie validée de règles et vitesses ; aucune modification d’un fichier
ne change une instance existante. Un ordre snapshotte ses valeurs. Évolution des rulesets actifs,
outil d’édition et migration des anciennes timelines hors lot (Q12/Q13/Q26).

Niveaux explicites 1–5 puis scaling configurable par infrastructure. Arrondis micro-unités et
durées exactes, multiplicateurs rationnels ; valeurs v0.1 provisoires à rééquilibrer par simulation.
Aucune limite de niveau 5. En v0.1, research/fleet speeds restent réservées.

- [Référence v0.1](../docs/01-game-design/colony-economy-v0.1.md)
- [ADR 0007](../docs/adr/0007-colony-economy.md)

Étape 6 : `rulesets/v0.2` complète avec `research.json`, huit technologies I/II, prérequis,
coûts/durées/effets et annulation. Research utilise la vitesse dédiée ; fleet demeure réservée.
Aucun fichier v0.1 ni Universe épinglé n’est réécrit. Arrondis/plafonds et snapshots documentés dans
[Research technique](../docs/03-technical/research-api-ui.md). Le loader par défaut reste v0.1 :
choisir explicitement v0.2 pour une nouvelle instance compatible, jamais à la lecture d’une ancienne.
