# Progression — Echosphere

Mise à jour : 2026-10-28. Cadre : [context.md](context.md).

## Reprise et autorisation vérifiées

PR #4 fusionnée sur instruction de Thomas : master `54f928e2348781db43b335d4dcf569aadc0db6e9`.
[CI master 40716684879](https://github.com/ThomasPerez91/Echosphere/actions/runs/40716684879)
verte avant création de `work/step-5a-colony-domain`. Brief joint appliqué : Étape 5A uniquement.
[PR #5](https://github.com/ThomasPerez91/Echosphere/pull/5) vers master ; aucune autorisation de fusion.
Aucune develop recréée, branche empilée, release ou déploiement.

## Domaine et règles livrés

- game_data/rulesets/v0.1 : resources.json, colony.json, infrastructures.json. JSON/Pydantic strict,
  clés dupliquées/versions mixtes/extras/mauvais types refusés ; erreur explicite sans fallback.
- Référence : 12 secteurs, 2 slots orbitaux réservés, 4 infrastructures I, 8 secteurs libres,
  Command Core conceptuel hors secteurs. Stocks 2000/1500/750, taux 120/100/60 par heure, capacité 10000.
- Cinq infrastructures configurables : trois producteurs répétables ; industrie/logistique uniques.
  Un secteur par exemplaire, aucun secteur de plus à l’upgrade ; niveaux continus sans plafond 5.
- Niveaux explicites 1–5 puis récurrence : producteurs coût/durée/production ×1,38/1,28/1,12 ;
  industrie ×1,40/1,30 et +5 points de bonus ; logistique ×1,40/1,30/1,18. Aucun facteur en service.
- Entiers micro-unités et microsecondes, fractions exactes. Scaling coût/durée plafond,
  production/capacité plancher, durée effective plafond, remboursement plancher. Refus de dépassement.
- Snapshot complet validé par univers, vitesses rationnelles par instance ×1 ; économie/construction
  actives, recherche/flotte seulement réservées. Pas de singleton ni changement implicite des instances.
- Ordre : snapshot version/coût/durée/type/niveau/secteur/vitesse/remboursements. Réservation à l’entrée,
  trois ordres actif inclus, un actif, clé de commande idempotente, prochain bonus industriel évalué
  à l’activation. Prérequis sur infrastructures achevées ; niveaux contigus avec prédécesseurs réservés.
- Annulation 100 % queued / 80 % active, idempotente. Cascade des upgrades dépendants du même secteur ;
  les autres gardent leur ordre. Démarrage suivant à la date logique d’annulation. Remboursement exact
  impossible faute de stockage : refus atomique sans perte/overflow caché, Q39 pour validation produit.
- Production réglée avant changement de niveau/capacité ; perte de production au plafond, reste nul.
  CONSTRUCTION_COMPLETE réutilise EventStream, SAVEPOINT, retries et worker ; aucune seconde file timer.
- Services internes configure_universe/initialize_colony/enqueue/cancel, scope univers/empire/colonie,
  verrou du stream et catch-up complet avant mutation. Transaction du caller, aucun commit interne.

## Persistance et image

Migration `0004_colony_economy`, migrations 0001–0003 intactes. Tables universe_economies,
colony_economies, colony_infrastructures et construction_orders. FK composites, secteur unique,
niveau >=1, unicité de clé/séquence, index partiel un actif. Capacité de planète et limites du ruleset
vérifiées par les services sous lock ; pas de duplication de game_data dans des CHECK de catalogue.
Upgrade/downgrade/upgrade vide et alembic check ; downgrade peuplé refusé avant DDL, pas de suppression
silencieuse. Pas de backfill fictif des anciennes timelines : leur adoption métier reste hors lot.
Contexte build backend à la racine pour inclure game_data ; .dockerignore et emplacement image explicites.
Compose conserve monolithe API/worker/PostgreSQL, vérifie le chargement des données dans le worker.

## UI et documentation

Colony : Vue d’ensemble / Infrastructures / Orbite / Défense, liens directs #colony/<vue>, sélection
globale Colonie conservée, focus/clavier/historique. Aucune huitième entrée principale, colonie/stock/
bâtiment/timer fictif ou commande de défense. État « Aucun univers / aucune colonie active ».
Défense documentée dans planetary-defense.md : réseau stratégique limité, modules persistants,
coût d’opportunité surface/orbite, dommages/réparation/Flux et révélation par renseignement futurs.
Aucune table DefenseNetwork/Module ou effet actif. Q30–Q38 ajoutées et ouvertes ; Q39 remboursement.
ADR 0007, docs produit/UX/tech/qualité, AGENTS, context et roadmap actualisés. Étape 5 scindée en
5A domaine/économie/construction et 5B API/UI interactive après contrat identité/autorisation Q16.
Les arbitrages v0.1 ne ferment pas les questions générales d’équilibrage et de modes.

## Validation en cours

Local : Ruff, 42 tests unitaires backend, ESLint, 11 tests frontend, build, 5 scénarios Chromium et
56 documents/liens. Captures Colony/Défense inspectées à 320 et 1440 ; scénarios aux quatre largeurs
320/390/768/1440. Les 59 intégrations PostgreSQL sont à exécuter par la CI, pas revendiquées en local.
101 tests backend collectés au total ; tests antérieurs conservés et complétés.

Première CI source 789aa96 : frontend et Compose verts, backend 98 réussis/1 échec de test.
L’intervalle de saturation logistique était de dix jours, insuffisant pour les Données ; corrigé
à vingt jours. Ajout de tests d’édition réelle du catalogue sans repricing et d’événement étranger.
Vérifier la prochaine tête et sa CI finale avant livraison ; une CI configurée n’est pas une preuve.

## Limites et reprise

1. Vérifier tête/CI/revue de PR #5, consigner le résultat effectif puis laisser non fusionnée.
2. Règles v0.1 provisoires, pas de simulation d’équilibrage longue ou charge massive revendiquée.
3. Aucun PostgreSQL/Docker local exploitable ; intégrations, migrations et Compose validés sur GitHub.
   Pas de recette WSL2/Docker Desktop, tactile/lecteur d’écran réel, Safari/Firefox.
4. Politique de remboursement au stockage insuffisant à revoir (Q39). Changement de ruleset/vitesse
   d’univers actif et adoption des anciennes timelines nécessitent un lot explicite.
5. Après revue/intégration, cadrer Q16 avant 5B. Aucune API gameplay (lecture ou mutation), identité
   globale factice ou gameplay cliquable. Pas d’auth complète, multijoueur, invitations, PvP,
   espionnage, combat, défense réelle, flotte, recherche ou colonisation implémentés dans ce lot.

## Historique

Étapes 0–4 : PR #1 bootstrap, #2 fondation SQLAlchemy/Alembic et modèles, #3 scheduler générique
corrigé, #4 shell responsive. Fusion #3 : 4ee81dd, CI 52 backend/3 frontend/Compose ; fusion #4 :
54f928e, source 52 backend/10 frontend/5 Chromium/Compose. develop supprimée par Thomas et absence
vérifiée. master = intégration stable, work/... → PR master → revue/autorisation propre à chaque merge.
