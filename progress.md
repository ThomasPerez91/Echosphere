# Progression — Echosphere

Mise à jour : 2026-10-28. [Contexte](context.md), [passation](docs/06-handoff/README.md).

## Dernier lot — passation documentaire Work / Codex

**Périmètre : documents uniquement**, plus liste des documents requis dans scripts/check_docs.py.
Aucun service, gameplay, migration/SQL, game_data, dépendance, Compose/Docker ou test fonctionnel changé.
Branche existante work/step-5a-colony-domain et PR #5 conservées ; pas de nouvelle branche/PR,
force push, suppression, merge, tag ou déploiement. Environnement de cette livraison : ChatGPT Work.

### État initial vérifié

PR #5 ouverte, mergeable, non fusionnée, tête 5be00da4726abd8fb38bd159deab1f1cf687df52 vers master
54f928e2348781db43b335d4dcf569aadc0db6e9. CI 40721303421 verte (backend/frontend/compose-smoke).
Dernier commit : context/progress seulement après 58e8f7c fonctionnel. Seules master et la branche #5
restent listées ; les anciennes branches work ont disparu, sans action de cette mission. Pas de develop.
Audit code/tests et limites dans [audit #5](docs/06-handoff/pr-5-audit.md).

### Travail et sources

Vision et documents existants enrichis, chiffres v0.1 préservés. 12 secteurs/2 orbitaux explicitement
limités au départ de référence ; Q39 toujours ouverte. Status implémenté/validé/provisoire/proposé/futur
séparés. Architecture actuelle réconciliée avec code, anciennes contradictions signalées superseded.

ADR 0008 créé sans renuméroter 0007 : compte global multi-parties, deux backends Portal/Game isolables,
Accounts DB/Game DB distinctes, interface interne contrôlée sans SQL Portal→Game, GameSession autonome
après ticket court/unique et gameplay direct. Décision validée **non implémentée**, protocoles non choisis.
Q16 partiellement cadrée, Q01–Q39 préservées, Q40–Q56 ouvertes. Roadmap : 5A → 5B contrats identité/
Portal-Game → 5C compte/lobby selon cadrage → 5D API Colony/UI sécurisées. Aucun Portal complet anticipé.

Dossier docs/06-handoff : README, source-map, decision-status, work-codex-handoff, known-gaps,
pr-5-audit. Procédure symétrique fetch/lecture/qualité/commit/push/SHA-CI pour Work et Codex ; reprise
locale WSL2 proposée mais jamais présentée comme testée. AGENTS devient la procédure commune.

Sources : dépôt, PR #1–5/CI/commits, contexte visible et brief de mission ; recherche contextuelle
partielle ciblée a retrouvé des extraits cohérents, pas toutes les conversations originales.
Aucun accès exhaustif au projet ChatGPT attesté. Source secondaire de fichier signalée par recherche
non lue intégralement. Pas de conversation brute, information personnelle/secret/identifiant privé
ou sujet hors Echosphere publié. Les décisions anciennes seulement retrouvées dans GitHub restent
qualifiées selon leur preuve, sans promotion des suggestions d’assistant.

### Vérifications et point de reprise

Check documentaire : 63 fichiers et liens locaux ; index ADR 0001–0008, Q01–Q56 sans trou/doublon,
recherche develop/plafond 5/12-2/backend unique et diff documentaire contre 5be00da. Ruff du script.
Les limitations techniques relevées sont consignées, non corrigées : borne secteur au service,
immutabilité de snapshot par contrat applicatif, initialiseur limité à la référence ; Q39 et UX de
cascade encore à valider. Aucun problème bloquant nouveau démontré par la lecture ciblée.

CI de la nouvelle tête documentaire à vérifier après publication. Les tests fonctionnels ne sont
pas relancés localement pour une mission docs ; CI existante complète conservée et ses résultats
seront observés, pas assimilés à une recette WSL2/tactile/charge/anti-DDoS.

Prochaine action : relire la tête publiée et sa CI/revue, laisser #5 non fusionnée. Après intégration
et instruction d’un nouveau lot, cadrer 5B (Q16/Q40–Q56), sans commencer directement une API Colony
ou le multijoueur. Le futur agent ne doit pas déduire une autorisation de merge de ce checkpoint.

## Historique du checkpoint fonctionnel 5A (antérieur à la passation)

Les sections suivantes conservent les preuves/limites du lot fonctionnel, pas une déclaration de
nouveaux tests exécutés dans la passation. La séquence 5B historique est affinée plus haut.

## Reprise et autorisation vérifiées

PR #4 fusionnée sur instruction de l’utilisateur : master `54f928e2348781db43b335d4dcf569aadc0db6e9`.
[CI master 40716684879](https://github.com/l’utilisateurPerez91/Echosphere/actions/runs/40716684879)
verte avant création de `work/step-5a-colony-domain`. Brief joint appliqué : Étape 5A uniquement.
[PR #5](https://github.com/l’utilisateurPerez91/Echosphere/pull/5) vers master ; aucune autorisation de fusion.
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
ADR 0007, docs produit/UX/tech/qualité, AGENTS, context et roadmap actualisés. Historique 5A : la mention 5B API/UI était la séquence de ce checkpoint,
**superseded** par 5B contrats / 5C fondation Portal / 5D API/UI (passation, ADR 0008).
Les arbitrages v0.1 ne ferment pas les questions générales d’équilibrage et de modes.

## Validation source vérifiée

Local : Ruff, 42 tests unitaires backend, ESLint, 11 tests frontend, build, 5 scénarios Chromium et
56 documents/liens. Captures Colony/Défense inspectées à 320 et 1440 ; scénarios aux quatre largeurs
320/390/768/1440. Les 59 intégrations PostgreSQL sont à exécuter par la CI, pas revendiquées en local.
101 tests backend collectés au total ; tests antérieurs conservés et complétés.

Première CI source 789aa96 : frontend et Compose verts, backend 98 réussis/1 échec de test.
L’intervalle de saturation logistique était de dix jours, insuffisant pour les Données ; corrigé
à vingt jours. Ajout de tests d’édition réelle du catalogue sans repricing et d’événement étranger.
CI source finale entièrement verte sur `58e8f7cf32c1b2fbfd9568ec2317cc4338ae7642` :
[run 40720967410](https://github.com/l’utilisateurPerez91/Echosphere/actions/runs/40720967410).
101 tests backend réussis (42 unitaires + 59 PostgreSQL), 11 frontend, 5 Chromium, lint/build,
56 documents/liens, migrations/absence de dérive, chargement v0.1 dans l’image et smoke Compose avec
panne/reprise PostgreSQL. Tous les scénarios antérieurs sont conservés. Ce checkpoint documentaire
suit la source validée ; vérifier la CI de sa propre tête avant toute future fusion autorisée.

## Limites et reprise

1. PR #5 prête pour revue, laissée non fusionnée. Vérifier sa tête documentaire finale et sa CI ;
   le code source 58e8f7c est validé par le run indiqué ci-dessus.
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
54f928e, source 52 backend/10 frontend/5 Chromium/Compose. develop supprimée par l’utilisateur et absence
vérifiée. master = intégration stable, work/... → PR master → revue/autorisation propre à chaque merge.
