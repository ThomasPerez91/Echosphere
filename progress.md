# Progression — Echosphere

Mise à jour : 2026-10-28. Cadre : [context.md](context.md).

## État initial vérifié et intégration de la fondation

Au début de cette mission : PR #2 et PR #3 ouvertes vers master, aucune fusion ; develop/master
étaient encore les branches historiques. PR #2 tête 333533146822a88170bf5d8eefd987d318931e4c ;
PR #3 tête 348c2e5e5276ddf71d850ec1b9c0017154f7e10f, ancienne file attachée aux colonies.

PR #2 fusionnée sur master sur instruction explicite, après CI verte :
a065ad80eeb6db73438e61b1d6cde8bc3293e06d. Fondation validée : SQLAlchemy/Alembic et les cinq modèles,
contraintes inter-univers, aucun user_id lié à Empire. PR #1/étape 0 était déjà intégrée.

## Correction actuelle — PR #3

Branche existante work/step-3-time-engine, PR vers master ; aucune nouvelle branche ni Étape 4.
Scheduler générique EventStream par univers, événements attachés au stream, adaptateur économique
ColonyTimeline distinct. FK composites pour rattachement colonie/stream/univers et événement/stream.
Cursor logique du stream séparé de settled_at économique ; handlers de taux et calcul exact conservés.
Aucun domaine Research/Fleet/AI/Combat anticipé. Les tests existants restent présents et adaptés.

Migration ajoutée 0003_generic_event_streams ; 0001/0002 inchangées. Backfill des données 0002,
préservation de l'historique et roundtrip peuplé. Refus du downgrade avant DDL pour streams non
représentables ou curseurs non alignés, sans suppression d'événement pour contourner le refus.

Modes de jeu et ADR 0006 ajoutés, Universe=frontière d'instance. Q19–Q29 ouvertes pour multijoueur,
aucune règle décidée ni feature créée. Workflow corrigé partout : master stable, work/... → PR master,
CI/revue et autorisation. develop n'est plus nécessaire ; suppression seulement après contrôle d'écarts.

## Validation et autorisation de clôture

Les tests locaux sans PostgreSQL couvrent toujours calcul exact, UTC et sondes ; les intégrations
sont explicitement ignorées localement. La CI doit vérifier tous les anciens scénarios plus streams
sans colonie, traitement multi-univers, scope incorrect, FK cross-universe et migrations peuplées.
Vérifier la tête finale et ses jobs backend/frontend/Compose avant la fusion de PR #3 autorisée par
Thomas. Les résultats finaux/URL seront consignés dans le checkpoint de ce lot et le rapport final.

## Reprendre après ce lot

1. Vérifier l'état GitHub de PR #3, sa tête, sa CI et son éventuelle fusion, sans déduire un état de ce texte seul.
2. Après correction/revue/fusion, prochaine étape autorisée : Étape 4, design system responsive/shell.
3. Recette UI cible : 320/390/768/1440 px, mobile prioritaire, contrôles tactiles ~44 px, aucun hover obligatoire.
4. Pas de nouvelle branche Étape 4 dans la présente mission ; ne pas démarrer Colony/Research/Fleet/AI/Combat.

[PR #2](https://github.com/ThomasPerez91/Echosphere/pull/2) · [PR #3](https://github.com/ThomasPerez91/Echosphere/pull/3)
