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
satisfaire sa dépendance, sans fusionner cette PR. La nouvelle PR cible develop et doit être examinée
après PR #2 ; son diff inclut cette fondation tant qu'elle n'est pas intégrée à develop.

Livré dans la branche : horloge injectable UTC, production entière avec reste exact, timeline par
colonie, trois ressources, événements datés idempotents, ordre stable, rattrapage borné et retries
persistants. Handler interne RESOURCE_RATE_CHANGE seulement. Worker du même monolithe et migration
0002. Compose ajoute un migrate one-shot et un worker sans port exposé ; aucune donnée de jeu créée.
Pas de bâtiment, recherche, flotte, combat, auth, interface jouable ou nouvelle ressource.

## Validation du lot

21 tests unitaires locaux réussis ; les intégrations PostgreSQL sont ignorées localement faute de
serveur et doivent passer dans la CI. Les nouveaux scénarios couvrent crash avant/après commit,
rollback des effets/enfants, idempotence, ordre identique, backoff/blocage, reprise explicite,
rattrapage borné et deux workers (même colonie et colonies distinctes).
Lint, SQL offline Alembic, check documentaire, build et tests frontend font partie de la recette.
Vérifier le résultat réel de la CI sur la nouvelle PR avant toute intégration ; ne pas confondre
les résultats verts de PR #2 avec ceux du nouveau moteur.

## Reprendre ici

1. Vérifier la nouvelle PR temporelle et sa CI ; corriger tout échec avant de déclarer le lot prêt.
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
- 2026-10-28 : étape 3 implémentée sur branche dépendante de PR #2 ; validation de la nouvelle CI en cours.
