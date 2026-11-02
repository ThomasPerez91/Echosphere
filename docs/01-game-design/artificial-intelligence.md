# Civilisations IA

**Statut : Orientation validée — Utility/Goals, équité et testabilité ; moteur non implémenté.**


L'IA est un acteur économique et stratégique autonome : elle explore, construit, recherche,
colonise et déplace ses flottes. Elle combat selon les règles communes. Commerce et négociation
avancés se développeront après le MVP ; des relations minimales sont prévues à l'étape 13.

## Moteur initial

Pas de LLM. Orientation : Utility AI / Goal-based AI déterministe et testable. Trois profils simples
peuvent suffire : expansionniste, économique/prudent, agressif. Paramètres envisagés : aggression,
expansion, economy, research, risk, diplomacy. Coefficients et cadence restent Q11.

## Équité vérifiable

Un humain et une IA demandent la même commande métier, par exemple un futur
`StartConstructionCommand`. Aucun crédit de ressources ni création d'unités réservé aux bots.
Les IA disposent d'une connaissance limitée et ne consultent pas le monde complet pour décider.
Le budget d'analyse peut différer mais pas les coûts, prérequis ou conditions de possession.

## Observabilité future

Enregistrer objectif, candidats accessibles, score et raison du choix sans exposer les secrets aux
joueurs. Rejouer une décision sur état figé. Les conditions de départ équitables restent Q11 ;
aucun handicap caché ne doit être ajouté au motif de rendre une partie plus difficile.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Vision consolidée — orientation validée, future

Perception → Goals → Evaluation → Decision → Action. La perception vient seulement des projections
accessibles au même empire humain. L’IA peut faire de mauvaises décisions ; elle n’a ni moyens
créés gratuitement ni connaissance compensatoire pour gagner. Profils possibles : expansionist,
economic/cautious, aggressive ; traits aggression/expansion/economy/research/risk/diplomacy proposés,
poids et cadence Q11. Un dialogue génératif éventuel est une couche future facultative, jamais
l’autorité stratégique ou le service validant une commande. Aucun LLM requis au moteur stratégique.
Diplomatie/commerce avancés restent post-MVP, mécanismes non décidés ; Q18 concerne les relations minimales.

## Q11 — proposition AI01 du 01/11/2026, non validée

**Proposition uniquement. Q11 reste ouverte ; aucun code IA engageant n'est autorisé par ce texte.**
Audit du code intégré `a33a452` et architecture conditionnelle : [moteur IA](../03-technical/ai-engine.md#ai01--audit-du-code-intégré).
[Plan AI02–AI11](../05-project/step-11-plan.md). La validation doit porter sur les choix A1–A10
ci-dessous ; les valeurs numériques sont une première balance à mesurer, pas un résultat de simulation.

### Périmètre utile avant Combat

La première IA développe ses colonies, choisit ses recherches, fabrique ses unités, explore par
SURVEY et fonde de vraies colonies par COLONIZE. Le transport ne sert que ses colonies et ses
paquets de fondation. Elle peut attendre : une action inutile n'est jamais obligatoire.
Aucun ennemi connu n'existe encore dans ses projections ; elle ne sait donc ni attaquer, ni choisir
une cible militaire, ni réagir à une flotte étrangère. Le profil « agressif » est reporté à Q10/
Combat : lui donner maintenant un poids militaire serait un faux comportement. Q18 reste distincte.

### Profils et choix proposés

Deux profils suffisent pour vérifier des trajectoires différentes sans inventer le Combat.
Poids entiers, somme 100 par profil ; ils changent les priorités, jamais coûts, stocks ou délais.

| Profil | Économie | Recherche | Exploration | Expansion | Logistique propre |
| --- | ---: | ---: | ---: | ---: | ---: |
| economic_cautious | 45 | 20 | 20 | 10 | 5 |
| expansionist | 25 | 15 | 20 | 35 | 5 |

Choix **explicite par Empire au provisionnement**, enregistré et immuable pendant la première
partie ; aucun tirage caché ni adaptation à la performance du joueur. Référence solo proposée :
1 humain + 2 IA, une de chaque profil ; 0–3 IA configurables avant démarrage (4 sites candidats
maximum aujourd'hui). Pas de conversion d'Empire humain, takeover, changement de profil ou
apparition tardive dans ce lot. Un seul profil économique réduit le travail mais ne prouve pas
l'effet des profils ; trois profils incluant « agressif » prépareraient un domaine absent.

### Objectifs, prudence et choix explicables

Une intention d'expansion peut demander plusieurs décisions : produire un colonisateur, attendre,
isoler cette unité si nécessaire, charger le paquet, puis COLONIZE. Chaque étape passe par une
commande ordinaire ; aucune macro ne fabrique/charge/lance gratuitement en une décision.
Un rapport `target_unavailable` ne révèle pas son occupant : mémoriser seulement l'échec propre
sur cette cible, sans chercher la cause cachée ; ne pas retenter cette planète pendant ce lot
(sans abandon/transfert, une réévaluation demanderait une future règle d'information).

Priorité de survie économique commune aux deux profils : une colonie fondée sans revenu construit
d'abord un producteur d'Alliages, puis de Flux, puis de Données si absents, en tenant compte des
ordres déjà engagés. Ni Industry ni Research avant ce démarrage local ; sinon le paquet minimum
peut être dépensé sans moyen de relancer l'économie. Aucun producteur ou ravitaillement offert.

Pour les autres choix, comparer seulement des candidats connus et légalement accessibles.
Les besoins (production/stockage, place de file, recherche, frontière DETECTED, projet d'expansion,
cargo utile) donnent une utilité entière bornée de 0 à 1000. Score = poids du profil × utilité ;
départage par coût serveur (tuple Alliages/Flux/Données), durée puis clé stable de l'action. Les fonctions de besoin et leur
normalisation seront explicites et versionnées avec tests à AI02/AI06 ; aucun float, réseau,
horloge cachée, ordre SQL ou connaissance étrangère dans le décideur. Une action préparatoire
hérite de l'objectif de son projet, pour éviter que la logistique ne perde toujours contre un upgrade.

Prudence proposée : hors bootstrap/ravitaillement, conserver dans la colonie payeuse de quoi
commander un producteur de niveau 1 de chaque ressource. Réserve calculée avec les devis actuels
communs, pas une ressource bloquée en DB. Elle est une politique IA, jamais un nouveau refus pour
les humains. La priorité bootstrap peut utiliser cette réserve. Une production/mission déjà
engagée compte dans le besoin : pas d'achat infini de sondes ou de colonisateurs en attente.
Ne pas annuler automatiquement des ordres ni rappeler une mission dans cette première politique ;
ces commandes existent mais exigeraient un objectif de risque observable absent aujourd'hui.

### Cadence et budgets proposés

- Une décision toutes les **10 minutes UTC serveur**, même cadence pour les deux profils ;
  **au plus une commande acceptée par décision** (ou WAIT). Pas de réaction instantanée à chaque
  fin d'ordre ni de cycle lié à une lecture/page ouverte. Après refus métier : attente de la
  prochaine échéance, aucune boucle d'essais sur d'autres cibles.
- Après panne : une décision sur l'état actuel, pas une rafale rétroactive de tous les tours
  manqués. Les productions/arrivées déjà acceptées se rattrapent intégralement par le moteur
  commun ; l'IA ne commande jamais dans le passé avec des informations acquises ensuite.
- **128 candidats maximum par décision**, quotas/fonctions de parcours stables et versionnés ;
  **64 flottes propres maximum observées par tour**, avec pagination/cursor persisté équitable.
  Tous les mondes connus du profil actuel (50 systèmes, au plus 250 mondes) restent accessibles,
  ainsi que les 12 colonies maximum autorisées par v0.5. Aucune recherche arborescente illimitée.
  Ces bornes limitent l'analyse IA, pas les droits ou plafonds de possessions des humains.
- Budget économique = **stocks réels disponibles** et réserve ci-dessus ; aucun crédit par tour,
  réduction de coût, spawn, vaisseau de secours, technologie ou cap de file spécifique.
- Garde-fous techniques proposés : délai transactionnel 2 s, attente de verrou 500 ms ; dépassement
  annule atomiquement le tour, jamais choix différent sur un sous-ensemble aléatoire. Retry
  technique 30 s, 3 échecs puis pause opérateur persistée ; limites séparées des refus métier.
  Objectif de calcul pur p95 <50 ms pour 128 candidats, à mesurer, pas une capacité démontrée.

### Départs et activation

Créer humain et IA à la même date de départ sur des sites candidats distincts, avant toute
commande. Même colonie de référence (12/2, mêmes stocks/infrastructures), mêmes vitesses et
connaissance initiale locale ; aucune flotte/colonie additionnelle gratuite pour l'IA. Les sites
sont comparables selon le générateur, pas identiques ; aucune connaissance globale fournie au décideur.
L'initialisation de départ commune n'est pas un spawn stratégique après démarrage.

Recommandation : ruleset **v0.6 complet**, copie économique de v0.5 + configuration IA validée,
pour de **nouveaux univers explicitement initialisés seulement**. v0.1–v0.5 et leurs snapshots
restent inchangés ; aucun bot activé à la lecture ou au redémarrage d'une ancienne partie.
Pas de nouveau parcours Portal créer/rejoindre. Un service de bootstrap Game et une commande
opérateur explicite suffisent au lot ; aucune identité humaine factice pour entrer en jeu.
La commande refuse monde occupé, sites insuffisants ou adoption partielle ambiguë, sans effacer
l'existant. La recette utilisera exclusivement un projet et des bases *_test.

### Arbitrages demandés avant AI02

| ID | Recommandation à valider |
| --- | --- |
| A1 | Développement, Research, SURVEY, COLONIZE et transport propre ; aucun Combat/relations ni profil agressif |
| A2 | Deux profils et poids du tableau ; choix explicite au départ, profil figé pour ce premier lot |
| A3 | Solo de référence 1 humain + 2 IA ; configurable 0–3 IA à la création, pas d'ajout/reprise d'Empire tardifs |
| A4 | Départs équitables simultanés par initialiseur commun ; aucune flotte ou aide économique propre aux IA |
| A5 | Décision toutes les 10 minutes, une commande maximum ou WAIT ; pas de rattrapage rétroactif des décisions manquées |
| A6 | 128 candidats, 64 flottes paginées, entiers/départage stable ; budgets techniques séparés et mesurés |
| A7 | Bootstrap économique prioritaire, réserve de prudence commune et projets d'expansion multi-décisions ; aucune annulation/rappel automatique |
| A8 | Échec COLONIZE : mémoriser l'indisponibilité observée et exclure la cible sans en déduire l'occupant |
| A9 | Nouveau v0.6 et activation explicite nouveaux univers ; pas d'adoption silencieuse ni refonte Portal/modes |
| A10 | Traces privées rejouables, pause/reprise opérateur et critères de preuve du plan ; aucune garantie de victoire ou d'équilibrage |

Une validation Q11 ne vaut pas autorisation de merge. AI02–AI11 restent conditionnels à une
instruction explicite ; ce document ne contient aucun profil exécutable.

## Q11 — validation avec amendements, 01/11/2026

**Q11 close pour l'étape 11, validation utilisateur explicite.** AI02–AI11 autorisés sans
validation intermédiaire sauf nouvelle décision produit. Les deux CI AI01, push 41343195071 et
PR 41343200391 sur f4a14d9, ont été vérifiées success 5/5 avant AI02. La proposition AI01 reste
historique ; les précisions ci-dessous priment. Aucun merge ou Combat autorisé.

- A1–A10 validés : profils et poids du tableau, choix explicite figé, départ équitable, bootstrap
  de référence 1 humain + 2 IA (economic_cautious/expansionist), 0–3 IA supportées par ce bootstrap
  seulement, sans en faire un plafond produit général. Sites en ordre canonique, indépendamment
  du profil et de leur qualité. Insuffisance de sites = refus, jamais génération compensatoire.
- Empire IA exclusif : activation refusée avec binding humain ; aucun grant humain tant qu'un
  contrôleur est actif. Aucun binding supprimé implicitement. controller_type descriptif ne
  suffit pas : AIController persistant Universe/Empire/profil/policy/état est la racine de confiance.
  Aucun Account/User/Membership/session/ticket/cookie IA, aucune permission Portal ai.*.
- Décideur pur → dispatcher limité → services communs ; pas d'exécuteur générique ni d'identité
  arbitraire fournie par le décideur. Capabilities read/construct, research read/start, galaxy
  read, fleet read/build/command, colony.expand ; aucune annulation ni rappel automatique.
- Grille de 600 s ancrée au départ, prochaine échéance = premier créneau strictement futur ;
  une commande maximum ou WAIT/refus par tour. Après panne, état actuel et un seul nouveau tour,
  aucun rattrapage stratégique. Projets multi-tours sans réservation, revalidés et abandonnables.
- 128 candidats maximum, pages flottes ≤64, bornes avant matérialisation/produit cartésien.
  Chaque famille paginée a ordre canonique, curseur persistant et parcours circulaire : une option
  continuellement éligible est examinée au plus en ceil(M/P) visites. Test anti-famine obligatoire.
- Bootstrap Colony : Alliages puis Flux puis Données, compte tenu des ordres déjà engagés et
  stocks réels. Réserve seulement décisionnelle, aucune ressource bloquée. Faute de moyens :
  attendre ou transport légitime. Échec COLONIZE mémorisé seulement planet_id/observed_at/reason
  target_unavailable, sans cause ni identité étrangère et sans partage de Knowledge.
- Utilité entière 0..1000, poids × utilité ; aucun hasard/float. Égalité : coût lexical
  (Alliages, Flux, Données), durée, clé stable. Rejeu = observation/mémoire/profil/policy/date
  identiques, pas seed seule ; manifester les identités dans les scénarios multi-bases.
- v0.6 complet = v0.5 + ai.json strict (policy, profils, cadence, budgets, normalisations).
  Données immuables épinglées ; charger v0.6 ne crée/active aucun contrôleur. v0.1–v0.5 inchangés,
  aucun backfill ou adoption. Vrai bootstrap opérateur transactionnel, aucun import *_test runtime.
- Orchestrateur Game dédié hors handler TimeEngine ; next_decision_at durable. Locks contrôleur
  → opérations → Research → colonies existantes triées ; inclure toute Colony créée pendant le
  catch-up avant observation. Aucun stream étranger ni inversion Planet→stream amont.
- Effet, séquence, trace, mémoire/intention et prochain rendez-vous atomiques. Clé stable
  contrôleur+séquence+action, même clé sur retry. Refus métier tracé puis prochain créneau sans
  autre essai ; erreur technique rollback intégral, retry borné puis blocked opérateur.
- enabled/paused/blocked explicites ; pause empêche les nouveaux tours, jamais les achèvements
  acceptés. Reprise sur état courant sans tours antidatés. Portal indisponible/session humaine
  expirée n'arrêtent ni IA ni événements acceptés.
- Traces privées : observation canonique/version, buts/candidats réellement évalués, scores,
  raisons/départage/intention/résultat et budgets/curseurs, y compris WAIT. Pas d'API publique.
  Rétention 100 tours, observation 256 KiB et candidats/résultat 64 KiB initiaux ; dépassement
  avant commande, jamais troncature cachée. Timeouts/retries/tailles techniques ajustables sur
  mesures, bornés et documentés, pas règles produit immuables.
- Sortie : variation des données cachées → même observation/décision ; profils réellement
  divergents ; autonomie économique complète jusque Colony fondée puis producteurs, via services
  communs uniquement. Recette page fermée/Portal coupé, redémarrage et session humaine expirée.
  Horloge injectée/cadence de test explicites possibles ; aucune aide après départ.
- Avant Ready : suites/DB/concurrence/crash/fog/autonomie/Alembic/smokes/docs/CI exacte ; puis
  attendre la revue automatique Codex et traiter les fils, zéro non résolu. Aucun merge implicite.

## Diplomatie — étape 13 et 13B

Policy v3 (Q18 close pour l'étape 13) : famille `diplomacy`, réponses prioritaires, aucune offensive
ni rupture de pacte. [Décisions et poids](relations.md#q18--validation-avec-amendements-02112026).
Protocoles frontaliers (13B, ruleset v0.9 seulement) : policy v4 validée le 02/11/2026, voir
[B08](first-contact.md#b08--politique-ia-validée-le-02112026). v0.6–v0.8 inchangées.
