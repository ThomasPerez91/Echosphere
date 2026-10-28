# Progression — Echosphere

Dernière mise à jour : 2026-10-28. Cadre stable : [context.md](context.md).

## Intégré

Étape 0 : [PR #1](https://github.com/ThomasPerez91/Echosphere/pull/1) fusionnée sur master à la demande
de Thomas. develop créée au commit 1ffeab068b3cbe205acfcd59ceee65e22262c5f5 ; master réservée aux releases.

Fondation 1–2 : [PR #2](https://github.com/ThomasPerez91/Echosphere/pull/2) toujours ouverte vers develop,
CI verte sur sa tête 333533146822a88170bf5d8eefd987d318931e4c. Elle n'est pas annoncée comme intégrée.
Elle apporte configuration, SQLAlchemy/Alembic et modèles Universe/Empire/System/Planet/Colony.

## Lot courant : étape 3, temps de colonie

Branche : `work/step-3-time-engine`, créée depuis develop puis avancée sur les commits de PR #2 pour
satisfaire sa dépendance, sans fusionner cette PR. La [PR #3](https://github.com/ThomasPerez91/Echosphere/pull/3) cible develop et doit être examinée
après PR #2 ; son diff inclut cette fondation tant qu'elle n'est pas intégrée à develop.

Livré dans la branche : horloge injectable UTC, production entière avec reste exact, timeline par
colonie, trois ressources, événements datés idempotents, ordre stable, rattrapage borné et retries
persistants. Handler interne RESOURCE_RATE_CHANGE seulement. Worker du même monolithe et migration
0002. Compose ajoute un migrate one-shot et un worker sans port exposé ; aucune donnée de jeu créée.
Pas de bâtiment, recherche, flotte, combat, auth, interface jouable ou nouvelle ressource.

## Validation du lot

CI vérifiée verte sur le commit source `493311333900cc937ebd81f900c92f8e32c18543` :
[exécution 40688487764](https://github.com/ThomasPerez91/Echosphere/actions/runs/40688487764).
46 tests backend réussis, dont 25 intégrations PostgreSQL réelles ; 3 tests frontend, lint, build,
SQL/migrations et 51 documents/liens vérifiés. Le smoke Docker démarre PostgreSQL, le service migrate,
API, worker et frontend ; Alembic check/upgrade, CLI worker et panne/reprise de la DB passent.

Les scénarios temporels couvrent crash simulé avant/après commit, rollback effets/enfants,
idempotence, ordre stable, backoff/blocage, reprise explicite, rattrapage borné et concurrence des
workers sur même colonie/colonies distinctes. Les calculs purs vérifient la précision indépendante
du nombre de lectures. Pas de fault injection OS ni de benchmark de charge revendiqué.

Le checkpoint documentaire est ajouté après ce commit source testé ; consulter la CI de la tête de
PR avant fusion. PR #2 et PR #3 restent ouvertes, ni develop ni master n'ont reçu ce lot. La recette
visuelle et le test Docker Desktop/WSL2 spécifiques restent à effectuer ; aucune UI de jeu n'est ajoutée.

## Reprendre ici

1. Relire PR #3 et la CI de sa tête ; le lot source est validé et prêt à examiner.
2. Faire examiner PR #2 puis la PR temporelle vers develop, sans merge implicite sur master.
3. Étape 4 : design system responsive et navigation de base, en conservant les états réseau et clavier.
4. Étape 5 : Colony, paramètres game_data et premier service de construction après décisions Q01/Q03/Q04.
   Tout service de dépense doit rattraper sa timeline et exiger complete=True dans sa transaction.

## Décisions encore ouvertes

Q03 : coûts/taux/capacités de gameplay et entretien ; seule la représentation/arrondi est cadrée.
Q13 : interactions entre plusieurs agrégats, flottes/combat, compatibilité/archivage des événements.
Q16 : identité/session, contrôle objet et contrats HTTP avant de créer des mutations publiques.
Q02 : protection hors connexion avant combat ; Q04/Q07 : catalogue et colonisation.
Voir le [registre central](docs/05-project/open-questions.md) et [ADR 0005](docs/adr/0005-colony-time-engine.md).

## Historique

- 2026-10-28 : bootstrap fusionné, develop créée, fondation publiée dans PR #2 et CI validée.
- 2026-10-28 : étape 3 publiée dans PR #3 dépendante de PR #2 ; CI PostgreSQL/concurrence/Docker verte.
