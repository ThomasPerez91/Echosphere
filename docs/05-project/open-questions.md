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
| Q15 | Navigation finale, détails carte tactile, libellés et tokens | 4 | [UX](../02-ux-ui/information-architecture.md) |
| Q16 | Mode d'auth/session futur, contrats d'erreur/idempotence et permissions | 1/2 | [Sécurité](../03-technical/security.md) |
| Q17 | Budgets de performance et charge de référence | 3 puis 17 | [Performance](../04-quality/performance.md) |
| Q18 | Contenu exact des relations minimales, hostilité et négociation | 13 | [Roadmap](roadmap.md) |

## Cadrage actuel des questions

Q16 est cadrée aux étapes 1–2 : pas de mutation HTTP publique tant que identité/session, contrôle
objet et idempotence ne sont pas décidés ; les sondes gardent leur contrat. Elle reste ouverte,
aucune méthode d'authentification n'a été choisie arbitrairement.
Q04 n'est pas fermée par le schéma : les capacités sont fournies explicitement, sans plafond
9–18 ou défaut 12 imposé. Q07 reste ouverte : la table colonies représente l'occupation actuelle,
le cycle de vie et l'historique nécessiteront une migration au lot colonisation.
Q02 est un prérequis du futur combat : aucun endpoint d'attaque ne sera livré avant arbitrage.

## Cadrage technique étape 3 (partiel)

Q03 : micro-unités entières (1 unité = 1 000 000), taux horaires et reste exact persisté. BIGINT non
négatif avec dépassement explicite. Capacité optionnelle saturante sans valeur par défaut de gameplay.
Coûts, rendements, entrepôts et entretien restent ouverts.
Q13 : pour une colonie, ordre due_at/séquence sous verrou, rattrapage à date logique, SAVEPOINT pour
reprise atomique, retries bornés et blocage de tête. L'ordre multi-agrégats, flotte/combat et migrations
de payload/archivage restent ouverts. Détails dans [ADR 0005](../adr/0005-colony-time-engine.md).

## Décisions techniques prises pour le bootstrap

Python 3.12, Node 22 dans Docker, PostgreSQL 17, psycopg direct pour les sondes, proxy Vite même
origin, ports loopback et absence de montage source. Ce sont des choix d'implémentation réversibles,
pas des arbitrages de gameplay. SQLAlchemy/Alembic sont désormais en place pour les cinq premiers modèles, sans endpoint métier.
