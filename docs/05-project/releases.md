# Versions et releases

**Statut : convention technique proposée pour démarrer.**

Le code du bootstrap porte `0.0.1` à titre de version de développement. Aucun tag ni release publique
n'est créé par l'étape 0. Le premier MVP jouable pourra être désigné `v0.1.0` après stabilisation ;
ce nom est une proposition, pas un engagement de date. Le séquencement v0.2 à v1.0 est dans la roadmap.

## Préparer une release

Identifier commit, versions frontend/backend, migrations et version des données. Documenter ajouts,
changements incompatibles, bugs corrigés et limites connues. Exécuter les checks et un démarrage
neuf ; tester la restauration avant toute migration de données persistantes importante.

Une modification d'équilibrage peut changer une simulation sans changer les API : conserver la
version des game_data et les hypothèses dans les rapports. La compatibilité des univers déjà créés
avec de nouvelles règles reste Q13/Q14.

## Branches (décision utilisateur du 28 octobre 2026)

`develop` est la référence de développement : branches de travail depuis develop et PR vers develop.
`master` est réservé aux releases. La PR #1 a été fusionnée sur master à la demande de Thomas,
puis develop a été créée depuis ce même commit. Cette initialisation n'est pas un schéma à répéter.

Pour une release : vérifier la CI de develop, préparer notes et versions/migrations, ouvrir une PR
develop → master et fusionner uniquement sur instruction. Tag et publication ne sont pas automatiques.
Après un éventuel correctif de release, réintégrer le changement dans develop par une PR.

Les PR sont examinées avant merge. Aucun déploiement public ou merge automatique sans instruction.
Une CI écrite mais jamais exécutée ne doit pas être présentée comme verte.

Voir [roadmap](roadmap.md) et [Definition of Done](../04-quality/definition-of-done.md).
