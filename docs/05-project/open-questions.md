# Registre central des décisions ouvertes

Chaque Q reste ouverte jusqu'à un arbitrage explicite. Les propositions des docs ne la ferment pas.
Consigner date, raison, impact, document modifié et ADR si nécessaire. Les étapes indiquées sont
les moments limites pour décider avant de dépendre du choix.

Lot 5B du 2026-10-29 : [contrats identité/Portal-Game](../03-technical/identity-contracts.md),
avec décisions utilisateur et mécanismes encore proposés explicitement distingués.
Les parties de Q40–Q44 listées en fin de registre sont closes sur arbitrage utilisateur explicite
pour PR #6 ; leurs autres parties restent ouvertes. Q45 est close pour le comportement produit décrit plus bas. Q16, Q21 et Q46–Q56 restent ouvertes.

| ID | Question ouverte | À traiter avant | Référence |
| --- | --- | --- | --- |
| Q01 | Durées quotidiennes, longueur/parallélisme des files, annulation/remboursement | 3 puis 5 | [Sessions](../01-game-design/player-session.md) |
| Q02 | Protection hors connexion, réaction à une attaque, absence prolongée | 12, cadrage dès 1 | [Sessions](../01-game-design/player-session.md) |
| Q03 | Taux/coûts, stockage, entretien, précision et arrondis des trois ressources | 3/5 | [Calcul](../03-technical/resource-calculation.md) |
| Q04 | Catalogue/niveaux, traits, capacités exactes, slots orbitaux et réaffectation | 2/5 | [Planètes](../01-game-design/planets-colonies.md) |
| Q05 | Technologies, prérequis, parallélisme et changement d'orientation | 6 | [Recherche](../01-game-design/research.md) |
| Q06 | Topologie, départs équitables, distribution des mondes, version du générateur | 7 | [Galaxie](../01-game-design/galaxy.md) |
| Q07 | Coûts/limites d'expansion, habitabilité, contestation, transfert et abandon | 10 | [Colonisation](../01-game-design/colonization.md) |
| Q08 | Transitions du fog, capteurs, partage et vieillissement de l'information | 7/8 | [Fog](../01-game-design/fog-of-war.md) |
| Q09 | Classes/stats, routes, vitesse, cargo, rappel et coût des missions | 9 | [Flottes](../01-game-design/fleets.md) |
| Q10 | Résolution combat, aléatoire, ciblage, retraite, pertes et butin | 12 | [Combat](../01-game-design/combat.md) |
| Q11 | Poids des profils, départs, fréquence et budget des IA | 11 | [IA](../03-technical/ai-engine.md) |
| Q12 | Mesure du ratio 80/20, métriques et format validé de game_data | 5 puis 16 | [Balance](../01-game-design/balance-philosophy.md) |
| Q13 | Ordre simultané, locks, rattrapage, retries et compatibilité des versions | 3 | [Événements](../03-technical/event-engine.md) |
| Q14 | Victoire/défaite, durée d'univers, resets et rattrapage | cadrage MVP | [Progression](../01-game-design/progression.md) |
| Q15 | Validation finale de la navigation proposée étape 4, carte tactile, libellés et tokens | 4 | [UX](../02-ux-ui/information-architecture.md) |
| Q16 | Identité/session et autorisation : architecture partiellement validée, mécanismes ouverts Q40–Q56 | 5B avant 5C/5D | [Sécurité](../03-technical/security.md) |
| Q17 | Budgets de performance et charge de référence | 3 puis 17 | [Performance](../04-quality/performance.md) |
| Q18 | Contenu exact des relations minimales, hostilité et négociation | 13 | [Roadmap](roadmap.md) |

## Modes futurs : nouvelles questions distinctes (toutes ouvertes)

| ID | Arbitrage attendu | Référence |
| --- | --- | --- |
| Q19 | Règles exactes des parties privées, invitations et IA optionnelles | [Modes](../01-game-design/game-modes.md) |
| Q20 | Nombre maximal de joueurs par famille d'univers | [Modes](../01-game-design/game-modes.md) |
| Q21 | Un joueur/un empire ou empire partagé, rôles et permissions | [ADR 0006](../adr/0006-universe-game-instance.md) |
| Q22 | Victoire, durée et fin par famille ; aucune durée maximale obligatoire en persistant | [Modes](../01-game-design/game-modes.md) |
| Q23 | Règles join/leave et conséquences pour l'empire et la partie | [Modes](../01-game-design/game-modes.md) |
| Q24 | Conditions de late join d'un univers persistant déjà actif | [Modes](../01-game-design/game-modes.md) |
| Q25 | Protection et progression d'un nouvel arrivant | [Modes](../01-game-design/game-modes.md) |
| Q26 | Rythmes/vitesses et version des rulesets selon famille d'univers | [Modes](../01-game-design/game-modes.md) |
| Q27 | Pause possible ou non des parties privées et autorité de décision | [Modes](../01-game-design/game-modes.md) |
| Q28 | Équipes/alliances de départ possibles et règles associées | [Modes](../01-game-design/game-modes.md) |
| Q29 | Dimensionnement, capacité et objectifs de charge des univers persistants | [Performance](../04-quality/performance.md) |

Aucune réponse implicite par le code de l'étape 3. Q14 reste la question générale de progression/fin,
Q22 distingue les familles ; Q02 et Q25 devront être conciliées sans décider de protection maintenant.

## Cadrage actuel des questions

Q16, cadrage historique 1–2 : aucune mutation publique sans identité/contrôle objet/idempotence.
**Évolution validée 2026-10-28** : compte global multi-parties, Membership, Portal/Game séparés,
Accounts DB/Game DB distinctes, pas de SQL Portal→Game, interface interne et GameSession autonome.
Ces décisions ne ferment pas les mécanismes Q40–Q56. Les sondes gardent leur contrat.
Q04 n'est pas fermée par le schéma : les capacités sont fournies explicitement, sans plafond
9–18 ou défaut 12 imposé. Q07 reste ouverte : la table colonies représente l'occupation actuelle,
le cycle de vie et l'historique nécessiteront une migration au lot colonisation.
Q02 est un prérequis du futur combat : aucun endpoint d'attaque ne sera livré avant arbitrage.

## Cadrage technique étape 3 (partiel)

Q03 : micro-unités entières (1 unité = 1 000 000), taux horaires et reste exact persisté. BIGINT non
négatif avec dépassement explicite. Capacité optionnelle saturante sans valeur par défaut de gameplay.
Coûts, rendements, entrepôts et entretien restent ouverts.
Q13 : pour chaque EventStream, ordre due_at/séquence sous verrou, rattrapage à date logique, SAVEPOINT pour
reprise atomique, retries bornés et blocage de tête. L'ordre multi-agrégats, flotte/combat et migrations
de payload/archivage restent ouverts. Détails dans [ADR 0005](../adr/0005-colony-time-engine.md).

## Décisions techniques prises pour le bootstrap

Python 3.12, Node 22 dans Docker, PostgreSQL 17, psycopg direct pour les sondes, proxy Vite même
origin, ports loopback et absence de montage source. Ce sont des choix d'implémentation réversibles,
pas des arbitrages de gameplay. SQLAlchemy/Alembic sont désormais en place pour les cinq premiers modèles, sans endpoint métier.

## Défense planétaire — nouvelles questions (toutes ouvertes)

| ID | Arbitrage attendu | Référence |
| --- | --- | --- |
| Q30 | Capacité défensive totale et croissance du réseau | [Défense](../01-game-design/planetary-defense.md) |
| Q31 | Nombre, types, familles et compatibilités de modules | [Défense](../01-game-design/planetary-defense.md) |
| Q32 | Interaction défense/flotte, portée et interception | [Défense](../01-game-design/planetary-defense.md) |
| Q33 | Réparation : coûts, durées, priorité et récupération hors combat | [Défense](../01-game-design/planetary-defense.md) |
| Q34 | Consommation de Flux normale/alerte/combat et épuisement | [Défense](../01-game-design/planetary-defense.md) |
| Q35 | Destruction permanente/temporaire et intégrité résiduelle | [Défense](../01-game-design/planetary-defense.md) |
| Q36 | Ciblage des modules, ordre des dommages et campagne d’usure | [Défense](../01-game-design/planetary-defense.md) |
| Q37 | Révélation par renseignement/espionnage, estimation et vieillissement | [Défense](../01-game-design/planetary-defense.md) |
| Q38 | Place/coût d’opportunité et rôle des défenses orbitales | [Défense](../01-game-design/planetary-defense.md) |
| Q39 | Annulation quand le remboursement dépasse la place de stockage disponible | [Économie v0.1](../01-game-design/colony-economy-v0.1.md) |

Aucune question défensive fermée ; pas de catalogue définitif, valeurs ni tables actives déduites
de ces orientations. Pour Q39, l’implémentation refuse atomiquement une annulation qui ne peut pas
rendre le montant exact, sans overflow/perte cachée ; choix conservateur à valider pour le produit.

## Arbitrages fournis pour 5A — 2026-10-28, balance v0.1 provisoire

Q01 partielle : trois ordres actif inclus, un seul actif, réservation immédiate, remboursement
queued 100 % / active 80 % et activation à la date logique. La cascade des upgrades dépendants
est implémentée ; sa confirmation produit/UX reste sous Q01, elle n’est pas promue en validation
utilisateur par sa seule présence en code.
Q03 partielle : stocks, taux, coûts et capacités de référence dans game_data ; production perdue au
plafond, récurrences rationnelles et arrondis côté serveur. Entretien général reste ouvert.
Q04 partielle : cinq types économiques, 12 secteurs/2 orbitaux de référence, producteurs répétables,
industrie/logistique uniques, niveaux continus (ancienne limite I–V remplacée). Traits, démolition,
réaffectation et orbitaux jouables restent ouverts. Q12 : JSON strict validé et snapshot par univers ;
simulations d’équilibrage et politique d’édition/migration futures restent ouvertes.
Q26 partielle : multiplicateurs économie/construction par univers, ×1 de référence, vitesses
recherche/flotte réservées sans système associé. Changement de vitesse d’un univers actif à cadrer.
Q16 reste partiellement ouverte : 5B doit préciser les contrats avant 5C/5D ; aucune API gameplay
ou identité globale factice ajoutée.

## Identité / Portal-Game — Q16 partiellement cadrée, aucune implémentation (2026-10-28)

**Décisions validées** : compte global, plusieurs univers simultanés, participation via
UniverseMembership, pas de Empire.owner_user_id unique ; empire partagé Q21 reste ouvert. Portal
Control Plane et Game Data Plane indépendants/isolables, Accounts DB/Game DB distinctes/séparables ;
aucun credential en Game DB, aucune écriture SQL Portal→Game. Interface interne contrôlée,
authentifiée et idempotente pour provision/grant/revoke/join. Ticket très court/usage unique puis
GameSession autonome ; gameplay direct à Game sans dépendance Portal par commande. Panne Portal
ne doit pas interrompre univers/workers/sessions établies selon le contrat à définir.
Référence canonique : [ADR 0008](../adr/0008-control-plane-game-data-plane.md).

Les lignes suivantes conservent les travaux restants. **Q40–Q44 partiellement closes** par les
arbitrages du 2026-10-29 décrits après le tableau ; aucune de ces questions n’est entièrement close.
Q45 est **close pour le comportement produit**, non implémentée. Q49 est **partiellement close** pour la récupération et le changement d’email ; les autres Q46–Q56 restent **Question ouverte**,
sans validation implicite de leurs mécanismes ; regroupement appareil Q41/Q43 toujours ouvert.

| ID | Arbitrage restant | Dépendance / référence |
| --- | --- | --- |
| Q40 | Partiellement close : login MVP, récupération 30 min/unique, réémission et effets du reset validés ; restent bibliothèque/paramètres Argon2id, mécanismes de récupération ; changement email sans MFA, demande unique 1 h/remplacement complet et révocation globale validés, mécanismes ouverts | 5B/5C, [contrats](../03-technical/identity-contracts.md) |
| Q41 | Partiellement close : 7 j absolus / 72 h d’inactivité et activité explicite classée côté serveur validés ; restent cookies/stockage et rotation | 5B, contrats |
| Q42 | Partiellement close : ticket 60 s/usage unique validé ; restent format/crypto, nonce/audience, liaison navigateur et consommation anti-rejeu | 5B, contrats et ADR 0008 |
| Q43 | Partiellement close : 8 h absolues / 2 h d’inactivité et expiration anticipée par GameAccess validées, activité explicite classée côté serveur ; restent stockage et limites de sessions | 5B avant 5D, contrats |
| Q44 | Partiellement close : plafond non glissant 8 h depuis confirmation Portal, refus à échéance et renouvellement avec Portal/confirmation/handoff validés ; restent protocoles et mécanismes de révocation/renouvellement | 5B, contrats |
| Q45 | Close — comportement produit : retour lobby sans logout ; déconnexion Game limitée à sa session ; compte sur appareil courant ; action distincte tous appareils ; progression conservée, révocation persistée/rejouée et état en attente | Validé utilisateur 2026-10-29, non implémenté ; appareil Q41/Q43 et protocoles Q53/Q54 ouverts, [contrats](../03-technical/identity-contracts.md) |
| Q46 | Auth service-to-service et exposition réseau de l’interface interne | 5B, aucun mTLS/signature/credential choisi |
| Q47 | CSRF, origines, cookies et politique CORS liée au découpage | 5B/5C/5D, sécurité |
| Q48 | MFA et récupération associée | Cadrage 5B, implémentation selon périmètre |
| Q49 | Partiellement close : récupération 30 min/unique, invalidation des anciens liens, effets globaux du reset, notification email et non-énumération validés ; changement sans MFA avec double confirmation/pending, notifications et réauthentification validé ; demande unique 1 h, remplacement complet et révocation globale validés ; restent fournisseur/livraison et mécanismes | 5B/5C |
| Q50 | Anti-bot/CAPTCHA, limites IP/compte et protections brute force | 5B/5C, pas de produit choisi |
| Q51 | Modèle exact rôles/permissions et contexte empire | 5B, sans fermer Q21 |
| Q52 | Membership suspendu, reprise et droits lors d’un accès Game | 5B, compatible Q23/Q24 |
| Q53 | Synchronisation Portal/Game, ordre/retries, autorité des droits et réconciliation | 5B avant provision/join |
| Q54 | Révocation pendant GameSession, propagation et limites en panne Portal | 5B, autonomie sans promesse d’instantanéité |
| Q55 | Politique d’accès/sécurité des univers privés et persistants | 5B puis lots modes, Q19–Q29 préservées |
| Q56 | Validation autonome du ticket, clés/rotation et dépendances de handoff en mode dégradé | 5B, format crypto non décidé |

## Arbitrages explicites 5B — 2026-10-29, parties closes uniquement

**Source/provenance : décision utilisateur explicite pour poursuivre PR #6**, synthétisée sans
transcript privé. Statut **Décision validée, non implémentée**. Canonique :
[identity-contracts](../03-technical/identity-contracts.md). Les décisions ne valent ni protocole
accepté pour les autres Qxx, ni livraison de code, ni autorisation de fusion ou de passage à 5C.

- Q40 : MVP email/mot de passe, adresse vérifiée avant premier handoff Game, récupération par
  jeton court à usage unique, hash Argon2id via bibliothèque maintenue. global_user_id indépendant
  de l’email et de la méthode de connexion. Google/OIDC futur comme méthode supplémentaire du même
  compte, sans dépendance MVP. Bibliothèque et paramètres restent ouverts ; durée et comportement
  de récupération sont désormais précisés par le complément Q40/Q49 ci-dessous, indépendamment
  du ticket de handoff de 60 s.
- Q41 : session Portal au plus 7 jours absolus et 72 heures d’inactivité ; l’activité ne prolonge
  pas l’absolu. La proposition initiale de 24 h d’inactivité est remplacée par cet arbitrage.
- Q42 : ticket de handoff au plus 60 secondes, usage unique. Format, crypto, nonce/audience,
  liaison au navigateur et preuve de consommation unique restent à contractualiser.
- Q43 : session Game au plus 8 heures absolues et 2 heures d’inactivité ; GameAccess peut la faire
  expirer plus tôt. L’activité ne prolonge pas l’absolu. Stockage et limites simultanées restent ouverts.
- Q44 : droits Game valides au plus 8 heures depuis leur dernière confirmation Portal, fenêtre
  jamais glissante sur l’activité Game, sans reset au début d’une panne. Révocation/suspension reçue
  appliquée immédiatement. Si Portal ou la liaison est indisponible, une nouvelle révocation peut
  rester sans effet jusqu’à valid_until ; aucune autonomie de renouvellement illimitée. À cette
  échéance, nouvelles commandes refusées, univers/workers poursuivant leur progression. Un
  renouvellement nécessite Portal disponible et une nouvelle confirmation/handoff valide.

Q46 (S2S), Q47 (cookies/CSRF/origines), Q48 (MFA), Q49 (fournisseur email et détails
de vérification/récupération), Q50 (anti-abus), Q51–Q53 (permissions/membership/synchronisation),
Q54 (propagation de révocation), Q55 (modes) et Q56 (crypto/clés) restent ouvertes.
La fenêtre validée sous Q44 ne ferme pas les mécanismes de Q54.

**Complément utilisateur validé Q41/Q43 — 2026-10-29 :** seules les interactions explicites
réinitialisent l’inactivité : navigation volontaire, action/commande, modification/sauvegarde d’un
réglage, actualisation demandée ou autre requête explicitement classée comme telle par le serveur.
Polling, refresh périodique, heartbeat, réception WebSocket, reconnexion automatique, prefetch,
télémétrie et onglet ouvert ne comptent pas. Classification par type de requête/action côté serveur,
sans confiance dans un timestamp navigateur. Aucune prolongation des limites absolues ni de
GameAccess.valid_until. Décision non implémentée ; les scénarios restent des critères futurs.

### Q45 — comportement produit validé le 2026-10-29, non implémenté

Source : arbitrage explicite utilisateur pour PR #6. Q45 close, aucune autre Qxx close par implication.
Retour lobby/quitter l’écran n’est pas une déconnexion : GameSession conservable dans ses limites.
Déconnexion Game : seule la session concernée, univers et appareil/session courants ; ni autres
GameSessions du même appareil, ni autres univers/appareils, ni session Portal invalidés.
Déconnexion du compte sur cet appareil : PortalSession courante et toutes les GameSessions du
même compte sur cet appareil invalidées ; autres appareils préservés, aucune partie silencieusement
laissée connectée. « Déconnecter tous les appareils » est distinct et explicite : toutes les
PortalSessions/GameSessions du compte, tous appareils et univers.
Memberships, empires, états, progression des univers/workers et actions déjà acceptées conservés.
Si Game est injoignable pendant la révocation globale : demande persistée/rejouée jusqu’à acquittement,
UI terminée/en attente sur certains services ; aucune instantanéité distante prétendue. Sessions
non atteintes toujours bornées par les échéances validées, dont valid_until et maximum 8 h depuis
confirmation Portal. Regroupement technique par appareil sous Q41/Q43, protocoles sous Q53/Q54
restent ouverts ; aucune acceptation implicite d’epoch, outbox ou stockage.

### Q40/Q49 — récupération validée le 2026-10-29, parties closes uniquement

Source : validation explicite utilisateur pour PR #6 ; non implémentée. Jeton valable au maximum
30 minutes depuis émission, usage unique et expiration serveur. Nouvelle émission : tous les
anciens jetons encore valides du compte immédiatement invalidés, anciennes URLs inutilisables ;
seul le parcours le plus récent peut aboutir.
Reset réussi : toutes les PortalSessions du compte invalidées sur tous appareils, demande de
révocation de toutes ses GameSessions tous univers/appareils, tous jetons de récupération invalidés.
Nouvelle connexion normale imposée, aucun auto-login ; email notifiant la modification, aucun
mot de passe dans les emails. Memberships, empires et états gameplay conservés.
Game injoignable : révocation persistée/rejouée jusqu’à acquittement, sans promesse instantanée ;
valid_until et maximum 8 h depuis dernière confirmation Portal inchangés, aucun reset de fenêtre.
Réponse de demande non énumérable ; contrôles anti-abus restent Q50. Q40/Q49 restent partiellement
ouvertes, fournisseur/livraison/changement d’email et mécanismes non choisis. Q48, Q50, Q53 et Q54
ne sont pas fermées par implication. Canonique : section 6 des contrats identité.

### Q40/Q49 — changement d’email validé le 2026-10-29, parties closes uniquement

Source : arbitrage explicite utilisateur pour PR #6 ; non implémenté. Sans MFA : session Portal
valide, mot de passe actuel ressaisi, confirmation depuis l’ancienne adresse et confirmation de
la nouvelle obligatoires. Adresse nouvelle pending jusqu’aux deux confirmations et jamais effective
avant validation. Succès : notifier les deux adresses, nouvelle authentification requise ;
global_user_id, memberships, empires et états gameplay conservés.
Ancienne adresse inaccessible : aucun bypass mot de passe seul ; flux distinct avec preuve
indépendante déjà établie (MFA, codes ou support seulement si décidés/disponibles). Sans ce mécanisme
dans le MVP, changement bloqué. Si Q48 valide et implémente MFA forte : remplacement possible de
la confirmation ancienne, réauthentification selon contrat, MFA et confirmation nouvelle obligatoires,
ancienne adresse notifiée avec moyen de signaler une opération non reconnue ; politique exacte Q48
ouverte. Aucun mécanisme de récupération indépendant/MFA/support n’est accepté ou implémenté ici.

**Complément utilisateur validé — 2026-10-29 :** demande unique active par compte, maximum 1 h
absolue depuis création ; les deux confirmations partagent cette échéance sans délai glissant.
À échéance toute la demande expire. Nouvelle demande : ancienne demande, deux liens et confirmations
acquises immédiatement invalidés ; deux nouvelles confirmations requises, jamais de mélange de demandes.
Succès après toutes validations : nouvelle adresse active ; toutes les sessions Portal/Game du compte
révoquées, tous appareils/univers et session courante inclus ; nouvelle connexion normale avec la
nouvelle adresse, sans maintien automatique. Game injoignable : intention persistée/rejouée jusqu’à
acquittement, aucune instantanéité promise, valid_until/8 h depuis confirmation Portal jamais relancés.
Notifications aux deux adresses après succès sans credential/token sensible ; identité et états conservés.
Q40/Q49 restent partiellement ouvertes pour fournisseur/livraison et mécanismes. Q48/Q50/Q53/Q54
ne sont pas fermées par implication. Prochain arbitrage nécessaire : périmètre MFA Q48 (MVP,
comptes concernés, facteur et récupération), sans l’implémenter ni commencer 5C.

12 secteurs/2 slots orbitaux concernent seulement le départ de référence v0.1 ; distribution et
capacités variables futures restent Q04/Q06. Q39 reste ouverte. Q01–Q39 ne sont ni supprimées,
renumérotées ni fermées par cet ajout. Les comptes/memberships restent sans nouvelles tables.
