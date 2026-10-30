# Audit documentaire réel de PR #5

> Mise à jour du 31/10/2026 : le refus de remboursement saturé décrit historiquement ici
> est remplacé par Q39 (plafonnement et perte), et la cascade est validée sous Q01.
> Référence actuelle : [économie v0.1](../01-game-design/colony-economy-v0.1.md).

**Statut : observation vérifiée au départ de la passation, 2026-10-28.** Lecture ciblée du code,
des tests et des preuves GitHub ; pas une certification sécurité, un benchmark ou une nouvelle
exécution locale des tests fonctionnels. Aucun problème de code corrigé dans cette mission.

## État observé

[PR #5](https://github.com/ThomasPerez91/Echosphere/pull/5) ouverte, ready for review, mergeable,
non fusionnée, work/step-5a-colony-domain → master. Tête 5be00da4726abd8fb38bd159deab1f1cf687df52 ;
master 54f928e2348781db43b335d4dcf569aadc0db6e9. Seules ces deux branches sont actuellement listées :
les anciennes work/step-0/1-2/3/4 ont disparu depuis les checkpoints précédents ; aucune suppression
n’a été faite par cette passation. Pas de develop. Aucun thread de revue inline retourné au contrôle.

[CI 40721303421](https://github.com/ThomasPerez91/Echosphere/actions/runs/40721303421) : backend,
frontend et compose-smoke completed/success sur la tête attendue. Le diff 58e8f7c → 5be00da touche
seulement context.md et progress.md (11 ajouts, 4 retraits). Le code fonctionnel reste celui déjà
validé sur [40720967410](https://github.com/ThomasPerez91/Echosphere/actions/runs/40720967410).

## Confrontation des affirmations avec le dépôt

| Affirmation externe | Résultat de la lecture | Preuve canonique |
| --- | --- | --- |
| Scheduler existant réutilisé | Confirmé : TimeEngine enregistre CONSTRUCTION_COMPLETE ; schedule/lock/catch-up existants | [service temps](../../backend/app/simulation/service.py), [service Colony](../../backend/app/colony/service.py) |
| Réservation atomique | Confirmé : lock du stream, catch-up complet, SAVEPOINT, prélèvement et ordre dans la transaction du caller | enqueue/catch_up_owned ; test_insufficient_resources_rolls_back_even_if_caller_catches_error |
| Trois ordres actif inclus | Confirmé : queue_limit=3, comptage active/queued ; index partiel un actif | [colony.json](../../game_data/rulesets/v0.1/colony.json), [modèles](../../backend/app/colony/models.py) |
| Annulation 100/80 et idempotence | Confirmé avec réserve Q39 : état cancelled rejoué sans re-crédit ; refus si remboursement exact impossible | cancel ; test_cancel_queued_full_refund_active_eighty_and_idempotence |
| Concurrence dépense/annulation | Tests présents et inclus dans le job backend vert | test_concurrent_commands_cannot_spend_same_resources, test_concurrent_cancellation_refunds_once |
| Snapshots de ruleset | Confirmé : copie validée par univers, version/quote/vitesse/remboursements par ordre ; fichiers édités sans repricing | configure_universe, OrderSnapshot ; test_editing_catalogue_files_does_not_reprice_existing_orders_or_universe |
| Niveaux >5 | Confirmé : explicit_levels + scaling_after_level, récurrence et refus de dépassement, pas de plafond de design 5 | [rules.py](../../backend/app/colony/rules.py), [tests règles](../../backend/tests/test_colony_rules.py), test_level_six_completion_and_additive_production |
| Isolation Universe | Confirmé : scope univers/empire/colonie, FK composites et validation événement/stream | owned_colony/complete_construction ; tests cross_universe et event_cannot_complete_an_order_from_another_stream |
| Reprise et prochain chantier | Confirmé : fin logique, activation atomique, test crash/restart et bonus industriel au démarrage suivant | [tests Colony](../../backend/tests/integration/test_colony.py), ADR 0005/0007 |

Les noms de tests ci-dessus sont dans [test_colony.py](../../backend/tests/integration/test_colony.py).
Les compteurs publiés sont 101 backend (42 unitaires + 59 PostgreSQL), 11 frontend et 5 Chromium ;
les statuts de jobs ont été relus, les logs détaillés de la précédente livraison figurent au checkpoint.
La nouvelle CI de passation doit être vérifiée séparément avant de la déclarer verte.

## Réserves à garder visibles

- **Q39 — Question ouverte** : refus atomique actuel quand le remboursement ne tient pas. Implémenté,
  pas définitivement validé comme règle produit. Aucun changement dans cette mission.
- **12/2 — Balance provisoire de départ** : initialize_colony exige aujourd’hui les capacités du
  ruleset de référence. Planet stocke déjà ses propres capacités ; ce contrôle n’autorise pas à
  imposer 12 secteurs/2 orbitaux à toute future planète. Un initialiseur général sera un lot futur.
- **Capacité secteur — limite technique réelle** : l’upper bound par capacité de planète est contrôlé
  dans enqueue ; le CHECK SQL de l’infrastructure vérifie positivité et niveau, pas cette relation
  inter-tables. Des écritures SQL directes peuvent la contourner. Les futurs outils/imports devront
  passer par le service ou établir une protection supplémentaire ; Q04 reste ouverte. Pas de correctif ici.
- **Snapshots — limite de portée** : configure_universe est à usage unique côté service ; la copie
  JSONB n’est pas rendue immuable par une contrainte DB. La complétion recalcule les effets depuis
  ce snapshot d’univers. Toute modification directe/migration de ce snapshot devra préserver les
  ordres existants et leurs effets ; aucun endpoint de modification n’existe actuellement.
- **Cascade d’annulation — Implémenté / proposition produit** : les upgrades dépendants sont annulés
  ensemble. Cette politique technique doit rester distinguée du remboursement 100/80 explicitement
  demandé ; confirmation de son UX à reprendre sous Q01, sans modifier le comportement maintenant.

Aucune anomalie bloquante nouvelle démontrée par cette lecture ciblée. Les réserves ne sont ni
masquées par une CI verte ni présentées comme réglées. [Lacunes et risques](known-gaps.md).
