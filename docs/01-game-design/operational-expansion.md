# Expansion opérationnelle, exploitation galactique et guerre de mouvement

**Statut : orientation produit pré-MVP validée par l’utilisateur le 09/11/2026 (Q62), arbitrages tranchés le même jour (§9) ; ce document
est la référence canonique du chantier EXP.** Provenance : instruction utilisateur du 09/11/2026
(« nouveau gameplay d’expansion galactique, contrôle opérationnel et guerre de mouvement »), qui
répond aussi aux « zones d’influence » laissées en attente en Q61. Les orientations 1–12 de cette
instruction sont validées ; les règles détaillées ci-dessous sont des **propositions de
conception** (EXP-00) tant qu’elles ne sont pas marquées validées ; les valeurs chiffrées sont une
**balance provisoire** versionnée dans `game_data` (ruleset v0.10 et suivants). Plan technique :
[plan EXP](../05-project/exp-plan.md).

Principe : **un Empire ne possède pas l’espace ; il le maîtrise par ses activités, ses flottes et
ses moyens réels.** Ni station obligatoire, ni monnaie d’influence, ni annexion, ni frontière figée,
ni quatrième ressource. Les flottes deviennent le moyen principal de maîtriser une région.

## 1. Trois notions distinctes (validé)

| Notion | Ce que c’est | Source de vérité | Persistant ? |
| --- | --- | --- | --- |
| **Connaissance** | Ce que l’Empire sait : UNKNOWN / DETECTED / MAPPED / MONITORED ([Fog](fog-of-war.md)) | `system_knowledge` et connaissances d’opportunités | Oui, datée |
| **Présence opérationnelle** | Ce que l’Empire fait réellement dans un système : transit, stationnement, prospection, exploitation, étude, patrouille, escorte | Missions et flottes actives | Non : dérivée de l’état courant, disparaît avec les moyens |
| **Capacité de contrôle** | Possibilité effective de détecter, surveiller, intercepter | Flottes réellement présentes, protocoles 13B, niveaux de détection | Non : évaluée à la date logique d’un passage |

Un système sans colonie n’a **aucun propriétaire**. Plusieurs Empires peuvent le connaître, le
traverser, y stationner, l’exploiter, l’étudier et s’y affronter. Les colonies restent des
possessions de leur planète. Cartographier ne donne jamais de contrôle militaire.

La « zone d’influence » de Q61 est une **représentation** de la présence opérationnelle (vue
« Présence stratégique », EXP-06), jamais une propriété ni une règle d’exclusion.

## 2. Opportunités galactiques (EXP-01)

Générées de façon déterministe avec la galaxie, par un générateur versionné (`opportunities-v1`)
appliqué au monde déjà généré : le monde `galaxy-v1` (systèmes, routes, planètes, départs) et son
empreinte ne changent pas. Paramètres dans `game_data` (`opportunities.json`, ruleset v0.10+).
Les univers v0.1–v0.9 n’ont aucune opportunité.

| Famille | Exemples (types v0.10) | Ce qu’elle apporte | Ressource |
| --- | --- | --- | --- |
| **Gisement** (`deposit`) | ceinture métallique, nuage de flux, cristaux mémoriels | Une **réserve finie** extraite par des flottes (EXP-02), à un **débit plafonné** par système | Alliages / Flux / Données selon le type |
| **Curiosité** (`curiosity`) | anomalie, épave ancienne, structure inconnue, signal artificiel | Une **étude** unique par Empire : gain ponctuel de Données, éventuel **indice** de dossier | Données |
| **Intérêt stratégique** | carrefour (≥ 4 routes), passage obligé vers une région | Valeur de position, **calculée** depuis les routes connues, jamais un bonus stocké | — |
| **Planète remarquable** | traits de planète | Reporté : règles explicites compatibles Q04, lot ultérieur | — |

Distribution (provisoire, v0.10) : environ la moitié des systèmes ordinaires, la plupart des
autres avec une opportunité, quelques-uns avec deux ou trois ; une petite part de rang
**remarquable** (réserve et gains multipliés), plafonnée par carte, jamais dans un système de départ
ni à moins de deux sauts d’un départ ; chaque zone de départ (rayon 2) contient au moins un gisement
ordinaire. Une réserve finie et un débit plafonné empêchent qu’une poignée de systèmes garantisse
la victoire.

**Dossiers de découverte** : quelques ensembles de 3 indices répartis dans des curiosités de
systèmes distincts ; l’Empire qui a étudié tous les indices d’un dossier obtient une découverte
majeure (gain de Données important ; effets supplémentaires = arbitrage A4).

**Découverte progressive** (Fog) : cartographier un système révèle seulement le **nombre de
signatures inexpliquées** ; la mission **Prospection** révèle type, rang et valeurs connues de
chaque opportunité, dans un rapport daté et persistant. La connaissance d’une réserve est datée :
l’épuisement par d’autres n’est vu qu’à une nouvelle observation (MONITORED ou nouvelle prospection).

## 3. Exploitation sans colonisation (EXP-02)

Missions du moteur Flottes existant (mêmes snapshots, clés d’idempotence, événements datés, rappel
symétrique, déchargement plafonné sans perte) :

| Mission | Flotte | Effet |
| --- | --- | --- |
| **PROSPECT** | au moins une sonde | Arrivée + étude ; révèle les opportunités du système ; rapport ; la flotte stationne |
| **EXTRACT** | au moins un extracteur, cargo disponible | Arrivée, puis extraction pendant une durée choisie ; arrête à la durée, cargo plein, réserve épuisée ou rappel ; puis reste ou rentre (choix au lancement) ; décharge normale dans une colonie propre |
| **STUDY** | sonde ou extracteur, soute libre ≥ Données | Étude d’une curiosité prospectée, une fois par Empire ; Données chargées dans la soute de la flotte (précision technique EXP-02a : un handler d’opérations ne touche pas une Colony), déchargées normalement dans une colonie (plafond Q39) ; indice de dossier |

- Nouvelle classe **Extracteur** (v0.10, provisoire) : débit par heure, cargo propre, pas de valeur
  militaire (civil : jamais détruit, D5).
- **Investissement réel** : construction des extracteurs, immobilisation, carburant aller-retour,
  durée, capacité cargo, retour pour décharger ; aucune production infinie depuis une installation
  abstraite.
- **Concurrence (règle proposée A3)** : chaque gisement a un débit maximal par heure. Si la demande
  des opérations simultanées (tous Empires) dépasse ce débit, il est **partagé au prorata des
  extracteurs** engagés ; la réserve diminue de la somme extraite. Aucun premier arrivé
  propriétaire. Règlement exact par intervalles entre départs/arrivées d’opérations, sous verrou du
  gisement, en micro-unités entières, reste persisté.
- Présence hostile : voir arbitrage A1 (une flotte civile n’est jamais détruite ; la protection
  vient de l’escorte et des protocoles 13B).

Équilibre visé : colonies = production permanente ; expéditions = gains ponctuels importants mais
coûteux ; flottes militaires = sécurité. Un Empire peu colonisateur mais bon explorateur doit
rester compétitif (simulations EXP-07).

## 4. Contrôle opérationnel (EXP-03)

Réutilise 13B sans second moteur : stationnement à protocole (SURVEILLANCE, AMBUSH, INTERCEPTION,
FRIENDLY_CONTACT), détection au passage réel (D2), information D3, pacte prioritaire, pertes
militaires seules.

- **Garde / escorte** : une flotte militaire stationnée dans un système où travaillent ses
  extracteurs les protège par son protocole ; une flotte ne remplit qu’un rôle à la fois (une
  mission ouverte, garanti en base) : vrai coût d’opportunité.
- **Patrouille (PATROL)** : circuit de 2 à 6 systèmes connus, durée d’arrêt par système. La flotte
  ne contrôle **que le système où elle se trouve à cet instant** : stationnée avec son protocole
  pendant l’arrêt, en transit entre deux arrêts (ses entrées sont des passages comme les autres).
  Elle continue tant qu’elle a ses unités et son carburant ; rapports à chaque événement notable.
- Présence et contrôle sont recalculés seulement aux événements (passages, arrivées, départs),
  jamais par balayage de la galaxie.

## 5. Guerre de mouvement (EXP-04)

Déjà fourni par 13B (PR #17) et conservé : passages réels par système intermédiaire, dates
logiques d’entrée, interceptions successives possibles, mission poursuivie avec les survivants,
interrompue si la flotte est détruite, aucune unité qui réapparaît, 24 h avant toute bataille
planétaire (Q02), aucun dommage aux colonies par interception, flottes civiles jamais détruites.

**Doctrines de déplacement** choisies au lancement, figées dans le snapshot de mission :

| Doctrine | Trajet | Durée / coût | Détection |
| --- | --- | --- | --- |
| **Directe** (défaut) | Plus court chemin connu (actuel) | Normaux | Normale |
| **Furtive** | Plus court chemin connu | Plus lente (facteur provisoire) | Signature réduite : déterministe, battue par une détection suffisante (A2) ; jamais d’invisibilité garantie |
| **Contournement** | Plus court chemin connu **évitant** des systèmes désignés (menaces connues ou choix du joueur) | Plus de sauts : plus de Flux et de temps | Normale ; une route sans danger connu n’est pas sûre |

Le serveur calcule et date tout (trajet, passages, coûts) ; le client affiche le résumé serveur
(`path`, PR #20). Aucun itinéraire ne révèle une donnée inconnue de l’Empire. La furtivité ne
supprime jamais les 24 h planétaires.

## 6. IA (EXP-05)

Mêmes commandes, ressources, informations et règles que les humains, décisions déterministes,
tours existants (600 s, une commande), aucune connaissance omnisciente, pas d’agitation inutile.
`economic_cautious` : opportunités rentables proches, routes sûres, escorte de ses exploitations ;
`expansionist` : prospecte et exploite plus loin, présence avancée, risques mesurés. Interception
offensive : seulement dans les cas déjà validés (B08) ; doctrines choisies selon les menaces
connues.

## 7. Interface (EXP-06)

Galaxie de la PR #19 conservée : vue optionnelle « Présence stratégique » (colonies, flottes,
patrouilles, exploitations, surveillance, alertes, menaces connues) sans frontière ; panneau
système (opportunités connues, opérations, observations datées, risques connus, actions réelles) ;
planification avec comparaison des doctrines (itinéraire, durée, Flux, risques connus, résumé
serveur, confirmation). Mobile et clavier comme le reste.

## 8. Esprit Echosphere

Missions persistantes et ordres qui continuent hors connexion ; aucune récolte manuelle répétée ;
rapports et alertes (cloche) ; automatisation gratuite pour tous (non pay-to-win) ; dix minutes par
jour suffisent, une à deux heures permettent de mieux préparer. Pas de RTS.

## 9. Décisions utilisateur du 09/11/2026 (après-midi) — priment sur les propositions ci-dessus

Provenance : réponses explicites de l’utilisateur aux arbitrages A1–A5 et compléments du même jour.

- **A1 remplacé — rencontre dans un système en opération** : le résultat dépend de la relation
  entre les deux Empires et des niveaux de détection :
  - **Allié** (pacte actif) ou **neutre** (connu, sans acte hostile récent) : simple message
    « flotte vue dans le système » (si détectée) ; aucune interruption.
  - **Inconnu** : message de rencontre d’un Empire et **protocole de premier contact** (attaque ou
    fuite selon le protocole choisi, règles 13B).
  - **Ennemi** (acte hostile récent, D4) : s’il est **de passage**, il passe, avec ou sans message
    selon la détection ; s’il a **prévu d’attaquer** les éléments présents, un **affrontement**
    s’engage avec la flotte en mission dans le système (et ses escortes).
- **Flottes d’extraction armées** : une flotte peut mêler extracteurs et vaisseaux de combat ;
  c’est cette flotte armée qui défend l’opération.
- **Flottes civiles destructibles (amende D5 à partir de v0.10)** : une flotte d’extracteurs **sans
  escorte** attaquée par un ennemi peut être **détruite**. D5 reste inchangée pour v0.9.
- **Défense locale obligatoire** : si une flotte de l’Empire est déjà en embuscade ou en patrouille
  dans le système, une attaque contre ses extracteurs est forcément défendue par elle.
- **Signatures** : les vaisseaux civils ont une signature plus faible que les vaisseaux de combat.
  Choix stratégique : extracteurs seuls mais discrets, ou escortés par une armada visible.
- **A2 validé** : lignes de Recherche *Capteurs* et *Signatures* ; doctrine furtive = +1 signature,
  durée × 1,5.
- **A3 remplacé** : entre Empires **neutres**, la réserve est **partagée**, la répartition dépend
  des extracteurs présents et de la **capacité de transport** (cargos ajoutés à la flotte) ; entre
  **ennemis**, c’est la flotte d’extraction armée qui décide (affrontement, A1).
- **A4 validé** : dossier complet = Données importantes + révélation des systèmes remarquables de
  la région, sans technologie exclusive.
- **A5 remplacé** : **tout passe en v0.10** (aucune partie existante à préserver) ; la création
  Portal et `start_universe` utilisent v0.10.
- **Tests PostgreSQL** : job CI temporaire sur les PR visant la recette, validé.
- **Galaxie — flottes visibles** : un symbole de flotte au-dessus d’un système ouvre une fenêtre
  (composition, mission) ; on peut y changer de mission ou ordonner un déplacement : la fenêtre se
  réduit en haut à gauche avec le filigrane « Choisir une destination », la carte reste utilisable
  (un clic ne ferme pas la fenêtre) ; choisir un système valide, clic droit ou Échap annule et
  restaure la fenêtre.
- **Maillage de la galaxie** : pas de systèmes tous reliés ; des **impasses** et des **connexions
  uniques** (goulots d’étranglement), enjeu stratégique majeur ; mais **aucun Empire isolé** : le
  graphe reste connexe et chaque départ garde des sorties. Ce lot de carte (avec les tailles
  100–2 000 de Q61) passe **avant** l’exploitation.

## 10. Arbitrages A1–A5 (proposition initiale, remplacée par le §9)

| Id | Question | Proposition | Bloque |
| --- | --- | --- | --- |
| A1 | Effet d’une flotte hostile sur une exploitation civile étrangère dans le même système | Une flotte AMBUSH/INTERCEPTION présente **suspend** l’extraction des Empires qu’elle détecte et que son protocole engagerait ; les extracteurs ne sont jamais détruits et se replient selon D7 (même règle que le repli amical) | Partie « contestée » d’EXP-02 |
| A2 | Furtivité : niveaux de signature/détection (Q58) | Deux lignes de Recherche : *Capteurs* (niveau de détection) et *Signatures* (niveau de furtivité) ; doctrine furtive = +1 signature, facteur de durée 1,5 ; comparaison FC7 inchangée | EXP-04 furtif |
| A3 | Partage d’un gisement disputé | Débit plafonné partagé au prorata des extracteurs engagés (§3) | EXP-02 concurrence |
| A4 | Récompense d’un dossier complet | Données importantes + révélation (DETECTED) des systèmes portant les opportunités remarquables de la région ; pas de technologie exclusive | Dossiers (fin d’EXP-01/EXP-02) |
| A5 | Nouvelles parties | Les parties créées depuis le Portal passent au ruleset v0.10 dès qu’EXP-02 est jouable ; les univers existants restent sur leur ruleset | Bascule de création |

Tout ce qui touche flottes civiles, 24 h, pactes, pillage, propriété des colonies ou règles de
combat reste soumis à décision explicite de l’utilisateur.

## Références

[Premier contact 13B](first-contact.md) · [Flottes](fleets.md) · [Combat](combat.md) ·
[Brouillard](fog-of-war.md) · [Relations](relations.md) · [Modes Q59–Q61](game-modes.md) ·
[Plan EXP](../05-project/exp-plan.md) · [Registre](../05-project/open-questions.md)

## Décision utilisateur du 10/11/2026 — régénération des gisements

Les réserves des gisements se régénèrent avec le temps pour rester des points stratégiques : en
v0.11, 10 % de la réserve totale par jour (`operations.regeneration_bps_per_day`), jamais au-delà du
total. La régénération est réglée en même temps que l’extraction, sous le verrou du gisement, en
µ-unités entières avec reste conservé ; une prospection observe la réserve à jour.
