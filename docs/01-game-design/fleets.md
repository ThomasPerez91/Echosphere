# Flottes et missions

**Statut : Q09 ouverte ; proposition F01 du 31/10/2026 ci-dessous, en attente de validation utilisateur.**
Rien de cette proposition n’est implémenté ni validé ; aucun schéma, migration ou ruleset v0.4 avant arbitrage.


Peu de classes au MVP. Rôles envisagés : sonde, transport léger, transport lourd, unité légère de
combat, escorte, unité lourde, colonisateur. Noms, statistiques et nombre final restent Q09.
Pas d'éditeur complexe de vaisseaux.

Missions envisagées : déployer, explorer, transporter, coloniser, attaquer, revenir. Chacune a une
destination, une échéance et un état serveur. La liste ne spécifie pas encore les règles de retour.

## Invariants proposés pour la conception

Une unité ne peut être engagée simultanément dans deux missions. Les routes sont validées sur le
graphe et selon les informations disponibles. Le commandement vérifie les coûts et la disponibilité
avant de réserver les unités. Les résultats sont traçables dans les rapports.

## Questions avant l'étape 9

Vitesses, trajet multi-sauts, capacité cargo, consommation de Flux, rappel, fusion/division, passage
en territoire étranger et visibilité restent Q09. Les timestamps remplacent toute simulation
continue de déplacement. Le client anime une projection et ne décide pas des arrivées.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Proposition Q09 — F01, 31/10/2026, en attente de validation

Provenance : instruction utilisateur du 31/10/2026 (étape 9, F00/F01 puis arrêt avant F02).
Valeurs chiffrées = **balance provisoire** destinée au futur ruleset v0.4, jamais des constantes de
service. Les sections « Recommandation » sont des choix proposés ; les arbitrages à trancher sont
listés à la fin. Audit du code et plan technique : [plan étape 9](../05-project/step-9-plan.md).

### Principe directeur

La vraie boucle jouable de l’étape 9, avec **une seule colonie par Empire** tant que l’étape 10
n’existe pas : produire des vaisseaux → les grouper → explorer avec une sonde (nouveaux univers) →
se déployer sur un système connu → revenir ou être rappelé. Le cargo et le transport sont définis
complètement mais ne deviennent utiles entre colonies qu’avec l’étape 10 (voir arbitrage A9).
Aucune présence étrangère, capteur, combat, colonisation ou IA.

### Catalogue MVP proposé : deux classes

| Classe (id) | Rôle | Coût | Durée unitaire | Temps/saut | Flux/saut | Cargo |
| --- | --- | --- | --- | --- | --- | --- |
| Sonde (`probe`) | Cartographie d’un système DETECTED (mission SURVEY), reconnaissance | 80 A / 40 F / 40 D | 20 min | 10 min | 4 | 0 |
| Cargo léger (`freighter`) | Transport de ressources entre colonies propres | 200 A / 60 F / 20 D | 40 min | 20 min | 8 | 500 |

Cargo exprimé en unités de ressource (500 = 500 000 000 micro-unités), toutes ressources confondues.
Repères : stocks initiaux 2 000/1 500/750 et production initiale 120/100/60 par heure ; une
expédition abstraite v0.3 à un saut coûte 50 A / 60 F / 25 D et dure 45 min, une sonde est donc un
investissement réutilisable amorti en deux ou trois cartographies. Aucune unité n’a de valeur
militaire : pas d’attaque, coque, armement, bouclier ou point de vie.

**Différés et pourquoi.** Colonisateur → étape 10, ses coûts/devenir dépendent de Q07 ; unités de
combat légère, escorte et lourde → étape 12, sans règle Q10 elles n’auraient aucun effet ; transport
lourd → inutile tant que les volumes restent faibles. Ajouter une classe plus tard = nouveau
ruleset, sans migration des unités existantes. Aucun champ de combat ajouté maintenant : un futur
état de dommage pourra s’ajouter par stack sans contredire ce modèle.

### Production des unités

| Sujet | Recommandation |
| --- | --- |
| Lieu | Depuis une colonie propre explicite, choisie comme source |
| Infrastructure requise | Aucune à l’étape 9 : pas de chantier naval implicite ni de slot orbital consommé ; un futur chantier orbital relève de Q04 et d’un nouveau ruleset |
| File | File de production **dédiée** par colonie, distincte de la construction (pas de concurrence avec les infrastructures) |
| Parallélisme | 3 ordres par colonie dont 1 actif, comme Q01 ; colonies indépendantes |
| Quantité | Un ordre = une classe et une quantité 1–20 ; l’ordre entier se termine à `quantité × durée unitaire` |
| Réservation | Coût total débité à l’acceptation (réservation immédiate), aucun débit à la fin |
| Annulation | Possible ; théorique 100 % en attente / 80 % actif ; crédit plafonné par ressource avec perte annoncée (politique Q39 **reprise explicitement**, preview obligatoire) |
| Sortie | Les unités terminées rejoignent la **garnison** de la colonie source (voir composition) |
| Stationnement | Aucune limite de stationnement ni entretien à l’étape 9 (Q03 entretien reste ouvert) |
| Bonus | Aucun bonus industriel/Research implicite ; vitesse univers `speeds.fleet` déjà réservée appliquée aux durées |

### Composition et stationnement

Une Fleet est un groupe d’unités comptées par classe (stacks), hétérogène autorisé, au moins une
unité, sans plafond autre que les bornes entières. Elle est soit **STATIONED** dans un système connu
de son Empire, soit **MOVING** dans une seule mission active.

- **Garnison** : une Fleet par colonie, créée à la première production, toujours stationnée dans le
  système de sa colonie ; elle ne part jamais elle-même.
- **Flotte opérationnelle** : créée au lancement d’une mission en prélevant une composition choisie
  sur une flotte stationnée (division implicite au lancement). Elle reste ensuite persistante et
  peut enchaîner des missions depuis le système où elle stationne.
- **Division** : uniquement entre flottes stationnées, au même système. **Fusion** : uniquement de
  flottes stationnées au même système (y compris vers la garnison). Aucune modification en vol.
- Lien de lieu : système (pas planète). Une flotte stationnée dans un système contenant une colonie
  propre peut charger/décharger avec cette colonie ; ailleurs, elle stationne sans interaction.

**Invariant** : une unité appartient à exactement un stack d’une seule Fleet ; une Fleet a au plus
une mission ouverte ; stacks et cargo ne changent que lorsque la flotte est stationnée. Une même
unité ne peut donc jamais appartenir à deux missions (garanti en base, voir plan technique).

### Missions livrées à l’étape 9

| Mission | Destination | Effet à l’échéance |
| --- | --- | --- |
| DEPLOY | Système MAPPED/MONITORED | La flotte stationne à destination, cargo conservé |
| SURVEY (v0.4) | Système DETECTED ; flotte composée **uniquement de sondes** | Arrivée + étude, cartographie comme Exploration (même fusion de connaissance), rapport immuable, la flotte stationne sur place |
| RETURN | Système de la colonie d’attache de la flotte | La flotte stationne chez elle ; fusion dans la garnison sur commande explicite |

Transport = **commandes distinctes et explicites**, pas une mission ambiguë : CHARGER à la colonie
d’origine (débit), DEPLOY vers le système d’une autre colonie propre, puis DÉCHARGER (crédit).
COLONIZE (étape 10) et ATTACK (étape 12) restent **absents**, pas des types factices.

### Trajets et Fog

- Destination DEPLOY/RETURN : MAPPED ou MONITORED. SURVEY : DETECTED. UNKNOWN refusé comme absent.
- Uniquement routes connues de l’Empire, tous les systèmes intermédiaires MAPPED/MONITORED (règle
  Exploration étape 7 reprise). Multi-sauts autorisés.
- Le serveur calcule le plus court chemin (sauts) avec départage stable ; le client ne choisit ni
  chemin ni durée. Devis affiché, recalculé sous verrou à l’acceptation.
- Chemin, composition, cargo, règles et coûts **snapshotés** à l’acceptation ; une connaissance
  acquise après le départ ne modifie pas le trajet. Les routes générées sont immuables aujourd’hui ;
  une future règle qui les modifierait garderait le trajet snapshoté jusqu’à l’arrivée.
- Flottes visibles uniquement par leur Empire. Aucune flotte étrangère, signature, contact,
  détection ou espionnage. **Une flotte stationnée ne rend pas un système MONITORED** à l’étape 9
  (pas de capteur implicite ; Q08 inchangée).

### Vitesse

`durée = sauts × max(temps_par_saut des classes présentes) ÷ speeds.fleet` (+ `survey_seconds` pour
SURVEY, 15 min proposé). La flotte va au rythme de sa classe la plus lente ; chaque saut a la même
durée quelle que soit la longueur visuelle de la route (aucun rôle des positions 2D). Vitesse
univers 1x ; aucun bonus Research maintenant (une future technologie de propulsion exigera un
nouveau ruleset). Route + composition + règles snapshotées → `arrival_at` déterministe, jamais recalculé.

### Carburant (Flux)

`Flux = sauts × Σ(nombre × Flux/saut de la classe)`, plus pour SURVEY un coût d’analyse fixe de
20 Données. Payé **en une fois au départ** par une colonie propre explicitement choisie (comme les
sources Exploration/Research ; abstraction assumée pour une flotte éloignée). Aller seul : RETURN
ou un nouveau DEPLOY paient leur propre trajet. Aucun débit à l’arrivée, aucune consommation
continue, aucun remboursement au rappel. Refus si stock insuffisant ; débit atomique avec la mission.

### Cargo et transport

- Seule la classe `freighter` porte du cargo : capacité = Σ(nombre × 500), toutes ressources
  confondues, micro-unités entières, aucun dépassement.
- CHARGER : flotte stationnée dans le système d’une colonie propre ; débit de cette colonie après
  rattrapage, refus si stock ou capacité insuffisants.
- DÉCHARGER : crédit par ressource **jusqu’à la capacité libre** de la colonie ; **l’excédent reste à
  bord**, sans perte (différent de Q39 : le cargo peut attendre). Preview avant confirmation.
- Le cargo voyage avec DEPLOY/RETURN et est conservé au rappel ; il n’est jamais crédité
  automatiquement à l’arrivée (voir verrous : pas de second stream dans un handler).

### Rappel

Autorisé pour DEPLOY et SURVEY tant que `now < arrival_at` (après rattrapage) ; refusé ensuite.
Retour **symétrique en temps**, sans position intermédiaire ni téléport :
`return_at = recalled_at + (recalled_at − started_at)`, vers le système de départ de la mission.
Aucun Flux supplémentaire ni remboursé, cargo conservé, étude non réalisée. L’événement d’arrivée
initial est acquitté `cancelled` (comme l’annulation de construction) et un `FLEET_RETURN` est
planifié avec une clé dérivée de la mission : rappel rejoué = même résultat. Un retour ou un RETURN
ne peut pas être rappelé.

### Exploration abstraite et vraies flottes — recommandation C

- Univers **v0.3** : `abstract-expedition-v1` inchangée (missions, rapports, coûts, capacité) ; aucune
  flotte, aucune migration, aucune conversion de mission.
- Nouveaux univers **v0.4** : l’exploration passe par SURVEY d’une flotte de sondes
  (`fleet-survey-v1`) ; la capacité abstraite n’existe pas dans ce ruleset (un seul moyen
  d’explorer par ruleset). Même connaissance, même fusion monotone, même règle de destination.
- Écartées : A (coexistence dans v0.4 → deux économies d’exploration redondantes à équilibrer) ;
  B appliquée aux univers existants (violerait l’immuabilité des rulesets/snapshots).

### Colonisation et combat futurs

L’étape 10 pourra ajouter une classe colonisateur et une mission COLONIZE dans un nouveau ruleset,
réutilisant flotte, trajet, snapshot et événement d’arrivée ; l’étape 9 ne crée jamais de colonie,
ne réserve aucune planète et ne résout aucune concurrence. L’étape 12 ajoutera classes militaires,
état de dommage et résolution Q10 ; aucun champ, cible, dommage, défense ou rapport militaire maintenant.

### Arbitrages à valider

| ID | Décision proposée |
| --- | --- |
| A1 | Catalogue limité à `probe` et `freighter`, chiffres provisoires ci-dessus |
| A2 | File de production dédiée par colonie (3/1, quantité 1–20, réservation immédiate), sans infrastructure requise ni slot orbital ; annulation 100/80 avec crédit plafonné Q39 explicite |
| A3 | Garnison par colonie + flottes opérationnelles ; division au lancement ou à l’arrêt, fusion à l’arrêt, rien en vol |
| A4 | Missions DEPLOY, SURVEY (sondes seules, v0.4), RETURN ; transport par CHARGER/DÉCHARGER explicites ; COLONIZE/ATTACK absents |
| A5 | Destinations et chemins : règle Exploration reprise, chemin serveur snapshoté |
| A6 | Vitesse : classe la plus lente, temps constant par saut, `speeds.fleet`, aucun bonus |
| A7 | Carburant Flux par unité et par saut + 20 Données pour SURVEY, payé au départ par une colonie choisie, sans remboursement |
| A8 | Déchargement plafonné sans perte, excédent conservé à bord ; aucun crédit automatique à l’arrivée |
| A9 | Livrer cargo/transport dès l’étape 9 bien qu’une seule colonie existe en jeu (recette avec seconde colonie de test, comme les fixtures existantes) — **ou** le reporter à l’étape 10 |
| A10 | Rappel symétrique en temps avant `arrival_at`, sans coût ni remboursement |
| A11 | Flottes propres seules visibles ; une flotte stationnée ne fournit aucune surveillance |
| A12 | Transition Exploration option C : v0.3 inchangé, v0.4 SURVEY par sondes seulement |
| A13 | Un seul EventStream « opérations d’Empire » = stream Exploration existant, pour toutes les flottes et la production (voir plan) |
| A14 | Permissions `fleet.read`, `fleet.build`, `fleet.command` (plafond du contrat porté de 9 à 12, aucune attribution automatique) |
| A15 | Ruleset complet v0.4 pour les nouveaux univers seulement, aucune flotte de départ gratuite |
