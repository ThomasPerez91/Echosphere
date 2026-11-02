# Relations entre civilisations

**Statut : Q18 ouverte. Proposition R01 du 02/11/2026, non validée ; rien n'est implémenté.**
Audit du code intégré `067a4e5` et plan conditionnel : [étape 13](../05-project/step-13-plan.md).
Une proposition d'assistant ne vaut pas décision : seuls les arbitrages validés explicitement par
l'utilisateur seront transcrits dans une section « validation » de ce document.

## Situation actuelle (v0.7)

Les Empires ne se connaissent pas. Aucun état de relation n'existe : tout Empire disposant de
`combat.attack` peut attaquer toute planète connue, sans préavis autre que les 24 h de Q02.
L'identité d'un adversaire n'apparaît que dans un rapport de combat, après bataille. Une colonie
étrangère n'est jamais affichée, même voisine. L'IA se défend mais n'attaque ni ne négocie.

## Q18 — proposition R01 du 02/11/2026, non validée

**Proposition uniquement.** Valeurs numériques = première balance provisoire, à mesurer.

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

## Références

- [Combat Q02/Q10](combat.md) · [Brouillard Q08](fog-of-war.md) · [Modes Q25/Q28](game-modes.md)
- [Civilisations IA](artificial-intelligence.md) · [Registre](../05-project/open-questions.md)
