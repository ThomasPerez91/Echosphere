# Contexte de reprise — Echosphere

Dernière mise à jour : 2026-10-28. Ce fichier décrit le cadre stable ; [progress.md](progress.md)
décrit le lot courant, les validations et les prochaines actions. Lire aussi [AGENTS.md](AGENTS.md).

## Produit

Stratégie spatiale persistante dans le navigateur. Une préparation quotidienne d'environ dix minutes ;
une session longue améliore les décisions, pas le rendement par clic. Civilisations IA autonomes,
sans LLM au départ, mêmes services/règles et connaissance limitée que les humains.
Trois ressources principales : Alliages, Flux, Données. Planètes à secteurs, pas de grille ; galaxie
future en graphe 2D seedé ; backend autoritaire. Aucun pay-to-win.

## Dépôt et branches

Dépôt : https://github.com/ThomasPerez91/Echosphere.
Le 28 octobre, Thomas a demandé de fusionner PR #1 sur master puis de créer develop comme référence.
Cette fusion est réalisée au commit 1ffeab068b3cbe205acfcd59ceee65e22262c5f5.
Toutes les nouvelles branches de travail partent de develop et les PR de développement le ciblent.
master reçoit les releases sur instruction. Ne pas confondre branche de référence du workflow et
réglage de branche par défaut dans l'interface GitHub ; ce dernier n'a pas été modifié ici.
Aucune autorisation générale de fusion/tag/déploiement ne découle de la fusion ponctuelle de PR #1.

## Architecture

Monolithe modulaire : React/TypeScript/Vite ; Python/FastAPI ; PostgreSQL 17 ; SQLAlchemy 2/Alembic.
UTC partout en calcul/stockage. API dans backend/app/api, config dans core, DB/sessions/modèles dans
persistence, migrations versionnées dans backend/migrations. Aucun calcul critique dans le navigateur.
Le socle temporel de colonie est persistant et transactionnel, sans tick global par seconde.
Micro-unités entières, reste exact, ordre due_at/séquence et verrou de timeline commun aux services.
Le frontend est encore un placeholder responsive ; les modèles ne constituent pas un jeu jouable.

## Ordre de travail et décisions

Roadmap 0–17 : [roadmap](docs/05-project/roadmap.md). Le lot courant 3 livre le socle temporel. PR #2 reste une dépendance en revue tant qu’elle n’est pas fusionnée.
Ne pas coder tout le MVP en interprétant une simple demande de poursuite comme validation de tous
les choix ouverts. Distinguer validé, orientation, provisoire, question ouverte et futur.
Registre Q01–Q18 : [questions ouvertes](docs/05-project/open-questions.md).
Q03/Q13 sont partiellement cadrées par ADR 0005 ; économie et interactions multi-agrégats restent ouvertes.
Q02 précède le combat ; Q16 toute mutation HTTP. Aucun endpoint métier non protégé n’est ajouté.
Aucune authentification complète, commande de jeu, IA ou génération de galaxie n'existe encore.

## Protocole de reprise

1. Lire progress.md et les consignes AGENTS, puis vérifier branches, PR et CI distantes.
2. Partir du dernier develop pour un nouveau lot ; continuer la branche courante si la PR attend une correction.
3. Lire les docs du domaine, cadrer les questions nécessaires et implémenter le plus petit lot complet.
4. Vérifier lint/tests/build, migrations PostgreSQL et smoke Docker selon les changements.
5. Mettre à jour progress.md avec résultats réels, limites et prochaine action, puis ouvrir une PR vers develop.

Ne stocker aucun secret ou token dans ces fichiers. Un résultat CI annoncé doit être vérifié sur GitHub.
