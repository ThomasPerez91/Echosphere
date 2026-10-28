# Contribuer à Echosphere

Lire [AGENTS.md](AGENTS.md), la [vision](docs/00-product-vision.md), les
[questions ouvertes](docs/05-project/open-questions.md) et la documentation du domaine touché.
L'étape 0 ne doit pas contenir de gameplay, même pour démontrer un écran.

## Workflow

Créer une branche de travail depuis master ; changements ciblés, commits cohérents avec préfixes
`docs:`, `chore:`, `feat:`, `fix:`, `test:` ou `ci:`. Pas de secret, .env, node_modules, .venv ou dist.
Ne pas réécrire une branche partagée ni forcer un push. Ouvrir une PR vers master ; pas de merge
ou déploiement automatique par un agent.

## Modifier une règle

Distinguer validé, orientation, provisoire, question ouverte et futur. Proposer explicitement tout
changement de décision validée ; conserver sa justification. Mettre à jour le document de référence,
le registre Qxx et les documents/paramètres impactés. Ajouter une ADR si le changement est structurel.
Ne pas interpréter un mockup comme règle de gameplay et ne pas inventer une valeur manquante.
Un détail technique réversible peut être choisi avec sa justification documentée.

## Vérifier

Commandes locales dans le [README](README.md) et la [stratégie de tests](docs/04-quality/testing-strategy.md).
Avant PR : Ruff/pytest, ESLint/Vitest/build et vérification documentaire. Après modification de Docker,
exécuter le smoke Compose sur un environnement équipé. Signaler clairement ce qui n'a pas pu tourner.
Toute UI se vérifie sur desktop/mobile et au clavier. Aucune formule critique côté navigateur.

Les lockfiles sont committés. Régénérer Python avec `uv pip compile pyproject.toml -o requirements.lock`
et `uv pip compile pyproject.toml --extra dev -o requirements-dev.lock` dans backend, puis installer
et tester les nouveaux locks. Pour npm : installation ciblée, revue du package-lock et `npm ci` propre.

Une PR décrit problème et comportement final, périmètre, tests exécutés et limites connues.
La [Definition of Done](docs/04-quality/definition-of-done.md) fait foi pour la recette.
