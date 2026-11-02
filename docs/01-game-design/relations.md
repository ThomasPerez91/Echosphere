# Relations entre civilisations

**Statut : Q18 close pour l'étape 13 le 02/11/2026 (validation explicite avec amendements).**
Les [décisions validées](#q18--validation-avec-amendements-02112026) priment sur la proposition R01
conservée plus bas comme historique. Plan : [étape 13](../05-project/step-13-plan.md). Présence
frontalière et protocoles de premier contact : [lot 13B](first-contact.md), hors étape 13.

## Situation actuelle (v0.7)

Les Empires ne se connaissent pas. Aucun état de relation n'existe : tout Empire disposant de
`combat.attack` peut attaquer toute planète connue, sans préavis autre que les 24 h de Q02.
L'identité d'un adversaire n'apparaît que dans un rapport de combat, après bataille. Une colonie
étrangère n'est jamais affichée, même voisine. L'IA se défend mais n'attaque ni ne négocie.

## Q18 — proposition R01 du 02/11/2026, non validée

**Historique : proposition remplacée par la validation ci-dessous.** Valeurs numériques = première balance provisoire, à mesurer.

### Principe

Des relations **minimales, bilatérales et explicables** : savoir qui l'on a rencontré, voir l'état
de la relation, proposer ou rompre un **pacte de non-agression**. Le pacte est le seul accord : il
empêche les batailles entre ses deux signataires et ne fait rien d'autre. Pas d'alliance, de
commerce, de tribut ni de partage d'information. Humains et IA utilisent les mêmes commandes.

### Contact

Un Empire **connaît** un autre Empire seulement après une observation légitime et datée :
1. **un rapport de combat** qui le nomme (attaquant et défenseur d'une bataille livrée) ;
2. **une présence étrangère observée** (option B3) : une colonie étrangère sur une planète d'un
   système que l'observateur surveille (MONITORED par sa propre colonie). L'observateur apprend
   seulement le nom de l'Empire, la planète et la date d'observation ; jamais stocks,
   infrastructures, flottes, Research ou autres colonies. En perte de surveillance, la présence
   reste datée (`last_seen_at`), comme toute information dynamique Q08.

Le contact est **orienté** (A peut connaître B sans réciproque) et durable : l'identité connue
n'est pas oubliée. Un échec `target_unavailable` ne crée jamais de contact. Aucun contact n'est
partagé, même entre signataires d'un pacte.

### États d'une paire

| État | Sens | Effet sur le Combat v0.7 |
| --- | --- | --- |
| Sans accord (défaut) | Contact établi ou non, aucun pacte | Inchangé : attaques possibles |
| Pacte proposé | Une proposition ouverte d'un camp vers l'autre | Inchangé tant que non acceptée |
| Pacte actif | Accepté par les deux camps | Toute bataille entre eux à `battle_at` est annulée |
| Pacte en rupture | Rupture notifiée, préavis en cours | Toujours protecteur jusqu'à la fin du préavis |

L'« hostilité » n'est pas un état déclaré : c'est un **fait observable** affiché avec sa date, le
dernier acte hostile connu de chaque camp (bataille reçue ou livrée entre eux). Pas de déclaration
de guerre obligatoire : imposer « hostile » avant d'attaquer révélerait l'occupant au lancement.

### Négociation

- **Proposer** un pacte : seulement à un Empire connu, au plus une proposition ouverte par paire.
  Expiration automatique après **72 h** ; retrait possible par son auteur.
- **Accepter / refuser** : par le destinataire seulement. Un refus bloque une nouvelle proposition
  du même auteur vers le même Empire pendant **24 h**.
- **Rompre** : unilatéral, effectif après un **préavis de 24 h** (cohérent avec la fenêtre Q02).
  Après la fin du préavis, retour à « sans accord » ; nouvelle proposition possible aussitôt.
- Aucune condition, contrepartie, ressource ou durée négociée. Aucune annulation d'ordre, de
  mission ou de production causée par un pacte.

### Effet sur le Combat

- ATTACK **n'est jamais refusée au lancement** pour une raison de relation (non-fuite inchangée).
  L'UI peut rappeler un pacte quand l'attaquant connaît déjà le propriétaire par son propre contact.
- À `battle_at`, si le pacte entre attaquant et défenseur lié est **effectif à cette date logique**
  (accepté au plus tard à `battle_at`, rupture effective strictement après), la bataille n'a pas
  lieu : issue `voided_by_pact`, aucune perte, retour normal de l'attaquant, carburant non
  remboursé, alerte du défenseur close comme annulée, rapports aux deux camps sans composition.
- La décision ne dépend que des dates logiques, jamais de l'ordre de traitement des workers.

### IA

Politique pure et déterministe, une nouvelle famille `diplomacy` dans le tour unique de 10 min :
- répondre à une proposition reçue : accepter si aucun acte hostile de cet Empire contre elle
  depuis **72 h**, refuser sinon ; la réponse est prioritaire sur les autres candidats ;
- proposer un pacte à un contact sans acte hostile récent : `economic_cautious` oui,
  `expansionist` seulement après avoir subi une attaque de ce contact il y a plus de 72 h ;
- ne jamais rompre un pacte dans ce lot ; aucune offensive (sauf arbitrage B10).
Mémoire limitée aux faits de ses propres contacts/rapports ; aucune connaissance étrangère cachée.

### Arbitrages demandés avant R02

| ID | Recommandation à valider |
| --- | --- |
| B1 | Périmètre : contact, état de paire, pacte de non-agression seul ; ni alliance, commerce, tribut, partage de Fog, messagerie libre |
| B2 | Contact par rapport de combat nommant l'adversaire ; orienté, durable, jamais par `target_unavailable` |
| B3 | Contact aussi par présence étrangère dans un système MONITORED (nom d'Empire, planète, date seulement) — extension Fog ; alternative : rapports seuls |
| B4 | Deux états effectifs (sans accord / pacte) ; hostilité = fait daté affiché, pas de déclaration de guerre préalable |
| B5 | Proposition unique par paire, expiration 72 h, retrait ; refus = délai 24 h avant nouvelle proposition |
| B6 | Rupture unilatérale avec préavis 24 h, pacte protecteur pendant le préavis |
| B7 | Effet Combat à `battle_at` seulement (`voided_by_pact`), jamais au lancement ; dates logiques seules |
| B8 | IA : famille `diplomacy`, réponse prioritaire, règles 72 h ci-dessus, profils différenciés, jamais de rupture |
| B9 | Ruleset v0.8 explicite (v0.7 + `relations.json` + `ai.json` v3), nouveaux univers seulement ; v0.1–v0.7 inchangés |
| B10 | Toujours aucune offensive IA à l'étape 13 ; alternative : riposte IA bornée contre un agresseur connu, à arbitrer séparément |
| B11 | Droits `relations.read` / `relations.negotiate` (17), capabilities IA correspondantes, migration additive 0013 |
| B12 | UI section Relations (contacts, état, faits datés, actions, historique), alertes ; sans maquette de référence, dérivée du design system |

Une validation Q18 ne vaut pas autorisation de merge. R02–R11 restent conditionnels.

## Q18 — validation avec amendements, 02/11/2026

**Q18 close pour l'étape 13.** Provenance : instruction utilisateur explicite. R02 → fin du lot
autorisés sans nouvelle validation produit intermédiaire, sauf contradiction réelle. Aucun merge.

- **B1 Périmètre :** contacts, état minimal de chaque relation, pacte de non-agression. Ni alliance,
  commerce, tribut, transfert de ressources/Colony/Fleet, partage de Fog, messagerie libre ou vote.
- **B2 Contact par Combat :** le modèle est **orienté** (A connaît B n'implique pas B connaît A),
  durable et jamais oublié. Une vraie bataille v0.7 produisant un rapport pour chaque camp, elle
  crée en pratique les deux contacts dans la même résolution. Le modèle orienté sert aux futurs
  contacts asymétriques (observation, détection, premier contact). `target_unavailable` : aucun
  contact.
- **B3 Contact par proximité :** une Colony étrangère observée dans un système réellement MONITORED
  grâce à la présence légitime propre crée un contact orienté. Seuls Empire, planète et
  `observed_at` sont accessibles, jamais stocks, infrastructures, Research, flottes, cargo,
  activité ou autres colonies. La donnée reste datée ; perdre MONITORED n'efface pas le contact.
  La détection future d'une flotte inconnue ne crée pas nécessairement un contact nommé (13B).
- **B4 États :** `NO_AGREEMENT` et `PACT` seulement ; pas d'`AT_WAR`, `HOSTILE`, `ALLY` ni
  `NEUTRAL`. L'hostilité est un fait historique daté par camp (dernier acte hostile de chacun), sans
  duplication incohérente. À l'étape 13, un acte hostile = bataille effectivement résolue entre les
  deux Empires ; `target_unavailable` et `voided_by_pact` n'en sont pas. Les futurs engagements
  automatiques (embuscade, interception) compteront lorsqu'ils existeront. Pas de déclaration de
  guerre.
- **B5 Proposition :** une seule ouverte par paire, vers un Empire déjà connu ; expiration 72 h,
  retrait par l'auteur ; après refus, le même auteur ne repropose pas au même Empire pendant 24 h.
  Ni conditions, ressources, tribut, durée négociée ou clause spéciale.
- **B6 Rupture :** unilatérale, préavis 24 h pendant lequel le pacte reste intégralement actif ;
  à l'échéance `PACT → NO_AGREEMENT`. Date logique autoritaire côté serveur.
- **B7 Combat :** ATTACK jamais refusée au lancement selon un pacte avec l'occupant caché. À
  `battle_at`, pacte actif entre les deux Empires → `voided_by_pact` : aucune perte, aucun tir,
  aucune composition révélée, retour de l'attaquant, carburant non remboursé, alerte du défenseur
  close, rapports datés des deux côtés. Décision selon l'état logique à `battle_at` seulement.
- **B8 IA policy v3 :** famille `diplomacy`, grille 10 min, une commande maximum par tour. Réponse à
  une proposition prioritaire sur les candidats ordinaires et consommant le tour : `ACCEPT` sans
  acte hostile du proposant envers l'IA depuis 72 h, sinon `REFUSE`. Proposition spontanée :
  `economic_cautious` vers un contact sans grief récent ; `expansionist` seulement si sa dernière
  attaque subie de ce contact a plus de 72 h. Aucune rupture par l'IA. Poids v3 :

| Profil | Économie | Recherche | Exploration | Expansion | Logistique | Militaire | Diplomatie |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| economic_cautious | 35 | 20 | 15 | 10 | 5 | 10 | 5 |
| expansionist | 20 | 15 | 15 | 30 | 5 | 10 | 5 |

- **B9 Ruleset :** v0.8 = copie complète v0.7 + `relations.json` + `ai.json` policy v3 ; v0.1–v0.7
  inchangés, aucune adoption rétroactive ni migration d'ancien Universe vers v0.8.
- **B10 Offensive IA :** aucune à l'étape 13. L'IA produit, défend, négocie, accepte ou refuse ; elle
  ne choisit pas de cible ATTACK. `INTERCEPTION` (13B) est distincte d'une stratégie offensive.
- **B11 Droits :** `relations.read` et `relations.negotiate`, total 17 ; CHECK/DTO/schéma/Portal/tests
  mis à jour. Migration 0013 : migration métier non destructive et sans transformation des données
  historiques, avec extension contrôlée des contraintes de permissions existantes. Aucun grant
  humain automatique ; l'IA reçoit ses capabilities internes par son seul dispatcher.
- **B12 Interface :** contacts connus, état, derniers faits hostiles datés, propositions reçues/
  envoyées, expiration, rupture en préavis, historique, alertes, actions disponibles. Design dérivé
  du design system existant, responsive et clavier, sans esthétique nouvelle.

## Références

- [Combat Q02/Q10](combat.md) · [Brouillard Q08](fog-of-war.md) · [Modes Q25/Q28](game-modes.md)
- [Civilisations IA](artificial-intelligence.md) · [Premier contact 13B](first-contact.md) · [Registre](../05-project/open-questions.md)
