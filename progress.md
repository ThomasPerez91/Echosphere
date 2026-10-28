# Progression — Echosphere

Mise à jour : 2026-10-28. Cadre : [context.md](context.md).

## État vérifié à la reprise

PR #2 et PR #3 corrigée sont fusionnées sur master. Fusion #3 :
`4ee81dd447726b5d72eaf1d26626215d14d1c931`, tête source
`4f29a81e57d39c1df6ba041bcc9c4e5b0ee0f6b1`.
Thomas a supprimé develop ; absence confirmée via la liste des branches GitHub.
Instruction « reprend » : poursuite du prochain lot, Étape 4, après satisfaction du prérequis #3.
Branche `work/step-4-responsive-shell` créée depuis ce master. PR vers master sans fusion.

## Lot actuel — Étape 4

- Shell responsive : sidebar desktop, barre basse mobile/tablette jusqu’à 800 px ; Plus donne accès
  à Flottes/Rapports/Relations. Fermeture par Échap avec retour du focus ; pas de modal.
- Sept destinations par fragments URL, liens directs, historique natif, destination inconnue avec
  retour Empire. Focus sur h1 au changement de section, lien d’évitement, sélection aria-current.
- Composants Button/Badge/Panel/EmptyState réellement utilisés, tokens CSS et illustration orbitale
  décorative CSS. Pas d’images externes ni de nouvelle dépendance runtime.
- Empire : stocks explicitement indisponibles, aucune partie active, vérification réseau manuelle.
  Autres sections : espace en préparation. Aucun stock, mission, ordre ou progrès fictif.
- Hook readiness séparé : contrat existant /api/ready, timeout 5 secondes, annulation au démontage,
  réponse tardive ignorée, retry. API/PostgreSQL vérifiés au dernier contrôle, pas le worker.
- Playwright ajouté en dev uniquement ; scénarios Chromium et installation dans la CI frontend.
  Vitest et Playwright ont des répertoires de collecte distincts. Pas de changement backend/BDD/Compose.
- Documents UX/techniques, AGENTS, context et roadmap actualisés. Q15 reste ouverte pour validation
  des choix proposés et future carte tactile. Aucune question d’équilibrage fermée implicitement.

## Vérifications du lot

Local : ESLint, 10 tests Vitest, build TypeScript/Vite et 5 scénarios Chromium réussis.
Chromium : 320/390/768/1440 px, pas de débordement, liens principaux de 44 px minimum,
lien d’évitement, clavier, h1 focus, Plus/Échap, liens directs/rechargement, précédent et retry.
Captures Empire/Colonie inspectées, desktop et mobile ; aucune valeur métier présentée comme réelle.
Ruff et 21 tests backend unitaires passent ; 31 intégrations PostgreSQL ignorées localement faute
de base de test activée. 53 documents/liens vérifiés. Docker non exécuté localement.

CI distante du lot : à vérifier après publication ; aucun résultat de la précédente étape n’est
présenté comme validation de cette tête. Le job backend exécutera les 52 tests avec PostgreSQL et
Compose vérifiera migration/worker/proxy avec panne/reprise de la base.

Limites : Chromium desktop émulant les dimensions, pas de recette tactile/lecteur d’écran réel,
Safari/Firefox, ni Docker Desktop/WSL2. Les sondes interceptées du navigateur ne remplacent pas
la CI Compose. Pas de certification d’accessibilité revendiquée ni de partie jouable.

## Point de reprise

1. Consulter la PR de cette branche, sa tête et sa CI ; corriger tout échec avant livraison.
2. La laisser non fusionnée : les autorisations de merge #2/#3 ne couvrent pas ce lot.
3. Après revue/intégration de ce shell, cadrer l’étape 5 (boucle Colony) : coûts/rendements/version
   des règles, stocks initiaux, secteurs et taille des files encore ouverts. Ne pas déduire ces
   valeurs de la présente interface. Continuer sur une nouvelle branche depuis master intégrée.
4. Ne pas anticiper Research/Fleets/AI/Combat ou les modes/participations multijoueurs.

## Historique des fondations

PR #1 : bootstrap. PR #2 : SQLAlchemy/Alembic et cinq modèles Universe/Empire/System/Planet/Colony,
contraintes inter-univers ; merge `a065ad80eeb6db73438e61b1d6cde8bc3293e06d`.
PR #3 : scheduler générique EventStream, événements liés au stream/univers, adaptateur économique
ColonyTimeline ; ordre/idempotence/retries/SKIP LOCKED/rollback/reprise, ressources entières exactes.
Migration 0003 avec historique préservé, roundtrip peuplé et downgrade protégé ; 0001/0002 intactes.
CI finale de #3 : 52 tests backend, 3 frontend, lint/build/docs, PostgreSQL/migrations/Compose verts :
[exécution 40694696012](https://github.com/ThomasPerez91/Echosphere/actions/runs/40694696012).
Modes documentés et ADR 0006 : Universe = instance isolée, pas User/processus ; aucune feature
multijoueur implémentée. master reste l’intégration stable, work/... → PR master → revue/autorisation.

[PR #2](https://github.com/ThomasPerez91/Echosphere/pull/2) · [PR #3](https://github.com/ThomasPerez91/Echosphere/pull/3)
