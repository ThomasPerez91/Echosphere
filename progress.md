# Progression — Echosphere

Dernière mise à jour : 2026-10-28. Cadre stable : [context.md](context.md).

## État livré sur master / base develop

- Étape 0 fusionnée : [PR #1](https://github.com/ThomasPerez91/Echosphere/pull/1).
- Commit de fusion : 1ffeab068b3cbe205acfcd59ceee65e22262c5f5.
- develop créée depuis cette fusion ; master est désormais réservée aux releases.
- CI étape 0 vérifiée verte : backend, frontend et Docker/PostgreSQL réel avec panne/reprise.

## Lot courant : fondation 1–2

Branche : `work/step-1-2-foundation`, créée depuis develop. PR : [#2](https://github.com/ThomasPerez91/Echosphere/pull/2), cible develop.
Les fonctionnalités ci-dessous restent sur cette branche jusqu'à examen/fusion de sa PR.

- Configuration centralisée validée (pydantic-settings), secrets masqués et délais bornés.
- Fabrique FastAPI ; modules API/core/persistence ; pool SQLAlchemy et transactions explicites.
- Modèles Universe, Empire, StellarSystem, Planet, Colony ; UUID et timestamps UTC.
- FK composites : pas de planète/colonie liée à un autre univers ; occupation courante unique.
- Alembic 0001, migration explicite, réversible seulement sur base jetable pour les tests.
- CI sur develop/master et branches work ; tests PostgreSQL dédiés et migration dans l'image Docker.
- Règles Git actualisées, context.md et progress.md inclus dans le check documentaire.

Ce lot ne livre ni écran de jeu ni endpoint de création de partie : aucune authentification n'est
encore décidée. La fondation prépare les services suivants sans exposer de mutations non protégées.

## Vérification et clôture du lot

Commandes locales : Ruff backend/scripts, pytest, génération SQL offline Alembic, check docs,
ESLint/Vitest/build frontend. Les tests DB sont ignorés localement sans PostgreSQL ; la CI exécute
les douze tests d'intégration sur une base *_test et le smoke Docker réel.
Résultats locaux vérifiés : 8 tests unitaires backend, 3 tests frontend, Ruff/ESLint/build,
SQL offline et 50 documents/liens. Premier passage CI : frontend et Compose/migrations réussis ;
un test PostgreSQL attendait la mauvaise classe d'erreur pour une chaîne trop longue. Correction :
distinguer le CHECK d'un contrôleur inconnu et le rejet de longueur. La CI est relancée sur ce correctif.
Le résultat final de la CI doit être consulté sur la PR du lot ; ne pas considérer une étape intégrée
à develop simplement parce que les fichiers sont présents dans cette branche de travail.
La recette visuelle et le test spécifique Docker Desktop/WSL2 restent à effectuer par l'utilisateur.

## Reprendre ici

1. Vérifier la PR work/step-1-2-foundation → develop et sa CI ; corriger tout échec avant fusion.
2. Une fois le lot intégré à develop, préparer l'étape 3 (temps), sur une nouvelle branche depuis develop.
3. Cadrer Q03 : précision/arrondis, stock et taux ; Q13 : ordre simultané, locks et reprise.
4. Implémenter horloge injectable, calcul différé et événements persistants, avec tests de crash,
   rejeu et concurrence ; aucun cron/timer mémoire comme autorité et aucune simulation par seconde.

## Questions qui restent ouvertes

Q16 : mode d'identité/session, erreurs de commandes et idempotence ; blocage de toute mutation HTTP.
Q04 : catalogue et capacités exactes (aucun défaut 12 ni maximum 18 imposé par ce schéma).
Q07 : coûts, concurrence métier, abandon et historique de colonisation.
Q02 : protections hors connexion avant combat. Toutes les autres Q restent dans le registre central.

## Historique bref

- 2026-10-28 : étape 0 publiée et vérifiée, puis fusionnée sur instruction ; develop créée.
- 2026-10-28 : lot 1–2 préparé sur sa branche, suivi et conventions de reprise ajoutés.
