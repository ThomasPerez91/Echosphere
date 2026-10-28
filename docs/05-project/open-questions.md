# Registre central des décisions ouvertes

Chaque Q reste ouverte jusqu'à un arbitrage explicite. Les propositions des docs ne la ferment pas.
Consigner date, raison, impact, document modifié et ADR si nécessaire. Les étapes indiquées sont
les moments limites pour décider avant de dépendre du choix.

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

Les lignes suivantes restent **Question ouverte**, aucun protocole ou chiffre n’est déduit :

| ID | Arbitrage restant | Dépendance / référence |
| --- | --- | --- |
| Q40 | Méthode de login, credentials et récupération compte | 5B/5C, [sécurité](../03-technical/security.md) |
| Q41 | Cookie/session Portal, durées et politique de stockage | 5B, sécurité |
| Q42 | Format/expiration du ticket, nonce, audience, usage unique et résistance au rejeu | 5B, ADR 0008 |
| Q43 | Durée, stockage et limites de GameSession | 5B avant 5D, ADR 0008 |
| Q44 | Refresh, expiration et révocation en fonctionnement normal ou panne Portal | 5B, ADR 0008 |
| Q45 | Logout global vs logout Game et effets sur les autres parties | 5B/5C, compte multi-parties |
| Q46 | Auth service-to-service et exposition réseau de l’interface interne | 5B, aucun mTLS/signature/credential choisi |
| Q47 | CSRF, origines, cookies et politique CORS liée au découpage | 5B/5C/5D, sécurité |
| Q48 | MFA et récupération associée | Cadrage 5B, implémentation selon périmètre |
| Q49 | Fournisseur email, verification et récupération | 5B/5C |
| Q50 | Anti-bot/CAPTCHA, limites IP/compte et protections brute force | 5B/5C, pas de produit choisi |
| Q51 | Modèle exact rôles/permissions et contexte empire | 5B, sans fermer Q21 |
| Q52 | Membership suspendu, reprise et droits lors d’un accès Game | 5B, compatible Q23/Q24 |
| Q53 | Synchronisation Portal/Game, ordre/retries, autorité des droits et réconciliation | 5B avant provision/join |
| Q54 | Révocation pendant GameSession, propagation et limites en panne Portal | 5B, autonomie sans promesse d’instantanéité |
| Q55 | Politique d’accès/sécurité des univers privés et persistants | 5B puis lots modes, Q19–Q29 préservées |
| Q56 | Validation autonome du ticket, clés/rotation et dépendances de handoff en mode dégradé | 5B, format crypto non décidé |

12 secteurs/2 slots orbitaux concernent seulement le départ de référence v0.1 ; distribution et
capacités variables futures restent Q04/Q06. Q39 reste ouverte. Q01–Q39 ne sont ni supprimées,
renumérotées ni fermées par cet ajout. Les comptes/memberships restent sans nouvelles tables.
