# Étape 6 — Recherche globale d’Empire

**Statut au 31/10/2026 : R00 publié ; R01 proposition à arbitrer ; R02–R09 non commencés.**
Une seule branche `work/step-6-research`, une seule [PR #9](https://github.com/ThomasPerez91/Echosphere/pull/9)
en brouillon. Base master `0e2ca11322a85452ad6860a4a35099bbc22a4689`, fusion #8/5D vérifiée ;
[CI post-merge 41144706921](https://github.com/ThomasPerez91/Echosphere/actions/runs/41144706921) success.
Premier checkpoint **098ab078889ca7a41b5ed77055663a439670ccdf** publié avant ce plan et avant code.
L’état GitHub réel prévaut toujours sur les anciens checkpoints.

**Verrou produit explicite :** l’utilisateur demande de présenter Q05 puis de s’arrêter pour son
arbitrage avant migration, backend Research, catalogue exécutable ou UI fonctionnelle. La portée
validée ci-dessous est distincte de la [recommandation Q05 non validée](../01-game-design/research.md).
Une fois Q05 validée explicitement, R02–R09 seront autorisés sans confirmation par détail technique.
Aucune fusion ni étape 7 sur la seule base de ce plan.

## Contrat déjà validé et sortie cible

Recherche globale à l’Empire, quatre domaines provisoires Ingénierie/Énergétique/Calcul/Xénoscience,
arbre court, orientations sans enfermement précoce. Coût/durée/effets/prérequis lisibles avant
confirmation, active et suivante programmée, effet unique à l’échéance. Même service métier humain/
future IA, vérifications dans la transaction et backend Game autoritaire. Réutiliser EventStream,
ScheduledEvent et worker ; aucun deuxième scheduler ou nouvelle ressource.

Sortie future : login → lobby → handoff → GameSession → Empire → recherche disponible avec coût/
prérequis réels → réservation → échéance persistée → navigateur fermé → achèvement worker une seule
fois → suivante activée selon Q05 → effets visibles dans l’état réel. Même lecture/lancement/file/
achèvement avec Portal arrêté et session encore valide ; refus à ses échéances 5B/5C.
Les smokes/fixtures ne remplacent pas un parcours produit de création de partie, toujours hors lot.

## Références relues

- AGENTS/CLAUDE/context/progress, roadmap et registre Q01–Q56.
- [Recherche/Q05](../01-game-design/research.md), [boucle](../01-game-design/core-loop.md),
  [progression](../01-game-design/progression.md), [balance](../01-game-design/balance-philosophy.md).
- [Moteur temporel](../03-technical/event-engine.md), [modèle](../03-technical/data-model.md),
  [sécurité](../03-technical/security.md), [API Colony](../03-technical/colony-api-ui.md).
- [Guide visuel](../visual-reference/README.md), [design-system.png](../visual-reference/design-system.png),
  [research-view.png](../visual-reference/research-view.png) inspectés : composition seulement.
  Les trois places, grandes listes, laboratoires, flottes et technologies dessinées ne sont pas validés.

## Découpage et critères futurs

| Ticket | Portée | Critère de sortie et statut actuel |
| --- | --- | --- |
| R00 | Vérifier #8/master/CI, synchroniser master, créer branche, publier checkpoint post-merge | Fait : 098ab07 ; 5D intégrée et aucune Research livrée |
| R01 | Proposition produit Q05 et contrat canonique | Proposition complète dans research.md, attente validation utilisateur ; ne pas marquer clos avant réponse |
| R02 | Petit catalogue/version/ruleset, quotes et validation stricte | Futur après Q05 ; noms/chiffres balançables, effets réels, prérequis connus/acycliques et tests de données ; aucune modification silencieuse des univers |
| R03 | Persistance et migration additive Game | Futur ; état Empire, ordres/acquis/effets/stream avec FK/scopes/uniqueness/index et upgrade/check/roundtrip/refus de downgrade peuplé |
| R04 | Services métier et handler du moteur existant | Futur ; paiements/rattrapages/idempotence, file, annulation, acquisition/effet uniques, rollback et concurrence ; petits effets Colony seulement si Q05 les valide |
| R05 | Projection/API Game et droits explicites | Futur ; chaîne session→accès→binding→Empire, non-fuite, CSRF/enveloppes strictes, extension explicite des permissions de contrôle, aucun accès automatique |
| R06 | Recherche connectée dans le shell existant | Futur ; acquis/active/suivante/options/verrous, paiement explicite, coûts/effets/prérequis et preview d’annulation selon Q05 ; aucune donnée runtime fictive |
| R07 | Refus, responsive, accessibilité et concurrence | Futur ; tests intégrés des cas ci-dessous, clavier/320/390/768/1440, confirmation dans le viewport, retry même intention |
| R08 | Recette réelle worker hors connexion et Portal coupé | Futur ; scénario complet HTTPS et bases jetables, effets visibles réels et deadline refusée ; aucune API interceptée dans cette recette |
| R09 | Relecture complète, validations, CI et passation | Futur ; SHA final vert, docs/checkpoint/description PR, Ready for review si réellement prêt ; aucun merge automatique |

Les colonnes de sortie sont des critères **non exécutés** pour Research. Les succès des étapes
3/5A/5D et de la CI du présent diff documentaire ne prouvent aucun de ces mécanismes futurs.

## Constats du code et décisions techniques à appliquer après Q05

### État et financement distincts

Empire existe dans app/persistence/models.py ; aucun état Research. ResourceBalance est attaché
à ColonyTimeline (colony_id/resource). Q05 propose une colonie payeuse explicite sans créer de caisse
Empire. Ne pas déplacer l’autorité Research sur Colony ou injecter un stock/Empire gratuit.

R03 devra définir un adaptateur typé Research d’Empire (noms de tables à préciser), un stream unique
référencé par FK composite avec universe_id, des acquis uniques Empire/technologie et ordres/reçus
idempotents. Aucun owner_kind/owner_id polymorphe sans FK. Pas de seed d’acquis à chaque démarrage ;
lire un Empire sans ordre doit produire un vrai état vide, pas un catalogue simulé.

### Coordination des verrous et effets, point d’attention R04

Le scheduler actuel ordonne due_at/séquence **par stream**, pas entre streams. Ses handlers ne
commitent pas et ne verrouillent pas un second stream. Garder cette contrainte ; un simple ajout
RESEARCH_COMPLETE ne résout pas une dépense de ressources Colony ni une annulation multi-colonies.

Proposition technique à détailler et tester avant implémentation des commandes R04 :

1. Adapter HTTP : verrou du principal Game (comme révocation C06), contrôles GameSession/accès/binding.
2. Coordination métier : stream Research de l’Empire, puis streams des colonies de financement
   nécessaires, dans un ordre total stable. Initialisation de l’ancrage Empire sérialisée.
3. Rattraper les échéances Research et la production des sources avant réservation/remboursement ;
   exiger catch-up complet, aucun état projeté au-delà d’une tête bloquée. Même transaction/SAVEPOINT.
4. Le handler de fin ne touche que les acquis/effets/file de l’Empire, et planifie le suivant depuis
   sa durée snapshotée ; **pas de remboursement ou écriture de stocks Colony dans ce handler**.
   Une incompatibilité métier de la suivante suspend son démarrage selon la proposition Q05 ;
   son annulation explicite coordonne ensuite les verrous/sources de remboursement.
5. Les effets initiaux proposés sont appliqués aux nouveaux devis acceptés, pas à la production
   continue ou aux ordres déjà réservés. Pour les réductions de coût Colony, ses routes de lecture/
   commande devront coordonner Research avant Colony sur les univers compatibles, puis déléguer
   à la quote métier commune ; ne jamais prendre un verrou Research après avoir pris Colony.
   Les handlers Colony existants restent indépendants et n’ont pas à verrouiller Research.

Documenter les interactions avec API Colony, worker et accès partagés par plusieurs participants :
le verrou d’un principal utilisateur seul ne sérialise pas deux participants du même Empire.
La matrice de concurrence doit couvrir Research contre dépenses/annulations Colony, sources de
financement différentes, demandes croisées et deux workers. S’il faut étendre le moteur générique,
le faire minimalement sous tests sans changer ses invariants ni créer une seconde ordonnance.

### Rulesets et compatibilité — Q26 préservée

Le loader v0.1 est strict, ses trois JSON sont déjà copiés dans UniverseEconomy. Le champ vitesse
research réservé ne signifie pas qu’un catalogue Research est présent. Ajouter une clé obligatoire
ou un défaut silencieux à tous les anciens snapshots casserait le contrat de version.

Recommandation technique R02 : nouveau ruleset complet compatible Colony (par exemple v0.2),
avec catalogue Research et lecture explicite de v0.1 conservée. Ne pas réécrire les JSON v0.1, ni
leur snapshot en base pour activer la Recherche à l’insu du joueur. Les instances v0.1 continuent
leur boucle Colony et affichent honnêtement Research indisponible pour leur version. Les nouvelles
instances/recettes compatibles épinglent explicitement la nouvelle version. Une adoption d’un
univers déjà actif nécessitera une procédure explicite, jamais backfill opportuniste à la lecture.
La création complète de partie produit et une migration générale de ruleset restent hors lot.

Quotes/effets/prérequis/durées versionnés et partagés par services, projection et future IA.
Arrondis entiers/rationnels, coûts non négatifs et au moins un coût positif, bornage BIGINT/date,
aucun float économique ni constantes dispersées dans HTTP/React. Refaire la matrice 5A/Q39 pour
préserver snapshots, remboursements et niveaux continus de la construction avec les effets validés.

### Permissions : extension du contrôle privé nécessaire, pas nouvelle identité

Les seules permissions acceptées actuellement sont colony.read/construct/cancel :
app/control/contracts.py, CHECK SQL EmpireBinding dans Game 0005, schéma
contracts/portal-game/v1.schema.json et allowlist Portal control/service.py. Le max de trois du
Binding est aussi à adapter. Les payloads GameSession reflètent le snapshot d’accès courant.

R05 devra propager les droits Research validés dans tous ces validateurs et une migration additive
pour le CHECK **sans réécrire 0005 publiée**. Relire aussi les tests/contrats de contrôle et la
compatibilité de livraison pendant un déploiement. Aucun droit Research ajouté aux anciens grants
par défaut ; attribution explicite, confirmation Portal et limites de validité inchangées.
Ceci est une extension ciblée aux services/contrats 5C, pas une refonte de Portal/auth/membership.
Aucun secret Accounts, SQL Portal→Game ou requête gameplay vers Portal.

### Interface et vision

Research appartient à l’Empire courant autorisé ; si plusieurs bindings Empire, sélection explicite,
pas l’hypothèse un compte = un Empire. Sélection de colonie payeuse distincte du scope Research.
Quatre cartes/domaines provisoires, panneaux active/suivante/acquis/disponible/verrouillé suivant le
vrai catalogue ; reprendre palette navy/cyan et composants du shell. Afficher la portée Empire et
la colonie financée sans présenter une caisse globale inexploitable. Aucun compteur 8/24 fictif,
tech de flotte/défense, popup d’accélération ou laboratoire absent pour remplir le mockup.
Temps restant = projection de dates serveur ; pas d’achèvement client, présence ou polling qui
prolonge la session. Reprendre générations/abort/retry de 5D et ne jamais envoyer une mutation
sur montage React/StrictMode. Aucune UI fonctionnelle Research dans le checkpoint actuel.

## Matrice de tests futurs obligatoires

| Groupe | Cas à prouver après validation Q05 |
| --- | --- |
| Idempotence | Double clic ; même clé/contenu avant/après fin/annulation ; même clé/payload différent ; retry après timeout/réponse perdue ; anti-rejeu d’événement et acquis/effet uniques |
| File | Deux demandes, dernière place, technologie déjà acquise/active/queued, prérequis manquant, suivante dépendante/indépendante, annulation/cascade, incompatibilité au démarrage expliquée |
| Ressources | Financement explicite même Empire, insuffisance, rattrapage, saturation mono/multi lors remboursement, deux ordres/même source et sources différentes, construction concurrente, stock/capacité exacts et rollback |
| Temps | due_at exact, worker tardif/hors connexion, lecture paresseuse, fin vs commande, enfant activé à date logique, crash avant/après commit, tête blocked et reprise |
| Scopes/droits | Autre Empire/autre Universe, deux participants même Empire, lecture sans mutation, start ≠ cancel, colonie payeuse étrangère/invisible, aucune autorité admin implicite |
| Sessions | Absente/expirée/révoquée/suspendue, révocation concurrente, aucune activité des lectures/timers, aucun report de l’absolu ou valid_until, worker sans utilisateur connecté |
| Données | Pré-requis inconnus/cycles, effets non supportés, doublons, versions mixtes, coûts/durées invalides/overflow, v0.1 inchangée et pas de migration silencieuse des univers |
| UI | Acquis/active/suivante/effets réels, coûts/durée/prérequis/financement avant confirmation, annulation complète, erreurs sans fuite, retry même intention, quatre largeurs/clavier et état vide authentique |

R08 : projet Compose aléatoire, bases strictement *_test, provisionnement et droits par le vrai
contrôle privé, recherche par HTTP réel sous HTTPS et worker réel sans page. Montrer une conséquence
réelle (quote de construction/recherche modifiée selon Q05) puis l’activation de la suivante.
Arrêter Portal API/contrôle : lecture, lancement et fin autorisés dans les bornes de la GameSession,
zéro appel gameplay Portal ; échéance atteinte = refus. Préserver les volumes conservés et secrets.

## Validation et checkpoint de sortie futurs

Game complet PostgreSQL, frontend Game lint/tests/build et Chromium, Alembic check/roundtrip,
checks docs/diff et smokes Game/Portal/contrôle/handoff/Colony/Research selon les domaines affectés.
L’extension des permissions/contrats 5C implique suites et smokes Portal/control/handoff ; la nouvelle
quote Colony implique ses tests/smoke Q39. CI complète du SHA final, puis description PR/checkpoint
réels, limites/anomalies et Ready for review si prêt, **sans merge**. Ne pas transformer une CI
verte documentaire en validation de Research inexistante.

## Hors lot

Génération galaxie, exploration, vue système, flottes, colonisation, IA, combat, diplomatie, défense,
multijoueur complet, modes PRIVATE/PERSISTENT, laboratoires, portefeuille global, création complète
de partie produit, production continue modifiée par Research et étape 7. Aucun abonnement/service
payant ou nouvel arbitrage Qxx pris pour faciliter le développement. Prochain échange demandé : Q05.
