# Contribuer à Echosphere

Lire [AGENTS.md](AGENTS.md), la [vision](docs/00-product-vision.md), les
[questions ouvertes](docs/05-project/open-questions.md) et la documentation du domaine touché.
Lire aussi [context.md](context.md) et [progress.md](progress.md), qui indiquent le lot courant et le point de reprise.

## Workflow

Synchroniser master, créer une branche courte work/..., développer, vérifier la CI puis ouvrir une
PR vers master. Revue et merge uniquement sur autorisation. master est l'intégration stable ; aucun
passage obligatoire par develop. Tags/releases identifiées seront ajoutés plus tard sur instruction.
Ne pas empiler une branche pour contourner une dépendance ouverte ; faire intégrer la fondation
ou signaler le blocage. Un nouveau lot repart de master ; une continuation explicitement autorisée
reste sur la branche/PR existante (passation actuelle : #5, sans nouvelle branche/PR).

Commits cohérents avec préfixes docs/chore/feat/fix/test/ci. Aucun secret, .env, node_modules,
.venv ou dist ; pas de force push ni réécriture partagée. Ne supprimer une branche que sur instruction
et après vérification de ses écarts. Les règles produit et les questions ouvertes ne se ferment pas
implicitement parce qu'un schéma ou un test les rend possibles.

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

## Travail entre environnements

Suivre [AGENTS](AGENTS.md) et [Work ↔ Codex](docs/06-handoff/work-codex-handoff.md) : état distant
avant action, lecture du checkpoint, synchronisation ff-only sans perte, mêmes vérifications, commit/
push puis SHA/CI relus. Une décision est synthétisée avec statut/provenance dans sa référence canonique,
pas exportée comme conversation privée. Les [limites des sources](docs/06-handoff/source-map.md)
et questions non résolues restent visibles. La cible Portal/Game n’est pas une implémentation.
