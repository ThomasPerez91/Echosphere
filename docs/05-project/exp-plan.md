# Plan EXP — expansion opérationnelle (pré-MVP)

**Statut : plan EXP-00 du 09/11/2026, rédigé par Claude Code sur instruction explicite de
l’utilisateur (chantier confié en autonomie, intégration pré-MVP obligatoire).** Design canonique :
[expansion opérationnelle](../01-game-design/operational-expansion.md). Base de travail :
`recette/ux-weekend` (master ne contient pas encore #16–#29) ; une PR par lot, Draft, vers la
recette tant que master n’a pas reçu la base.

## 1. Audit — état réel au 09/11/2026

| Élément | État | Réutilisation EXP |
| --- | --- | --- |
| Galaxie `galaxy-v1` (`app/galaxy/generator.py`, `world.py`) | 30–50 systèmes, routes sans pont, départs équitables (zone rayon 2, deux sorties, ratio d’équité), générateur pur SHA-256 | Base des opportunités : générateur séparé, monde inchangé |
| Connaissance (`system_knowledge`, `planet_knowledge`, `route_knowledge`) | Fog Q08 côté serveur | Ajout d’une connaissance d’opportunité datée |
| Flottes v0.4+ (`app/fleet/`) | DEPLOY, SURVEY, RETURN, COLONIZE, ATTACK ; une mission ouverte par flotte ; snapshots ; cargo ; déchargement plafonné | Nouvelles missions PROSPECT / EXTRACT / STUDY / PATROL dans le même moteur |
| Trajets (`app/fleet/path.py`, PR #20) | `missions[].path` public | Doctrines : même chemin public, nouveau calcul de contournement |
| 13B (`app/frontier/`, PR #17) | Passages par saut (`fleet_mission_passages`), périodes de protocole, détections, engagements, repli, orchestrateur | Patrouilles, escortes, interceptions successives, furtivité : extensions, pas de second moteur |
| Combat v0.7 (`app/combat/`) | ATTACK planétaire à 24 h, fences, résolveur déterministe | Inchangé ; les rencontres en transit restent celles de 13B (D5) |
| IA v0.6–v0.9 (`app/ai/`) | Utility/Goals, tours 600 s, B08 | Nouvelles familles d’objectifs en v0.10 |
| Rulesets | v0.1–v0.9 figés ; versions codées en dur dans plusieurs validateurs | v0.10 = copie de v0.9 + opportunités ; ensembles de versions à étendre explicitement |

Contraintes relevées : versions de ruleset énumérées dans `colony/rules.py`, `ai/bootstrap.py`,
`ai/rules.py`, `ai/worker.py`, `control/contracts.py` (`start_universe` figé sur v0.9) ; création
Portal (`CREATION_RULESET`) figée sur v0.9 (A5).

## 2. Lots, dépendances et PR

| Lot | Contenu | Dépend de | Testable seul |
| --- | --- | --- | --- |
| **EXP-00** | Design, plan, roadmap, arbitrages A1–A5 | — | Docs |
| **EXP-01a** | Ruleset v0.10 (copie v0.9 + `opportunities.json`), règles validées, générateur pur `opportunities-v1`, tests de déterminisme/distribution/équité | EXP-00 | Oui (tests purs) |
| **EXP-01b** | Tables `galaxy_opportunities`, `opportunity_knowledge`, `discovery_dossiers` ; génération dans `generate_world` pour v0.10 ; signatures révélées à la cartographie ; projection Galaxie/System View sous Fog | 01a | Oui (intégration PostgreSQL) |
| **EXP-02a** | Classe Extracteur ; missions PROSPECT et STUDY ; rapports ; crédit de Données plafonné | 01b | Oui |
| **EXP-02b** | Mission EXTRACT : durée, cargo, réserve, partage au prorata (A3), fin (rester/rentrer), reprise après crash | 02a | Oui |
| **EXP-02c** | Dossiers complets (A4) ; exploitation contestée (A1) | 02b + arbitrages | Oui |
| **EXP-03** | Mission PATROL (circuit, arrêts, protocole pendant l’arrêt), escorte = stationnement à protocole | 13B, 01b | Oui |
| **EXP-04a** | Doctrine Contournement (systèmes évités, chemin serveur, coûts) | PR #20 | Oui |
| **EXP-04b** | Doctrine Furtive (A2 : niveaux, facteur de durée) | Recherche + A2 | Oui |
| **EXP-05** | IA v0.10 : prospection, exploitation, escorte, patrouilles, doctrines | 02b, 03, 04a | Oui (politique pure + intégration) |
| **EXP-06** | UI : panneau système, ordres, patrouilles, doctrines, vue Présence stratégique | lots correspondants | Vitest/Playwright |
| **EXP-07** | Simulations multi-Empires, scénarios A–I, performance, recette | tous | Recette |
| **Bascule** | `start_universe` et Portal en v0.10 (A5) | 02b au minimum | Oui |

Chaque lot backend expose son API et un minimum d’UI quand il devient jouable (pas d’attente
d’EXP-06 pour tout).

## 3. Modèle de données prévu (EXP-01b/02)

- `galaxy_opportunities` (immuable sauf réserve) : univers, système, ordinal, famille, type, rang,
  ressource, réserve initiale et restante (µ-unités), débit maximal/h, durée d’étude, gain de
  Données, dossier/indice éventuel. Verrou de ligne = portée de la concurrence d’extraction.
- `opportunity_knowledge` (par Empire) : niveau (`signature` / `prospected`), valeurs observées et
  `observed_at` ; jamais de valeur courante non observée.
- `opportunity_studies` (Empire × curiosité, unique) ; `discovery_dossiers` + progression par
  Empire.
- `extraction_operations` : mission, gisement, extracteurs engagés, intervalle, extrait réglé
  (µ-unités + reste), état ; règlement à chaque début/fin d’opération du gisement.

## 4. Contrats API prévus

- Galaxie/System View : `opportunities` par système connu (signatures ou détails prospectés,
  datés), sans fuite pour UNKNOWN/DETECTED.
- Flottes : `kind` ∈ PROSPECT / EXTRACT / STUDY / PATROL ; `extract` {duration_seconds, on_end:
  `stay`|`return`} ; `patrol` {systems[], dwell_seconds, protocol} ; `doctrine` ∈ `direct` |
  `stealth` | `detour` et `avoid[]` ; devis serveur avec `path`, durée, Flux, passages.

## 5. Invariants conservés

Serveur autoritaire, dates logiques, micro-unités entières, idempotence, une mission ouverte par
flotte, handlers mono-stream (le verrou du gisement est une portée de concurrence explicite comme
le verrou de planète de la colonisation), Fog côté serveur, IA par les services communs, rulesets
immuables, aucune migration de snapshot existant, aucun balayage de galaxie par mouvement.

## 6. Scénarios de validation (EXP-07)

A expansion économique · B système partagé · C contrôle militaire · D offensive à douze sauts ·
E progression furtive · F contournement · G jeu hors ligne · H crash/redémarrage · I IA équitable
(détail dans l’instruction du 09/11/2026, repris dans les tests de chaque lot).

## 7. Avancement

| Lot | Branche | État |
| --- | --- | --- |
| EXP-00 | `work/exp-00-design` | Rédigé 09/11/2026 |
| EXP-01a | `work/exp-01-opportunities` | Ruleset v0.10, règles et générateur pur livrés, tests purs exécutés |
| EXP-01b | — | Suivant : persistance, génération à la création, Fog, projection |
