# Étape 13 — Relations IA minimales

**État courant : R02–R10 implémentés sur la PR #16 (Draft) ; validation locale PostgreSQL, Alembic,
Chromium et Compose réussie le 02/11/2026 ; R11 (revue indépendante, Ready) à faire. Q18 close le
02/11/2026. Aucun merge.**
[Contrat technique](../03-technical/relations-api-ui.md).
Base master `067a4e58863b910785764591d8bf3af4b0ec18e0` : étape 12 Combat MVP intégrée via PR #15
(tête `589ce60`), merge du 02/11/2026, CI post-merge 41375165508 success sur `067a4e5`
(backend, frontend, portal-backend, portal-frontend, compose-smoke ; `static-checks` sauté par
conception sur push master). Branche unique `work/step-13-ai-relations`, une PR Draft vers master.
Claude Code seul écrivain du lot. Aucun merge autorisé.

Sortie roadmap : interactions compréhensibles entre civilisations ; Q18 arbitrée, pas de diplomatie
avancée anticipée. **Q18 close pour l'étape 13** : [décisions validées](../01-game-design/relations.md#q18--validation-avec-amendements-02112026)
(la proposition R01 reste historique). R01 était un gate produit, levé par cette validation.

| Ticket | Travail et preuve attendue (R02–R10 réalisés, R11 en attente de validation locale) |
| --- | --- |
| R00 | Synchro post-merge PR #15, branche, statuts canoniques, ce plan ; checkpoint publié avant code |
| R01 | Audit du code intégré `067a4e5`, proposition Q18 (B1–B12) ; validée avec amendements, cadrage 13B documenté |
| R02 | Ruleset v0.8 (copie v0.7, `relations.json`, `ai.json` v3) et règles pures de relation |
| R03 | Migration 0013 (métier non destructive, extension contrôlée du CHECK des droits) : contacts, relations, journal, `relations.*` (17) |
| R04 | Sources de contact : rapports de combat et colonie étrangère dans un système MONITORED |
| R05 | Négociation : proposer/retirer/accepter/refuser/rompre, idempotence, échéances logiques |
| R06 | Intégration Combat : pacte effectif à `battle_at`, issue `voided_by_pact`, rapports/alertes |
| R07 | API et UI section Relations (liste, détail daté, actions), responsive/clavier |
| R08 | IA policy v3 : famille `diplomacy`, poids validés, réponses prioritaires, aucune offensive |
| R09 | Concurrence, Fog/non-fuite, rejeu, régressions et compatibilité v0.1–v0.7 |
| R10 | Recette Compose réelle Relations (humain + 2 IA, Portal coupé) |
| R11 | Revue indépendante, CI, docs, passation ; Ready ; aucun merge |

Hors périmètre validé : alliances, commerce, tribut, transfert de ressources/colonies/flottes,
partage de Fog, messagerie libre, vote, conquête, protection Q25, offensive IA, dialogue génératif.
**Lot 13B ([premier contact](../01-game-design/first-contact.md), Q57/Q58) documenté mais exclu** :
aucun champ de protocole, nouvelle mission, technologie d'espionnage, furtivité, événement de
passage, auto-interception/embuscade/repli, worker de patrouille, UI de protocole ni ruleset v0.9. Q03, Q04 global, Q14, Q25 et Q30–Q38 inchangées.

## R00 — reprise post-merge Combat, 02/11/2026

- PR #15 fermée et fusionnée (merge `067a4e5`, parents `f79d9f6` et `589ce60` = tête de
  `work/step-12-combat`). Aucune PR ouverte, aucune branche `work/step-13*` distante préexistante.
- Full CI post-merge 41375165508 vérifiée par l'API GitHub : 5 jobs success sur `067a4e5`.
- Clone neuf de `master` = `origin/master` = `067a4e5`, arbre propre ; branche créée depuis ce SHA.
  Aucun travail local d'un autre agent dans ce répertoire.
- Statuts « lot courant » mis à jour : étape 12 historique, étape 13 courante.

## R01 — audit du code intégré (master `067a4e5`)

Lecture : vision, IA, Combat, Fog, modes, Exploration/System View, Flottes, contrats Combat et IA,
registre. Seul le code fait preuve d'implémentation. Aucun test runtime relancé pour R01.

### Constats prouvés

- **Aucune notion de relation ni de contact.** `Empire` ne porte que `name` et `controller_type`
  (`backend/app/persistence/models.py:48`). Aucune table, règle ou permission ne lie deux Empires.
  Le Combat v0.7 est donc une **hostilité universelle implicite** : tout Empire disposant de
  `combat.attack` peut viser toute planète connue (`app/fleet/service.py:705`, `check_attack`, ne
  refuse que sa propre colonie).
- **Non-fuite au lancement d'ATTACK.** L'occupant est lu sous verrou Planet et lié en interne comme
  défenseur (`service.py:838-842`, `open_engagement` `:903`) ; rien n'est renvoyé à l'attaquant.
  Une règle de relation vérifiée au lancement révélerait l'occupant : elle est exclue.
- **Seule source d'identité étrangère : les rapports de combat après bataille.**
  `app/combat/orchestrator.py:167` crée un rapport pour chaque camp nommant l'adversaire.
  L'issue `unopposed` ne produit qu'un rapport attaquant sans identité adverse (`:162`).
  L'alerte défenseur (`app/combat/service.py:87`) ne révèle pas l'attaquant.
- **Aucune présence étrangère projetée.** System View ne publie que les colonies propres
  (`app/galaxy/system_view.py:57-97`, `kind: own_colony`) ; MONITORED n'existe qu'autour d'une
  colonie propre (Exploration). Une colonie étrangère voisine, même dans un système MONITORED, est
  invisible aujourd'hui : un « contact » par proximité exigerait une extension Fog (arbitrage B3).
- **IA sans capacité offensive ni mémoire d'adversaire.** Buts v0.7 = 5 familles + `military`
  défensif (`app/ai/rules.py:11`) ; aucun candidat offensif (`app/ai/observation.py:551`) ;
  la mémoire ne garde que `target_unavailable` (`observation.py:129-146`). Ajouter une famille ou
  un poids change la somme 100 des profils : nouveau `ai.json`, donc nouveau ruleset.
- **Permissions :** 15 droits (`app/control/contracts.py:11`), dont `combat.read/attack`.
  Toute action de relation demandera de nouveaux droits Portal/Game et une migration.
- **UI :** la section `#relations` existe comme espace réservé sans données (`frontend/src/App.tsx:22`).
  Aucune maquette Relations dans `docs/visual-reference` : composition à dériver du design system.

### Contradictions et contraintes

Aucune contradiction bloquante. Contraintes structurantes pour Q18 :
1. une relation ne peut **jamais** filtrer ATTACK au lancement (non-fuite) ; son effet ne peut
   s'appliquer qu'à `battle_at`, quand le rapport révélerait de toute façon l'adversaire ;
2. l'effet d'une relation sur une bataille doit dépendre de **dates logiques** (acceptation,
   rupture, `battle_at`), jamais de l'ordre de traitement des workers ;
3. une commande de relation touche deux Empires : elle ne doit verrouiller aucun stream
   d'opérations (ni d'autre Empire), seulement une ligne de relation par paire canonique ;
4. Q08 interdit tout partage automatique de Fog, même sous accord ;
5. v0.1–v0.7 et leurs snapshots restent inchangés : relations seulement en v0.8 explicite.

### Architecture proposée (conditionnelle à Q18)

- **Données :** `empire_contacts` (observateur, observé, source, `first_seen_at`, `last_seen_at`),
  `empire_relations` par paire canonique (UUID min/max, état, `accepted_at`, `ends_at`), journal
  immuable des propositions/réponses/ruptures. FK et scope par univers ; aucun état dérivé non daté.
- **Commandes :** verrou de la seule ligne de paire (créée à la demande, `ON CONFLICT`), clé
  d'idempotence par Empire ; aucune prise de stream d'opérations, Research ou Colony. Échéances
  (expiration 72 h, fin de préavis) évaluées par comparaison de dates à la lecture/commande :
  aucun ScheduledEvent multi-Empire.
- **Combat :** l'orchestrateur, sous ses verrous existants (streams triés → engagement), lit la
  ligne de paire en `FOR SHARE` et applique la règle des dates logiques. Ordre global :
  streams → engagement → relation ; une commande de relation ne prend jamais de stream, donc aucune
  inversion possible.
- **Contacts :** créés dans la transaction qui produit le rapport de combat ; présence étrangère
  (B3) produite par la projection Knowledge du système MONITORED de l'observateur.
- **IA :** observation bornée aux propres contacts/relations/propositions, curseur circulaire de la
  famille `diplomacy` ; dispatcher limité aux commandes de relation via les services communs.
