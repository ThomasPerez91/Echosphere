# Étape 6 — Recherche globale d’Empire

**Statut actuel au 31/10/2026 : intégré via PR #9, merge `437844e4`, Q05 close.**
CI post-merge 41152760101 success (5/5) vérifiée. Les consignes de branche/revue ci-dessous
sont historiques ; étape 7 devient le lot courant, étape 8 non commencée.

**Checkpoint antérieur à la fusion : R00–R09 réalisés sur PR #9.**
Une seule branche `work/step-6-research`, une seule [PR #9](https://github.com/ThomasPerez91/Echosphere/pull/9),
base master `0e2ca11322a85452ad6860a4a35099bbc22a4689` (fusion #8, CI post-merge 41144706921 success).
R00 **098ab078889ca7a41b5ed77055663a439670ccdf** publié avant plan et code, puis R01 proposition
**4b74dabbccd028480f58aea4c58106573ba35043**, arrêt respecté jusqu’à validation utilisateur.

Q05 ensuite validée explicitement : [contrat canonique](../01-game-design/research.md),
**Clos produit — implémentation étape 6**. R02–R09 autorisés sans validation intermédiaire, sauf
arbitrage non couvert. Aucun merge ni étape 7. État GitHub réel prioritaire sur ce checkpoint :
si #9 ouverte et mission dessus, reprendre cette branche ; après fusion, considérer Research
intégrée à master et repartir de master synchronisée pour un nouveau lot autorisé.

## Réalisation et critères

| Ticket | Résultat | Validation |
| --- | --- | --- |
| R00 | #8/master/CI vérifiés, branche/checkpoint publiés avant code | Historique 098ab07 et CI PR 41145436851 success |
| R01 | Q05 proposée puis validée explicitement par utilisateur | File 1+1, paiement Colony, 100/80 plafonné, 8 techs, snapshots sans recalcul, pas de laboratoire |
| R02 | Ruleset complet v0.2 et catalogue strict, aucune réécriture v0.1 | Tests de données/versions/coûts/effets/prérequis/cycles/bornage |
| R03 | Migration additive 0007, état/ordres/acquis/stream Empire, FK financières | Upgrade/check/roundtrip ; refus de downgrade peuplé/grants ; tests de scopes/index |
| R04 | Services communs et handler TimeEngine, financement/refund coordonnés, effets Colony | Tests PostgreSQL : file, snapshots, débit unique, plafonnement/cascade, worker, rollback/retry, concurrence |
| R05 | API Game sécurisée et permissions distinctes, allowlists Game/Portal/schéma | Sessions/CSRF/enveloppes/scopes/read/start/cancel et deux participants du même Empire |
| R06 | Écran Research connecté au shell, source explicite, acquis/file/options, confirmations | Vitest et Chromium ; aucun ordre au montage/StrictMode, retry même intention |
| R07 | Mobile/clavier/confirmation/reçus et courses métier | 320/390/768/1440, Escape/focus/viewport, course Research/Colony et workers |
| R08 | Recette HTTPS réelle, navigateur fermé et Portal coupé | `smoke_research_compose.py`, succès CI observé : worker hors page, Portal coupé et effets réels, preuve dans progress |
| R09 | Relecture, docs/passation/PR, validations finales | Relecture/tests/passation réalisés ; Ready for review après CI de tête verte, statut réel dans GitHub ; jamais merge automatique |

## Architecture livrée

[Contrat technique complet/API/UI/recette](../03-technical/research-api-ui.md).
Pas de second scheduler : `RESEARCH_COMPLETE` s’inscrit dans TimeEngine et ScheduledEvent.
État autoritaire par Empire et Universe, EventStream dédié unique, acquis uniques et ordre financier
attaché à sa Colony ; aucune trésorerie Empire ou source automatique. Modèles/FK composites assurent
les scopes, index un actif/un suivant, une technologie non annulée et une clé par Empire.

Transactions : principal Game → Research → sources Colony triées. Les services Colony compatibles
coordonnent Research avant leur propre stream ; la quote métier partagée reçoit les effets acquis.
Le handler Research ne verrouille jamais Colony et ne modifie aucun stock : acquisition unique et
activation de la suivante selon sa durée figée. Les handlers Colony conservent leur indépendance.
Annulation coordonnée, reçus réels, capacité allouée une seule fois, cascade dépendante uniquement.

Ruleset v0.2 complet, v0.1 inchangée et jouable sans Research. Aucun backfill/adoption d’univers actif,
pas de laboratoire/slot supplémentaire ni changement de production continue. Bonus I/II maximum
par effet, coûts et durée effective pris à l’acceptation. Speed/bonus/règles de remboursement
snapshotés ; aucune acquisition ultérieure ne reprice/rechronomètre un ordre accepté.

Permissions `research.read/start/cancel` étendues explicitement dans contrats Game, CHECK SQL,
schéma privé v1 et allowlist Portal ; anciens grants sans nouveaux droits. `colony.read` requis pour
chaque source financière. Aucun besoin de construct, aucun droit admin implicite. Même verrou
principal que les révocations C06 et aucune dépendance HTTP Portal pendant le gameplay.

## Validation et preuves

Local Work : Ruff Game/scripts, suites unitaires, frontend lint/Vitest/build/Chromium et docs exécutés.
PostgreSQL et Docker absents : intégrations et smokes exécutés via CI, aucun succès WSL2 revendiqué.
La CI complète conserve les cinq jobs Game, frontend Game, Portal backend/frontend, Compose.
Recettes antérieures Game/Portal/control/handoff/Colony (dont Q39) conservées et recette Research ajoutée.
Le SHA, runs, nombres et limites réellement observés sont dans [progress](../../progress.md).

Couverture Research : refus de versions/catalogues invalides ; file/duplicates/prérequis ; coûts,
durées et bonus I/II ; source étrangère, source commune et deux sources ; caps et reçu rejouable ;
activation logique et effet unique ; erreur technique sans acquisition partielle ; état métier bloqué
annulable ; même clé concurrente, dernière place et dépense Colony concurrente ; deux workers ;
sessions/CSRF/droits séparés, aucune activité à la lecture et partage Empire sans partage de clé HTTP.
Migration vérifiée sur base jetable, ancienne économie/snapshots préservés.

R08 : projet Compose aléatoire sans ports hôte, bases strictement *_test, droits par contrôle réel,
login/handoff HTTPS. Deux réservations et page fermée jusqu’aux deux achèvements worker ; vérifier
la durée du suivant figée et les effets sur devis Colony. Arrêter Portal API/contrôle, lire et lancer
Research, refermer la page, vérifier acquis/effets puis refuser une session expirée. Aucun intercept.
Fixtures/vitesses de recette strictement test, jamais runtime ou capacité produit de créer une partie.

## Hors lot et sortie

Génération/exploration/galaxie, flottes, colonisation, IA implémentée, combat/diplomatie/défense,
multijoueur complet, laboratoires, portefeuille global, production continue modifiée par Research,
création complète de partie produit et migration générale d’univers existants restent hors lot.
Pas de nouvelle décision Qxx, dépendance ou abonnement nécessaire. Étape 7 seulement sur instruction.
Après revue/CI réellement vertes, rendre PR #9 Ready for review comme autorisé et attendre le merge
explicite. Après fusion, master synchronisée puis recette locale WSL2/Docker/Codex ; ne pas recréer #9.
