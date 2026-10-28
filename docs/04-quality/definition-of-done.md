# Definition of Done

**Statut : règle de travail.**

## Chaque changement

- Périmètre explicite, pas de feature non documentée ; hypothèses et arbitrages identifiés.
- Règles critiques côté serveur, UTC et PostgreSQL source de vérité.
- Tests pertinents ajoutés/actualisés ; lint, tests et build passent.
- Cas d'échec, reprise et concurrence couverts selon le risque.
- Responsive mobile et desktop, clavier, chargement/erreur vérifiés pour un changement UI.
- Documentation et ADR actualisés si le comportement ou une décision structurelle change.
- Aucun secret, logs sensibles, code généré inutile ou dépendance non justifiée.
- PR compréhensible : comportement final, validation réelle et limites ; pas de merge automatique.

## Étape 4

Shell aux largeurs 320/390/768/1440, navigation clavier, focus, historique et liens directs vérifiés.
Readiness : chargement, échec, timeout, réponse invalide/tardive, démontage et reprise. Aucun stock
fictif ou ordre de jeu. Lint/tests/build/docs et tests navigateur en CI ; recette visuelle des captures.
Limites tactiles, lecteur d’écran réel et WSL2 signalées. Q15 reste ouverte pour validation produit.

## Étapes 1–2

Configuration validée, sondes compatibles, sessions et transactions explicites. Modèles/migration
cohérents, contraintes cross-universe et unicité vérifiées sur PostgreSQL réel, migration réversible
sur base jetable et absence de dérive ORM. Aucun endpoint métier non autorisé. context.md/progress.md
à jour ; branches de travail depuis master, PR/CI vers master ; tags/releases identifiées plus tard.

## Étape 3

Horloge injectable, calcul exact stable à la fréquence de lecture, production segmentée aux dates
logiques. Ordre/verrou par colonie, reprises avant/après commit et isolation des workers vérifiés sur
PostgreSQL. Pas d'avancement au-delà d'une échéance bloquée ou du budget de rattrapage. Retry borné,
diagnostic sans payload sensible et relance explicite. Migrations et runtime Compose vérifiés.
Décisions Q03/Q13 cadrées sans fermer les paramètres métier ou le multi-agrégat. Aucun nouvel endpoint
public non protégé. PR #2 fusionnée sur master avant la correction de PR #3.

## Étape 0 (historique)

Tous les fichiers demandés existent, liens valides et questions ouvertes centralisées.
README et AGENTS suffisent à reprendre le projet. Frontend placeholder responsive, backend minimal,
.env.example, Dockerfiles, Compose PostgreSQL persistant sans port DB publié et probes présentes.
Qualité backend/frontend et CI disponibles ; commandes WSL2 et URLs documentées.
Les services doivent être vérifiés selon les moyens disponibles et toute absence de test Docker
réel est signalée. Aucun gameplay, auth, Redis, WebSocket ni moteur temporel implémenté.

La livraison distante n'est terminée qu'après publication de la branche et ouverture d'une PR
vers master laissée non fusionnée. Un refus d'accès GitHub doit être rapporté comme blocage ; un
bundle local ne vaut ni push ni PR. La CI configurée n'est pas une CI passée tant qu'elle n'a pas tourné.

Voir [stratégie de tests](testing-strategy.md) et [contribution](../../CONTRIBUTING.md).
