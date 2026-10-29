# Progression — Echosphere

Mise à jour : 2026-10-29. [Contexte](context.md), [passation](docs/06-handoff/README.md).

## Lot courant — préparation 5B : contrats identité / Portal-Game

**Statut : décisions utilisateur partielles Q40–Q44 intégrées ; mécanismes encore proposés,
activité explicite Q41/Q43 et comportement Q45 validés ; récupération Q40/Q49 à examiner, 5B non déclarée achevée.**
Après la mission de reprise en lecture seule, l’utilisateur a autorisé le prochain lot sur une
nouvelle branche. Interprétation appliquée selon roadmap : cadrage 5B, sans implémentation 5C/5D.
Environnement : Codex local, Linux WSL2. Aucune délégation ni identité d’agent précédent supposée.

### Déconnexions Q45 — 2026-10-29

Source : validation explicite utilisateur pour PR #6. Comportement produit Q45 clos, non implémenté :
retour lobby sans logout ; déconnexion Game d’une seule session ; compte sur appareil courant
(PortalSession courante + toutes ses GameSessions du compte) ; tous appareils comme action distincte.
Autres appareils préservés lors du logout normal ; memberships/empires/états/progression/actions
acceptées conservés. Révocation globale persistée/rejouée jusqu’à acquittement, état UI en attente
si service injoignable, borne valid_until/8 h inchangée. Aucune autre Qxx close par implication.
Regroupement appareil sous Q41/Q43 ; protocoles sous Q53/Q54 et tickets en vol sous Q42/Q56 ouverts.
Un epoch d’accès commun ne peut implémenter le logout d’un seul appareil : limite explicitée,
sans adopter un nouveau modèle de stockage. Matrice d’acceptation future complétée, aucun test
fonctionnel de ces mécanismes exécuté.

Reprise : fetch, branche work/step-5b-identity-contracts propre et synchronisée sur d879f7e5002d91342f08819ff2bad69ee83ad7d0 ;
PR #6 OPEN/brouillon, base master 8214e0b inchangée. CI de cette tête observée verte :
push 40879933579 et PR 40879939979, backend/frontend/compose-smoke réussis.
Fichiers : contrats, registre Qxx, context/progress, sécurité, API/architecture, ADR 0008, roadmap,
README/index/passation/décisions/lacunes. Résumés périmés corrigés ; Markdown uniquement.
Checks locaux : check documentaire, diff, Q01–Q56 et comparaison des statuts ; seules les décisions
Q45 changent, aucune autre fermeture. Suites fonctionnelles backend/frontend/Compose et Ruff
non relancées localement pour ce diff documentaire ; CI de la nouvelle tête à observer après push.
Prochain arbitrage nécessaire : Q40/Q49, durée du jeton de récupération, réémission et effets sur
sessions ; puis changement d’email et périmètre MFA Q48. Aucun choix implicite depuis Q45.
Aucun merge de PR #6, passage à 5C ou implémentation ; résultats CI publiés dans la PR après observation.

### Complément activité Q41/Q43 — 2026-10-29 (checkpoint antérieur à Q45)

Source : arbitrage explicite utilisateur, synthétisé dans identity-contracts et Qxx. Seules les
interactions explicites classées côté serveur réinitialisent l’inactivité ; toutes les catégories
automatiques citées dans le contrat sont exclues. Heure serveur, aucun timestamp client autoritaire ;
aucune modification des maxima absolus ou de valid_until. Q41/Q43 restent partiellement ouvertes,
Q45–Q56 inchangées. Aucune implémentation ni fusion autorisée.

Reprise : fetch effectué, arbre propre, tête locale/distante 5dbd9184509ca6323279365944dea9567207cd17,
PR #6 OPEN/brouillon, base master 8214e0b inchangée. CI de cette tête vérifiée : push 40878132584
et PR 40878144213, backend/frontend/compose-smoke réussis.
Fichiers : identity-contracts, open-questions, context, progress, sécurité, roadmap et index des décisions.
Scénarios futurs complétés : catégories automatiques sans effet, interactions explicites, timestamp
client falsifié, échéance contrôlée avant réinitialisation et maxima inchangés. Aucun test de ces
mécanismes futurs exécuté. Vérifications locales : check documentaire, diff et périmètre Markdown ;
aucune suite fonctionnelle backend/frontend/Compose ni Ruff relancée pour ce complément documentaire.
Après publication, relire SHA distant et CI effective de cette nouvelle tête ; les résultats de
5dbd918 ci-dessus ne prouvent pas la CI du présent commit.
Prochaine décision à ce checkpoint : Q45, depuis arbitrée dans le complément ci-dessus. 5C/5D restent hors de ce lot documentaire.

### Arbitrages utilisateur intégrés — 2026-10-29, checkpoint antérieur à Q45

Source : validation explicite utilisateur pour poursuivre PR #6, synthétisée dans le canonique
identity-contracts.md et le registre Qxx, sans transcript brut. Aucune validation implicite
du reste de la proposition et aucune autorisation de fusion.

- Q40, parties closes : MVP email/mot de passe ; email vérifié avant premier handoff ; récupération
  courte/unique ; Argon2id via bibliothèque maintenue ; global_user_id indépendant de l’email et de
  la méthode. Google/OIDC supplémentaire futur facultatif. Bibliothèque/paramètres et récupération
  détaillée restent ouverts ; fournisseur email et MFA dans leurs Q49/Q48 restent à arbitrer.
- Q41, partie close : Portal 7 jours absolus et **72 heures** d’inactivité, remplaçant la proposition
  initiale de 24 h. Activité sans prolongation du maximum absolu ; cookies/stockage/rotation ouverts.
- Q42, parties closes : ticket de handoff 60 secondes et usage unique. Format, crypto, liaison
  navigateur et mécanismes anti-rejeu toujours ouverts ; aucune durée de récupération déduite.
- Q43, parties closes : Game 8 h absolues/2 h d’inactivité, GameAccess pouvant expirer plus tôt ;
  absolu non prolongé par activité. Stockage et limites simultanées ouverts ; activité arbitrée dans le complément ci-dessus.
- Q44, parties closes : droits au plus 8 h depuis dernière confirmation Portal, non glissants et
  sans reset en panne ; révocation/suspension reçue immédiate ; nouvelles commandes refusées à
  valid_until, univers/workers continuant. Renouvellement avec Portal disponible et nouvelle
  confirmation/handoff valide ; aucune autonomie illimitée. Protocoles/synchronisation non choisis.

Q40–Q44 restent partiellement ouvertes ; Q16/Q21/Q45–Q56 ne sont pas fermées. Les comptes,
sessions et tickets ne sont toujours pas implémentés. La validation de la fenêtre ne vaut pas
acceptation de mTLS, JWT, stockage opaque, cookies, epoch, outbox ou politique de logout.

Poursuite documentaire : expressions des échéances et exemples de confirmation retardée/panne
ajoutés, scénarios futurs de frontière et compte MVP précisés. Aucun test artificiel ou code ajouté.
À ce checkpoint antérieur, l’activité Q41/Q43 restait à arbitrer ; le complément ci-dessus
consigne désormais sa validation explicite.
Les autres questions techniques restent listées pour la suite, pas repoussées implicitement à 5C.

Fichiers de cette continuation : identity-contracts, open-questions, context/progress et références
README/docs/index/architecture/API/sécurité/ADR 0008/roadmap/passation/known-gaps pour éviter des
mentions périmées « durées/login encore proposés ». Diff Markdown uniquement, aucun changement de
code, test, dépendance, migration, ruleset, Compose ou script.

Vérification initiale de cette continuation : arbre propre, branche locale et distante à
2d1efdabac4a5e6396b515f63fc02684869c8ac9 après fetch, PR #6 OPEN/draft sur la même tête vers
master 8214e0b ; seule PR ouverte listée. CI de cette tête relue :
[40873616329](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873616329) et
[40873623209](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873623209), tous les jobs
backend/frontend/compose-smoke réussis. Aucun merge, changement de branche ou travail concurrent.
Checks de cette continuation exécutés : 64 documents/liens valides, git diff --check sans erreur,
Q01–Q56 sans trou/doublon ; comparaison avec HEAD confirmant que seuls les libellés Q40–Q44
changent dans les tableaux du registre et qu’ils restent explicitement partiellement clos.
Relecture des limites/formules/exemples, de la séparation validé/proposé et du diff de confidentialité.
Périmètre Markdown uniquement vérifié. Aucune suite backend/frontend/Compose ou Ruff relancée
localement pour ce changement documentaire ; aucun nouveau mécanisme de session testé.
Publication effectuée sur la même PR #6 brouillon, restée OPEN/non fusionnée :
56e43a9bf5a9100e22ad3c4363095a45b0452db9, SHA distant relu ; master reste 8214e0b.
CI de ces arbitrages : [push 40877809734](https://github.com/ThomasPerez91/Echosphere/actions/runs/40877809734)
et [PR 40877818343](https://github.com/ThomasPerez91/Echosphere/actions/runs/40877818343),
backend/frontend/compose-smoke tous réussis sur cette tête. Description de PR actualisée avec
les décisions partielles et les mécanismes non validés. Ce checkpoint consigne ces résultats
après leur observation ; vérifier également sa propre CI publiée. Aucune CI présentée comme
preuve d’un mécanisme Portal/Game futur, aucun merge ni passage à 5C.

### Base et périmètre initiaux (historique de préparation)

GitHub relu : PR #5 MERGED, tête acde9d358bfe724be61198cd60fd1e72c6e38459, base master,
merge 8214e0bd30a00bf0336264a428e6975d307350ba. Fetch effectué ; master locale propre et identique
à origin/master. Aucune PR ouverte au contrôle, aucune develop. CI master
[40765430216](https://github.com/ThomasPerez91/Echosphere/actions/runs/40765430216) completed/success
sur ce merge, jobs backend/frontend/compose-smoke verts. Dernière livraison consignée : passation
Work par #5 ; cette recette locale lui succède sans attribuer un nom non attesté à son auteur.

Branche : work/step-5b-identity-contracts, créée depuis cette master sans empilement.
Premier commit publié : e3d2f8ec1dcb647a147dc9d885be4f06f9f46802,
[PR #6](https://github.com/ThomasPerez91/Echosphere/pull/6) brouillon OPEN vers master.
Le présent checkpoint documentaire suit ce commit ; consulter aussi sa propre CI publiée.
Aucune fusion, suppression de branche, release ou déploiement autorisé.

Fichiers : nouveau docs/03-technical/identity-contracts.md ; références API/sécurité/modèle/architecture,
index docs/ADR/décisions, README/passation, roadmap/questions/known-gaps, context/progress et liste
des documents requis de scripts/check_docs.py. Aucun code métier, game_data, migration, dépendance,
Compose, composant UI ou test fonctionnel modifié.

### Préparation initiale et statut des propositions (avant les arbitrages ci-dessus)

Contrats proposés : autorités Portal/Game, participation/accès local versionné/bindings d’Empire,
interface interne idempotente avec révisions/outbox/réconciliation, handoff lié au navigateur,
consommation atomique, session opaque et contrôles locaux, concurrence avec révocation, logout,
rotation de clés, isolation et matrice de scénarios futurs. Alternatives et sources OWASP/RFC
publiques consignées. À ce premier checkpoint, aucun protocole, algorithme, fournisseur ni durée
nouveau n’était présenté comme accepté.
Relecture : distinguer la révision de livraison de l’epoch d’invalidation des sessions pour qu’un
renouvellement à droits inchangés ne déconnecte pas les sessions valides ; cookies par univers
proposés pour les onglets multi-parties, limite de sessions/cleanup restant sous Q43.

Arbitrage principal alors proposé : validité locale des droits bornée à 8 h, session Game 8 h absolues/
2 h d’inactivité, ticket 60 s ; autonomie en panne Portal jusqu’aux limites, révocation appliquée
dès livraison mais non instantanée si liaison coupée. Ces valeurs étaient des propositions à revoir,
depuis acceptées uniquement dans le périmètre décrit en tête. Q21 et les questions de modes restent ouvertes. 5C ne commence
pas automatiquement après la rédaction ; recueillir les arbitrages nécessaires et leur provenance.

### Recette de reprise locale réalisée avant création de la branche

Cette recette appartient à la mission de reprise du 2026-10-29, sur master 8214e0b inchangée ;
elle ne valide aucun mécanisme futur de 5B et n’a pas été relancée pour le diff documentaire.

- `python3 scripts/check_docs.py` : 63 documents/liens valides.
- `docker compose ps -a` : postgres/backend/frontend healthy, worker running, migrate Exited (0).
- `docker compose exec backend alembic check` : aucune dérive ; current = 0004_colony_economy head.
- `python3 scripts/smoke_compose.py` : succès, frontend/proxy/sondes et panne/reprise PostgreSQL.
- Backend dans un conteneur Python 3.12 : premier passage 42 réussis/59 ignorés sans RUN_DB_TESTS.
  Passage complet avec base dédiée echosphere_codex_20261029_test : initialement 100 réussis/1 échec
  de chemin game_data, puis 101 réussis après montage de l’arborescence complète en lecture seule.
  La base dédiée a été supprimée ensuite ; aucune suite de downgrade sur la base de jeu.
  Ruff backend/scripts passe. Avertissement Starlette/httpx déprécié observé.
- Frontend conteneur Node 22 : npm ci, lint, 11 tests et build réussis. Les empreintes des fichiers
  App, test, CSS, ColonyView, scénario E2E et package-lock de l’image concordaient avec le dépôt.
- Playwright : installation impossible dans Alpine (apt-get absent), puis 5 scénarios Chromium
  réussis dans un conteneur Debian Node 22 jetable, copie de sources montées en lecture seule.
  Largeurs 320/390/768/1440 et navigation clavier/retry. Aucun test navigateur Windows attesté.
- Chargement du ruleset dans l’image worker : v0.1. Diff et état Git propres à la fin de la recette.

Limites environnement : noyau 6.18.54.1-microsoft-standard-WSL2, Compose v5.6.1, Python hôte 3.14.4,
pas de Node/npm hôte ni backend/.venv. Les tests ont utilisé les versions Docker prévues, sans
installer les outils sur l’hôte. Les premiers accès fetch/socket Docker/localhost ont été refusés
par le bac à sable puis ont réussi avec autorisation ; aucun défaut WSL2 démontré par ces refus.
Pas de recette graphique Windows, tactile, lecteur d’écran, Safari/Firefox, charge massive ou
résilience Portal/Game réel (inexistant). Pile Compose laissée démarrée, volume de jeu conservé.

`npm audit --json` : 3 dépendances affectées (1 modérée, 2 critiques) dans la chaîne de développement
Vitest/@vitest/mocker/tinypool. Aucun correctif automatique effectué. Voir known-gaps pour les avis.

### Validation du premier checkpoint documentaire (historique)

Checks du diff 5B exécutés : 64 documents/liens valides, git diff --check sans erreur,
Q01–Q56 présentes exactement une fois dans les tableaux du registre ; périmètre Markdown et
liste REQUIRED de check_docs.py vérifié. Ruff de scripts/check_docs.py passe dans le conteneur
Python 3.12 avec dépendances de développement figées. Relecture du nouveau contrat, de ses statuts,
de ses liens et du diff de confidentialité effectuée. Aucune suite fonctionnelle relancée pour
ces changements documentaires ; les scénarios 5B sont des critères futurs non exécutés.
Branche publiée, SHA distant e3d2f8e relu, PR #6 brouillon créée et non fusionnée.
[CI push 40873175483](https://github.com/ThomasPerez91/Echosphere/actions/runs/40873175483)
completed/success sur e3d2f8e, jobs backend/frontend/compose-smoke verts. Ces résultats ne prouvent
aucune implémentation des contrats futurs. Le présent checkpoint et les précisions de relecture
suivent cette tête ; leur CI propre reste à relire après publication, sans la présumer réussie.
Prochaine action à ce checkpoint : revue et arbitrage, désormais partiellement effectués comme
consigné en tête ; pas d’implémentation Portal/API Colony sur la seule présence du document.

---

## Lot précédent — passation documentaire Work / Codex (historique)

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

Passation publiée en deux commits :
- 14fd4db40b3a422228433af7ede9842caa61c363 — docs: consolidate product and Portal-Game isolation decisions.
- 2748d41fba0fdd3fcf09ce2e60c4ad1f07e999cd — docs: add durable Work and Codex handoff procedure.

[CI 40742149137](https://github.com/ThomasPerez91/Echosphere/actions/runs/40742149137) entièrement
verte sur 2748d41 : backend/frontend/compose-smoke, 101 tests backend (42 unitaires + 59 PostgreSQL),
11 frontend, 5 Chromium, build/lint, 63 documents/liens et démarrage/panne-reprise PostgreSQL.
Les tests fonctionnels ne sont pas relancés localement pour la mission docs ; leurs fichiers sont
inchangés. Ces résultats CI ne sont pas une recette WSL2/tactile/charge/anti-DDoS. Le présent commit
de checkpoint suit cette tête validée : vérifier aussi sa propre CI avant toute fusion autorisée.

### Prochaine action selon l’état GitHub réel

L’état GitHub réel prévaut sur les états historiques de ce document.

- **Si PR #5 est encore ouverte** : vérifier sa tête publiée et sa CI, effectuer la revue ;
  merge uniquement sur autorisation explicite. Reprendre sa branche pour une mission sur #5,
  sans créer de nouvelle branche ou PR pour ce lot.
- **Si PR #5 est déjà fusionnée** : synchroniser master, considérer 5A/passation comme intégrées,
  puis effectuer la recette locale WSL2/Docker/Codex selon la procédure de passation. Cette recette
  n’a pas encore été effectuée. Ne pas recréer une branche #5. Le prochain développement fonctionnel
  est 5B (Q16/Q40–Q56), uniquement après instruction, sur une nouvelle branche work/... issue de
  master synchronisée ; ne pas commencer directement une API Colony ou le multijoueur.

Le futur agent ne doit pas déduire une autorisation de merge ou de développement de ce checkpoint.

## Historique du checkpoint fonctionnel 5A (antérieur à la passation)

Les sections suivantes conservent les preuves/limites du lot fonctionnel, pas une déclaration de
nouveaux tests exécutés dans la passation. La séquence 5B historique est affinée plus haut.

## Reprise et autorisation vérifiées

PR #4 fusionnée sur instruction de l’utilisateur : master `54f928e2348781db43b335d4dcf569aadc0db6e9`.
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
[run 40720967410](https://github.com/ThomasPerez91/Echosphere/actions/runs/40720967410).
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
