# ADR 0007 — Domaine Colony, ruleset par univers et file transactionnelle

Date : 2026-10-28. Statut : acceptée pour l’implémentation Étape 5A ; valeurs de balance provisoires.

## Contexte

Le scheduler générique et le shell sont intégrés. La boucle économique doit réserver les coûts,
respecter l’ordre logique et les capacités, et préparer humain/IA/headless sans endpoint non protégé.
Les niveaux I–V limitatifs sont remplacés par une progression continue. Q16 reste ouverte.

## Décision

Fichiers JSON stricts dans game_data/rulesets/v0.1 : resources, colony, infrastructures. Pas de
dépendance YAML. Tous les champs sont explicites, extras/booléens numériques/versions mélangées et
clés dupliquées sont refusés. Règles validées et copiées une fois par univers ; pas de singleton
métier ou modification implicite des parties lors d’une édition du catalogue. Multiplicateurs
rationnels par instance ; économie/construction actives, recherche/flotte seulement conceptuelles.

Infrastructure : colonie/univers et secteur explicites, unicité du secteur, niveau >=1. Les capacités
de planète et limites configurables sont vérifiées par le service sous verrou de stream, sans
CHECK SQL qui dupliquerait le catalogue. Un changement futur de capacité doit utiliser le même lock
et refuser un retrait de secteur occupé/réservé. Aucun service de redimensionnement dans ce lot.

Ordres séquentiels avec snapshots complets, unicité des clés de commande et index partiel un actif.
Les services n’ont pas de commit : caller transaction + SAVEPOINT par commande, identité/empire
explicites, propriété vérifiée avant accès puis après attente du lock, rattrapage complet avant
mutation. La réservation est immédiate. Les handlers utilisent le stream déjà verrouillé et aucun
autre stream ; l’activation du suivant et son événement sont dans la même transaction.

CONSTRUCTION_COMPLETE s’enregistre dans TimeEngine ; aucun second scheduler. Règlement des stocks
avant changement de production/capacité. Prochaine activation à due_at, pas à l’heure du polling.
Le bonus industriel courant est pris à l’activation ; coût/durée de base/vitesse sont snapshotés.
Un événement d’un autre stream ou univers ne peut pas appliquer l’ordre. Le worker reprend les
échéances PostgreSQL sans joueur connecté. Un événement annulé est acquitté avec error_code cancelled,
sans prétendre que le chantier est terminé ; l’état completed/cancelled métier reste dans l’ordre.

Annulation idempotente : remboursement 100/80 %, upgrades dépendants du même secteur annulés en
cascade, ordre des autres secteurs préservé. Stockage insuffisant pour rendre le montant exact :
refus complet, sans perte ou crédit caché (Q39 ouverte pour validation produit de ce cas limite).

## Conséquences

BIGINT micro-unités, taux horaires/reste et saturation réutilisés ; fractions et arrondis documentés
sans float. Pas de plafond 5. Erreur explicite en dépassement numérique ou de date.
Migration 0004 additive ; downgrade vide réversible, downgrade peuplé refusé avant DDL. Pas de backfill
inventé d’infrastructures sur les anciennes timelines ; migration métier d’un ancien univers hors lot.
Les règles restent auditables et reproductibles ; changer une version d’univers actif demandera une
commande/migration explicite. Une ancienne version doit rester disponible pour nouvelles instances.

Q16 bloque l’API et la partie interactive 5B. Les services internes ne sont pas une autorisation
HTTP ; une future couche vérifiera user/membership/univers/permissions/empire avant leur invocation.
Aucune table/commande de défense anticipée, seulement sa documentation et sa place dans Colony.

## Validation

Tests des vrais fichiers v0.1, niveaux et scaling, arrondis et vitesses, PostgreSQL pour réservation,
concurrence, secteurs/unicité, annulation, crash/reprise, idempotence, activation et stockage. Tests
existants conservés, migrations/absence de dérive et smoke Docker avec données incluses dans l’image.

- [Économie](../01-game-design/colony-economy-v0.1.md) · [Scheduler](0005-colony-time-engine.md)
- [Instance](0006-universe-game-instance.md) · [Questions](../05-project/open-questions.md)
