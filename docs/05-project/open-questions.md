# Registre central des décisions et questions ouvertes

Chaque Q reste ouverte jusqu'à un arbitrage explicite. Les propositions des docs ne la ferment pas.
Consigner date, raison, impact, document modifié et ADR si nécessaire. Les étapes indiquées sont
les moments limites pour décider avant de dépendre du choix.

## Complément utilisateur du 31/10/2026 — PR #8

Provenance : instruction explicite de finaliser 5D avec Q39 et de consolider les autres arbitrages.
Q01 (construction), Q08, Q17, Q19–Q39 et Q55 sont désormais closes dans la portée indiquée.
Seule Q39 change le gameplay livré ici, avec confirmation complète de cascade Q01.
Fog, modes, partage produit, pause, protections et défense restent futurs. Les budgets performance
et caps sont des objectifs/paramètres initiaux, sans capacité garantie. Q02/Q03/Q04/Q05/Q10/Q14
et les autres questions non tranchées gardent leur portée ; aucun nouveau choix implicite.

Lot 5B du 2026-10-29 : [contrats identité/Portal-Game](../03-technical/identity-contracts.md)
validés par l’utilisateur, dont le bloc final en quatorze points avec corrections MFA, sessions
configurables et CORS. 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`) ;
contrats partiellement implémentés par C02–C07 sur PR #7, handoff/GameSession C07 livrés sur PR #7. 5C devient le lot courant, sans modifier ces décisions.
Le tableau Q40–Q56 distingue décisions closes, détails techniques délégués et sujets différés.

| ID | Question ouverte | À traiter avant | Référence |
| --- | --- | --- | --- |
| Q01 | **Clos construction** : 3 ordres actif inclus, 1 actif/colonie, 100 % queued / 80 % active théoriques, cascade des seuls upgrades dépendants validée ; colonies parallèles futures ; pacing onboarding secondes–5 min, début 5–30 min, intermédiaire 30 min–8 h, avancé 8–72 h, projets majeurs jours ; valeurs exactes game_data balançables. Recherche distincte Q05 | 3 puis 5 | [Sessions](../01-game-design/player-session.md) |
| Q02 | Protection hors connexion, réaction à une attaque, absence prolongée | 12, cadrage dès 1 | [Sessions](../01-game-design/player-session.md) |
| Q03 | Taux/coûts, stockage, entretien, précision et arrondis des trois ressources | 3/5 | [Calcul](../03-technical/resource-calculation.md) |
| Q04 | Catalogue/niveaux, traits, capacités exactes, slots orbitaux et réaffectation | 2/5 | [Planètes](../01-game-design/planets-colonies.md) |
| Q05 | Technologies, prérequis, parallélisme et changement d'orientation | 6 | [Recherche](../01-game-design/research.md) |
| Q06 | Topologie, départs équitables, distribution des mondes, version du générateur | 7 | [Galaxie](../01-game-design/galaxy.md) |
| Q07 | Coûts/limites d'expansion, habitabilité, contestation, transfert et abandon | 10 | [Colonisation](../01-game-design/colonization.md) |
| Q08 | **Clos produit, futur** : UNKNOWN sans fuite ; DETECTED existence/position approximative ; MAPPED structure durable ; MONITORED dynamique actualisée ; perte MONITORED → MAPPED, last_seen_at et aucun partage automatique | 7/8 | [Fog](../01-game-design/fog-of-war.md) |
| Q09 | Classes/stats, routes, vitesse, cargo, rappel et coût des missions | 9 | [Flottes](../01-game-design/fleets.md) |
| Q10 | Résolution combat, aléatoire, ciblage, retraite, pertes et butin | 12 | [Combat](../01-game-design/combat.md) |
| Q11 | Poids des profils, départs, fréquence et budget des IA | 11 | [IA](../03-technical/ai-engine.md) |
| Q12 | Mesure du ratio 80/20, métriques et format validé de game_data | 5 puis 16 | [Balance](../01-game-design/balance-philosophy.md) |
| Q13 | Ordre simultané, locks, rattrapage, retries et compatibilité des versions | 3 | [Événements](../03-technical/event-engine.md) |
| Q14 | Victoire/défaite, durée d'univers, resets et rattrapage | cadrage MVP | [Progression](../01-game-design/progression.md) |
| Q15 | Validation finale de la navigation proposée étape 4, carte tactile, libellés et tokens | 4 | [UX](../02-ux-ui/information-architecture.md) |
| Q16 | Cadrage identité/session/autorisation 5B clos ; réalisation 5C/5D et reports explicites Q48/Q49/Q55 ; modes et partage futurs distincts | 5B avant 5C/5D | [Sécurité](../03-technical/security.md) |
| Q17 | **Clos comme objectifs non démontrés** : 1 persistent, 200 memberships humaines, 50 sessions, jusqu’à 500 Empires ; p95 lecture <250 ms, mutation <500 ms, erreurs serveur hors métier <0,1 %, worker p95 <2 s/p99 <5 s, handoff p95 <1 s, sondes <100 ms ; benchmark séparé Portal/Game HTTP/workers/PostgreSQL/IA | 3 puis 17 | [Performance](../04-quality/performance.md) |
| Q18 | Contenu exact des relations minimales, hostilité et négociation | 13 | [Roadmap](roadmap.md) |

## Modes futurs : décisions produit closes, réalisation future

| ID | Arbitrage attendu | Référence |
| --- | --- | --- |
| Q19 | **Clos produit, futur** : PRIVATE invisible publiquement par défaut, invitation uniquement, configurable dans ruleset supporté, progression hors connexion, IA possibles après lot IA | [Modes](../01-game-design/game-modes.md) |
| Q20 | **Clos, paramètres initiaux configurables** : SOLO 1 humain ; PRIVATE maximum 8 ; PERSISTENT objectif 200 memberships humaines, référence 50 GameSessions humaines simultanées, à mesurer | [Modes](../01-game-design/game-modes.md) |
| Q21 | **Clos produit, parcours futurs** : Empire partagé autorisé ; profils administrateur d’Empire/opérateur/observateur = ensembles de permissions, jamais bypass ; aucun owner_user_id unique. Bindings/permissions existants 5C/5D | [ADR 0006](../adr/0006-universe-game-instance.md) |
| Q22 | **Clos produit, futur** : SOLO open-ended ; PRIVATE open-ended par défaut ; PERSISTENT sans fin automatique ; aucune durée maximale ni victoire obligatoire MVP | [Modes](../01-game-design/game-modes.md) |
| Q23 | **Clos produit, futur** : quitter retire accès sans supprimer automatiquement Empire/monde ; sans humain Empire dormant, aucune relève IA implicite avant lot IA | [Modes](../01-game-design/game-modes.md) |
| Q24 | **Clos produit, futur** : persistent late join si admissions ouvertes, place, départ valide, ruleset compatible et protection applicable ; nouvel Empire normalement, partage sous Q21 ; PRIVATE invitation et autorisation | [Modes](../01-game-design/game-modes.md) |
| Q25 | **Clos produit, futur** : persistent protection maximum initial 7 jours réels, fin anticipée sur offensive volontaire ; aucune attaque émise/reçue pendant protection, économie/exploration accessibles, aucun bonus caché permanent | [Modes](../01-game-design/game-modes.md) |
| Q26 | **Clos produit** : version ruleset épinglée par Universe (socle existant) ; seule vitesse initiale supportée 1x, autres profils préparables sans activation ; aucune modification silencieuse d’un Universe existant | [Modes](../01-game-design/game-modes.md) |
| Q27 | **Clos produit, futur** : pause SOLO autorisée, PRIVATE accord de tous les humains actifs, PERSISTENT jamais ; gameplay et IA réellement suspendus, maintenance distincte | [Modes](../01-game-design/game-modes.md) |
| Q28 | **Clos produit, futur** : chaque Empire indépendant au départ, aucune équipe/alliance imposée MVP ; partage Empire ≠ alliance | [Modes](../01-game-design/game-modes.md) |
| Q29 | **Clos comme objectif architectural non démontré** : persistent 200 memberships humaines, 50 GameSessions humaines simultanées, jusqu’à 500 Empires humains + IA ; caps configurables, benchmark requis | [Performance](../04-quality/performance.md) |

Q19–Q29 sont clos côté produit le 31/10/2026 (instruction explicite PR #8), non implémentés par
ce correctif. Q14 reste la question générale de progression/fin ; Q02 demeure la protection hors
connexion générale, distincte de la protection nouvel entrant Q25 désormais validée.

## Cadrage actuel des questions

Q16, cadrage historique 1–2 : aucune mutation publique sans identité/contrôle objet/idempotence.
**Évolution validée 2026-10-28** : compte global multi-parties, Membership, Portal/Game séparés,
Accounts DB/Game DB distinctes, pas de SQL Portal→Game, interface interne et GameSession autonome.
Le complément 5B du 29/10 clôt les contrats Q40–Q56 dans les limites du tableau ci-dessous ; les sondes gardent leur contrat.
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

## Défense planétaire — décisions closes, réalisation future ; Q39 appliquée en 5D

| ID | Arbitrage attendu | Référence |
| --- | --- | --- |
| Q30 | **Clos produit, futur** : capacité dédiée du réseau défensif, augmentable, coût réel en espace Colony | [Défense](../01-game-design/planetary-defense.md) |
| Q31 | **Clos produit, futur** : Point Defense / Anti-Ship / Shield / Sensor–Electronic Warfare / Support–Repair ; emplacements SURFACE / ORBITAL | [Défense](../01-game-design/planetary-defense.md) |
| Q32 | **Clos produit, futur** : défense locale planète/orbite, jamais flotte, combat possible avec flotte alliée présente | [Défense](../01-game-design/planetary-defense.md) |
| Q33 | **Clos produit, futur** : réparations ressources + temps + priorités ; recharge de bouclier distincte de réparation structurelle | [Défense](../01-game-design/planetary-defense.md) |
| Q34 | **Clos produit, futur** : NORMAL / ALERT / COMBAT ; consommation Flux selon systèmes/état, dégradation ou désactivation déterministe si insuffisant | [Défense](../01-game-design/planetary-defense.md) |
| Q35 | **Clos produit, futur** : modules OPERATIONAL / DAMAGED / DISABLED / DESTROYED | [Défense](../01-game-design/planetary-defense.md) |
| Q36 | **Clos produit, futur** : ciblage fin conditionné au renseignement ; sinon distribution selon catégorie/exposition/doctrine/arme | [Défense](../01-game-design/planetary-defense.md) |
| Q37 | **Clos produit, futur** : renseignement défense lié à Q08, données datées et vieillissantes | [Défense](../01-game-design/planetary-defense.md) |
| Q38 | **Clos produit, futur** : surface consomme capacité/secteur réel, orbital vrais slots ; coût économique et spatial réel | [Défense](../01-game-design/planetary-defense.md) |
| Q39 | **Clos produit, appliqué en PR #8** : annulation possible ; remboursement théorique queued 100 % / active 80 %, crédit par ressource jusqu’à capacité, excédent définitivement perdu sans réserve ; preview théorique/récupérable/perte et cascade avant confirmation ; atomique/idempotent | [Économie v0.1](../01-game-design/colony-economy-v0.1.md) |

Q30–Q38 : décisions produit closes le 31/10/2026, aucun module/catalogue chiffré ni code défensif
livré. Q39 : nouvelle règle appliquée dans PR #8, remplaçant le refus de stockage de 5A/5D.
Les caps, durées exactes, coûts et seuils futurs restent configurables/balançables ; une décision
close ne prouve jamais son implémentation ni ses performances.

## Historique des arbitrages 5A — 2026-10-28, précisé par la clôture du 31/10/2026

À ce checkpoint historique, Q01 partielle : trois ordres actif inclus, un seul actif, réservation immédiate, remboursement
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
À ce checkpoint 5A, Q16 restait partiellement ouverte. Son cadrage 5B est désormais clos selon le
tableau ci-dessous ; aucune API gameplay ou identité globale factice ajoutée.

## Identité / Portal-Game — clôture du cadrage 5B, 2026-10-29

**Provenance : validation utilisateur explicite pour PR #6**, arbitrages successifs puis bloc final
complet, corrigé sur trois points. **Décisions validées, non implémentées.** Canonique :
[identity-contracts](../03-technical/identity-contracts.md), qui précise [ADR 0008](../adr/0008-control-plane-game-data-plane.md).
La clôture de contrat ne signifie ni livraison ni test fonctionnel. PR #6 est intégrée ; 5C a reçu
son instruction distincte, avec checkpoint documentaire avant code. Aucun début de 5D ni nouvelle fusion.

« Clos 5B » clôt l’arbitrage du contrat indiqué ; « délégué » est un travail technique autorisé pour
le futur lot dépendant, pas une question produit à reposer. « Différé » reste ouvert avec son échéance.

| ID | Décisions désormais closes | Détails techniques délégués | Différé / échéance |
| --- | --- | --- | --- |
| Q40 | **Clos 5B** : email/mot de passe, identité indépendante, Argon2id ; 15–128 caractères/espaces, refus courants/compromis, pas de rotation imposée ; vérification initiale ; reset et changement volontaire avec révocation globale sans auto-login ; flux email avec/sans MFA et invalidations croisées | Bibliothèque/paramètres mesurés, vérification compromis sans mot de passe brut transmis, schémas/transactions — 5C | OIDC supplémentaire futur ; support sous Q48, livraison sous Q49 |
| Q41 | **Clos 5B** : Portal 7 j absolus/72 h inactif, activité explicite classée serveur ; opaque/cookies protégés/rotation ; appareil = profil navigateur ; plafond initial configurable 10 appareils, aucune limite de memberships | Stockage, rattachement sécurisé, comptage concurrent, nettoyage et rotation — 5C | Hôtes/configuration production avant déploiement sous Q47 |
| Q42 | **Clos 5B** : ticket signé asymétriquement, 60 s/unique, liaison compte/appareil/membership/univers/destination/navigateur ; pré-auth 5 min ; consommation atomique, jamais en URL/log/localStorage | Format/algorithme/bibliothèque, claims, schémas, index et tolérance sans extension d’échéance — 5C/5D | Aucun arbitrage produit restant pour ce contrat |
| Q43 | **Clos 5B** : Game 8 h absolues/2 h inactif, bornée par accès ; opaque/isolation univers ; une session compte/appareil/univers partagée par onglets ; plafond initial configurable 10 univers actifs/appareil, jamais memberships | Cookies, comptage/nettoyage concurrents, stockage et recette multi-univers — 5C/5D | Aucun arbitrage produit restant pour ce contrat |
| Q44 | **Clos 5B** : droits 8 h maximum depuis confirmation Portal sans glissement/reset en panne ; refus à échéance ; renouvellement Portal + nouvelle confirmation/handoff ; révocation reçue immédiate | Protocole, bornage dates, renouvellement sérialisé avec révocation — 5C/5D | Preuves de panne/résilience avant API interactive 5D |
| Q45 | **Clos 5B** : retour lobby sans logout ; logout Game seule ; Portal courant et Games du même appareil ; action distincte tous appareils/univers ; état en attente et progression conservée | Ciblage session/appareil/compte, UI et courses avec handoff — 5C/5D | Aucun arbitrage produit restant pour ces portées |
| Q46 | **Clos 5B** : interface interne privée, mTLS, autorisation par service/opération ; proxy authentifié seulement, aucun header client fiable | PKI, rotation/certificats, topologie, limites et recette — 5C avant interface utilisée | Configuration de déploiement avant exposition |
| Q47 | **Clos 5B** : frontend→API même origine, CORS credentials refusé par défaut, exception seulement sur besoin explicite/allowlist minimale ; CSRF et cookies Secure/HttpOnly/host-only, aucun secret localStorage | Noms/SameSite/hôtes locaux, recette navigateur et handoff par navigation POST — 5C/5D | Domaines publics avant déploiement ; autre topologie exige recette adaptée |
| Q48 | **Contrat MVP clos 5B ; support différé** : MFA facultative joueurs, obligatoire privilégiés ; TOTP unique/cinq WebAuthn nommables ; deux WebAuthn avant privilèges production ; step-up par action 5 min/unique ; révocations MFA ciblées, audit/notifications ; dix secours ≥128 bits, récupération 15 min sans Game/admin ; aucun bypass perte totale | Crypto, stockage TOTP chiffré/clé séparée, vérification WebAuthn/RP, enrôlement, preuves, schémas et tests — 5C selon cadrage compte/MFA | Procédures support renforcé joueur/privilégié ouvertes, lot distinct avant activation du service ; compte bloqué sans procédure approuvée |
| Q49 | **Flux clos 5B ; production différée** : vérification initiale 24 h unique/réémission ; reset 30 min/unique/dernier lien ; demande email 1 h unique/preuves liées ; notifications et réauthentification ; livraison persistée/retentée sans faux succès, non-énumération | Adaptateur indépendant du fournisseur, jetons, transactions, signalement de sécurité et tests — 5C | Fournisseur, domaines et réglages d’envoi avant déploiement ; aucun achat/abonnement 5B |
| Q50 | **Clos 5B** : limites compte/IP/opération, ralentissement progressif login/MFA, quotas inscription/email, non-énumération ; aucun verrouillage permanent provoqué par tiers ni CAPTCHA tiers obligatoire au lancement | Seuils configurables documentés et testés — 5C avant exposition publique | Ajout ultérieur d’un prestataire CAPTCHA = décision distincte |
| Q51 | **Clos 5B** : membership unique compte/univers ; binding Empire explicite et permissions consultation/construction/annulation ; aucun droit gameplay admin implicite | Représentation permissions/bindings et contrôles d’objet/fog — 5C/5D | Partage Empire Q21 validé ; profils conceptuels définis, parcours produit et permissions détaillées de modes futurs |
| Q52 | **Clos 5B** : suspension interdit nouveaux handoffs/commandes après application sans arrêter univers ; réactivation par nouvelle décision/handoff sans restaurer sessions | États/révisions et sérialisation droits/commandes — 5C/5D | Règles métier join/leave/late join Q23/Q24 conservées |
| Q53 | **Clos 5B** : Portal intention/Game application ; outbox atomique ; identifiants stables, effets/résultats atomiques idempotents, révisions ordonnées, retry/acquittement/réconciliation ; anti-rejeu conservé | Enveloppes, verrous, délais, déduplication et purge sûre — 5C/5D | Sauvegarde/purge opérationnelles avant production ; pas de purge anti-rejeu au seul TTL audit |
| Q54 | **Clos 5B** : révocations session/appareil/compte/membership ; persistées jusqu’à acquittement ; UI fidèle ; anciennes preuves sans résurrection ; commandes revérifiées à acceptation, progression conservée | Générations/stockage, messages ciblés et courses avec handoff/renouvellement — 5C/5D | Recette de résilience 5D, sans promesse distante instantanée |
| Q55 | **Clos produit le 31/10/2026** : SOLO aucune admission extérieure ; PRIVATE invite only ; PERSISTENT CLOSED / APPROVAL / OPEN ; admission distincte des permissions gameplay | Implémentation des politiques et parcours dans le futur lot modes, scopes existants conservés | Aucun parcours de création/join/admission livré par ce correctif |
| Q56 | **Clos 5B** : validation locale ticket signé, clés publiques prédistribuées ; clé inconnue refusée sans découverte Portal ; ticket déjà émis consommable sous contrôles en panne, révocation reçue prioritaire ; rotation/compromission séparées de S2S | Algorithmes, distribution/rotation, tolérance, rétention anti-rejeu et tests — 5C/5D | Domaines/RP et recette clés avant déploiement |

### Corrections prioritaires du bloc final

- MFA : révocation globale après activation initiale, désactivation, remplacement/suppression réduisant
  ou remplaçant la protection, récupération après perte ou reset MFA. Pas de révocation globale
  imposée pour ajout d’authentificateur ou régénération volontaire des secours avec step-up valide
  via un facteur déjà enregistré ; ces opérations restent sensibles, auditées et notifiées.
- Sessions : 10 appareils/compte et 10 univers Game actifs/appareil sont seulement des paramètres
  techniques initiaux configurables ; ils ne limitent jamais les memberships.
- CORS : chaque frontend appelle sa propre API même origine ; credentials cross-origin refusés
  par défaut, aucune origine autorisée sans besoin explicite et allowlist minimale.

### Reports assumés et condition de sortie

Q48 et Q49 conservent uniquement les reports indiqués. Q55 est close côté admission depuis le
31/10/2026 ; ses parcours produit restent futurs.
Les détails techniques délégués ne sont ni des arbitrages produit manquants ni une implémentation.
Q16 a son cadrage identité/session/autorisation couvert par 5B ; sa réalisation relève de 5C/5D,
les politiques futures liées aux modes restant ouvertes dans leurs propres Qxx.
Aucun arbitrage produit supplémentaire nécessaire au cadrage 5B n’a été identifié à la consolidation.

5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`), contrats partiellement implémentés par C02–C07 sur PR #7, handoff/GameSession C07 livrés sur PR #7.
Historique 5B : seul le cadrage identité/autorisation Q16 avait été actualisé. Le complément
utilisateur du 31/10/2026 clôt les décisions indiquées ci-dessous, sans renuméroter Q01–Q56 ;
lot courant 5D sur PR #8, sans merge ni étape 6.
5B n’a créé aucune table ; C02 ajoute les comptes côté Portal seulement, pas de membership.
