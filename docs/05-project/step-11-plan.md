# Étape 11 — Première IA stratégique

**Statut : AI00/AI01 documentaires autorisés le 01/11/2026 ; Q11 ouverte.**
Base master `a33a452b416ec83d4e8b91d84292913d18db5a40`, PR #13 fusionnée ; CI post-merge
41340653571 success 5/5 vérifiée. Branche unique `work/step-11-first-ai`, PR Draft vers master.
Codex local seul écrivain autorisé. Ancienne branche Colonisation conservée, aucun merge.

| Ticket | Périmètre et gate |
| --- | --- |
| AI00 | Synchronisation post-merge, statuts canoniques, commit/push documentaire avant code IA |
| AI01 | Audit indépendant du code intégré, Q11 proposée, architecture proposée et plan AI02→AIxx |
| AI02→AI11 | Plan détaillé ci-dessous après audit ; entièrement conditionnel à validation explicite Q11 |

Sortie roadmap : Utility/Goals et profils simples ; services communs, décisions reproductibles,
connaissance limitée. Aucun code engageant à AI01 : ni tables/profils exécutables, worker,
scheduler, migration ou ruleset IA. Pas de Combat étape 12. Aucun LLM stratégique, spawn gratuit,
privilège implicite controller_type, connaissance omnisciente ou budget inventé comme validé.

Lectures et audit : produit/économie/fog/flottes/colonisation/recherche ; services et projections,
GameSession/permissions/Portal-Game ; worker/TimeEngine/EventStream ; règles v0.1→v0.5,
modèles/migrations/tests/recettes. Seul le code réellement intégré fait preuve d'implémentation.

AI01 doit séparer constats prouvés (SHA et fichier:ligne), risques/décisions ouvertes et proposition.
Validation de cette mission docs : check_docs/liens, diff/confidentialité ; CI effective observée,
aucune suite runtime présentée comme relancée. Après publication AI01 : arrêt pour validation Q11.

## AI01 — audit et proposition publiables, 01/11/2026

AI00 publié avant code : `6a09b07ae34d36020867dfb4815e521a5d2d2fbd`.
[PR Draft #14](https://github.com/ThomasPerez91/Echosphere/pull/14), base master a33a452.
Audit indépendant du code intégré et preuves fichier:ligne :
[moteur IA](../03-technical/ai-engine.md#ai01--audit-du-code-intégré).
[Q11 proposée A1–A10](../01-game-design/artificial-intelligence.md#arbitrages-demandés-avant-ai02).
**AI01 terminé pour proposition ; arrêt obligatoire avant AI02, Q11 non validée.**

Services métier déjà communs et projections Knowledge réutilisables ; frontières restantes :
principal interne limité, collecteur/décideur sans ORM, persistance/reprise des décisions, bootstrap
équitable. AI_TURN multi-stream écarté dans l'architecture proposée au profit d'un orchestrateur
Game hors handler. Zéro code IA, table, migration, JSON exécutable ou activation à AI01.

## AI02 → AI11 — plan proposé, entièrement conditionnel

Aucune ligne ci-dessous n'autorise son implémentation avant validation explicite de Q11 et de la
suite. Les paramètres sont ceux de la proposition, à adapter aux amendements validés.

| Ticket | Résultat à livrer après validation | Preuve pertinente |
| --- | --- | --- |
| AI02 | Contrat Q11 validé/provenance ; ruleset complet v0.6, profils/cadence/budgets/fonctions d'utilité stricts et versionnés ; aucune réécriture v0.1–v0.5 | Chargement réel, extras/versions refusés, comparaison des anciens rulesets/snapshots, scores entiers et profils différenciés |
| AI03 | Contexte serveur IA par contrôleur, capabilities exactes, collecteur DTO borné et dispatcher vers services communs ; extraction des projections/contrôles HTTP seulement si nécessaire | Coûts/prérequis/refus identiques, aucun privilège controller_type ou User factice ; variations des mondes cachés sans effet sur les entrées/choix |
| AI04 | Migration Game additive proposée 0011 : contrôleurs, séquences/tours/traces et mémoire minimale, FK scopes, index des rendez-vous, unicité de décision ; aucun nouvel inventaire de ressources/unités | Upgrade/check/roundtrip base *_test ; downgrade peuplé refusé, pas de backfill/activation des Empires existants |
| AI05 | Orchestrateur persistant hors handler, horloge injectée, ordre de locks, coalescence des créneaux manqués, une commande/tour, retry/blocked et pause/reprise ; CLI explicite du même monolithe | Deux processus, crash avant/après commit, même intention, aucun second stream pris par un handler ; aucune décision sur catch-up incomplet, aucun recul de curseur |
| AI06 | Utility/Goals pur et projets multi-décisions : économie de départ/fondation, recherche, production, SURVEY, préparation/chargement/COLONIZE, ravitaillement utile propre, WAIT et échec générique mémorisé | Observation/profil/date/mémoire figés → mêmes décisions ; bootstrap sans revenu, stocks insuffisants, file pleine, mouvements en cours, cible indisponible, pas d'unités offertes |
| AI07 | Service/CLI Game d'initialisation de nouveaux univers v0.6, humain et IA au même instant/sites distincts par ordinal canonique, contrôleurs explicitement activés, isolation du processus IA et limites de pool/CPU | Rejeu de bootstrap même contenu, conflit sans perte, sites occupés/insuffisants refusés ; anciens univers intacts, aucune dépendance des fixtures *_test ou du Portal par tour |
| AI08 | Scénarios headless bornés sur vrais services, horloge avancée explicitement ; manifeste d'identités/versions/seed/entrées et traces privées rejouables, aucune UI de debug omnisciente | Plusieurs cycles et deux profils ; ressources produites/dépensées et unités fabriquées, exploration puis fondation réelles ; rejeu d'un tour, pas de promesse d'identité multi-bases par seed seule |
| AI09 | Régressions/sécurité/concurrence et mesure de budgets : pagination équitable, refus, pause, vieillissement Knowledge, multi-univers, croissance de fichiers/traces et retards | PostgreSQL dédié ; transformation de données étrangères n'altère aucun choix ; tours limités avant matérialisation ; création d'une Colony pendant catch-up, saturation de file/stockage, contention avec le worker |
| AI10 | Recette Compose isolée nouvelle : humain réel + IA provisionnées, page fermée, redémarrage orchestrateur/worker, Portal arrêté, session humaine expirée, état DB avant lecture ; observabilité privée | Aucun crédit ni flotte placés pour aider l'IA ; comptes seulement humains ; durées de test explicitement distinctes, progression autonome prouvée. Smokes précédents conservés |
| AI11 | Revue, docs/passation, suites/CI du SHA final, limites de balance/charge déclarées ; PR unique éventuellement Ready après preuves | Game PostgreSQL complet, Portal si contrat touché, Alembic, lint/Vitest/build/Chromium existants, docs/diff, tous smokes CI ubuntu-24.04 ; aucun merge ni étape 12 |

AI05 ne dépend pas d'un nouveau type ScheduledEvent qui ferait des appels multi-streams. Les
événements d'achèvement Colony/Research/Fleet restent exécutés par TimeEngine, sans credential
ni présence utilisateur. La pause des décisions ne doit pas interrompre les ordres déjà acceptés.

### Critères de sortie fonctionnels et preuves à construire

- **Services communs :** mêmes devis, débits, droits d'action, files, snapshots, refus et coûts
  qu'une action humaine comparable. Aucun setter de stock, stack ou Knowledge dans la politique.
- **Connaissance limitée :** UNKNOWN jamais visible ; DETECTED sans structure, MAPPED durable,
  MONITORED propre daté ; rapport d'échec COLONIZE sans occupant. Le collecteur est la seule
  frontière DB du décideur, pas un module de découverte supplémentaire.
- **Reproductibilité :** trace canonique versionnée rejouable ; candidats ordonnés, égalités
  départagées explicitement ; pas de dépendance au hash Python/ordre SQL/heure implicite.
  Même seed sans manifeste d'identités et horaires n'est pas un test de rejeu suffisant.
- **Autonomie économique :** chaque profil démontre une chaîne financée de construction,
  recherche, production d'une sonde, SURVEY, fabrication/chargement d'un colonisateur, COLONIZE
  et démarrage de la nouvelle colonie ; aucun spawn compensatoire. Les besoins de recette ne
  changent pas rétroactivement une règle ou un ruleset de production.
- **Reprise :** deux orchestrateurs ne commandent qu'une fois par tour ; WAIT/refus/commande et
  prochain rendez-vous sont durables ; blocage, coupure avant/après commit et longue absence
  restent bornés, sans rattrapage stratégique antidaté. Portal et sessions humaines non requis.
- **Budgets :** mesurer p95 du décideur et du tour, compteurs de requêtes/candidats/flottes,
  durée de locks, décisions WAIT/refus, débit et rétention des traces. Le 500 Empires futur de
  Q17 n'est pas une cible démontrée par un scénario 1 humain + 2 IA sur 40 systèmes.

## Validation réellement faite à AI00/AI01

- Lecture/audit sur a33a452, comparaison JSON v0.1→v0.5 et inventaire migrations/models/handlers.
- `python3 scripts/check_docs.py` et `git diff --check` exécutés ; aucun changement runtime.
- CI post-merge 41340653571 success 5/5 observée : 364 Game, 124 Portal, 81 Vitest/31 Chromium
  Game ; recettes Compose existantes réussies. Ces chiffres sont ceux de la CI lue, pas d'une
  exécution locale AI01 ni d'un test IA.
- CI de la nouvelle tête documentaire : état exact à consigner dans la PR après push. PR
  laissée Draft pour Q11 ; ni suite IA, ni benchmark, ni recette d'autonomie encore exécutés.
