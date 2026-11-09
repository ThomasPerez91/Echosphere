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
| **EXP-00** | Design, plan, roadmap, arbitrages A1–A5 (tranchés le 09/11) | — | Docs |
| **GAL-2** | `galaxy-v2` en v0.10 : impasses et goulots, graphe connexe, départs non isolés, tailles 100–2 000 et plafonds Q61 ; création Portal/Game en v0.10 | EXP-01a | Oui |
| **EXP-01a** | Ruleset v0.10 (copie v0.9 + `opportunities.json`), règles validées, générateur pur `opportunities-v1`, tests de déterminisme/distribution/équité | EXP-00 | Oui (tests purs) |
| **EXP-01b** (après GAL-2) | Tables `galaxy_opportunities`, `opportunity_knowledge`, `discovery_dossiers` ; génération dans `generate_world` pour v0.10 ; signatures révélées à la cartographie ; projection Galaxie/System View sous Fog | 01a | Oui (intégration PostgreSQL) |
| **EXP-02a** | Classe Extracteur ; missions PROSPECT et STUDY ; rapports ; crédit de Données plafonné | 01b | Oui |
| **EXP-02b** | Mission EXTRACT : durée, cargo, réserve, partage au prorata (A3), fin (rester/rentrer), reprise après crash | 02a | Oui |
| **EXP-02c** | Dossiers complets (A4) ; exploitation contestée (A1) | 02b + arbitrages | Oui |
| **EXP-03** | Mission PATROL (circuit, arrêts, protocole pendant l’arrêt), escorte = stationnement à protocole | 13B, 01b | Oui |
| **EXP-04a** | Doctrine Contournement (systèmes évités, chemin serveur, coûts) | PR #20 | Oui |
| **EXP-04b** | Doctrine Furtive (A2 : niveaux, facteur de durée) | Recherche + A2 | Oui |
| **EXP-05** | IA v0.10 : prospection, exploitation, escorte, patrouilles, doctrines | 02b, 03, 04a | Oui (politique pure + intégration) |
| **EXP-06** | UI : symboles de flottes sur la carte et fenêtre de flotte (changement de mission, déplacement avec carte « Choisir une destination »), panneau système, ordres, patrouilles, doctrines, vue Présence stratégique | lots correspondants | Vitest/Playwright |
| **EXP-07** | Simulations multi-Empires, scénarios A–I, performance, recette | tous | Recette |
| **Bascule** | Intégrée à GAL-2 (A5 remplacé : tout en v0.10) | — | — |

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
| Galaxie v2 + bascule v0.10 | `work/galaxy-v2` (PR #33) | Livrés : impasses, goulots, tailles 100–2 000, start_universe/Portal en v0.10 |
| EXP-01b | `work/exp-01b-opportunities` | Livré : tables `galaxy_opportunities` / `opportunity_knowledge` (migration 0015), génération avec le monde v0.10 (insertion groupée), signatures à la cartographie, détails datés après prospection, onglet « Données » |
| EXP-02a | `work/exp-02a-prospect-study` | Livré : classe Extracteur, missions PROSPECT/STUDY (migration 0016), Données d’étude en soute, offres « Prospecter » / « Étudier » sur la carte |
| EXP-02b | `work/exp-02b-extract` | Livré : mission EXTRACT, chantiers partagés au prorata (migration 0017), arrêt sur rappel, offre « Extraire » |
| EXP-02c | — | Suivant : dossiers complets (A4), exploitation contestée (A1), flottes civiles destructibles |

## 8. EXP-01b — contrat de projection (09/11/2026)

Galaxie et System View, systèmes MAPPED/MONITORED d’un univers v0.10 seulement :
`opportunities: {signatures, known[]}`. `signatures` = opportunités du système non encore
prospectées par cet Empire ; `known[]` = `{id, family, kind, tier, observed_at}` plus, pour un
gisement, `resource`, `reserve` (µ-unités observées à `observed_at`), `throughput_per_hour`, et pour
une curiosité `study_seconds`, `data`, éventuellement `dossier`/`clue`. Un système DETECTED n’a
jamais ce champ (refusé par le client comme fuite de Fog). Les rapports de cartographie stockés
restent inchangés. La génération écrit les mondes par lots (identifiants explicites, une insertion
par table) pour qu’une carte de 2 000 systèmes tienne dans la transaction de démarrage.

## 9. EXP-02a — contrat PROSPECT / STUDY (09/11/2026)

Deux analyses du moteur de missions Flottes, ruleset v0.10 seulement (`exploitation_unavailable`
sinon) ; mêmes invariants que SURVEY : chemin serveur sur routes connues (0 saut possible dans le
système courant, sans carburant), analyse après l’arrivée, résolution par le handler d’opérations de
l’Empire, droits `fleet.command` + `galaxy.read`.

- **PROSPECT** (`destination_id`) : unités de relevé seules (`survey_units`), système MAPPED+
  (`system_not_mapped`), durée d’analyse `operations.prospect_seconds`. Effet : chaque opportunité du
  système devient connue de l’Empire, réserve datée (`observed_at`, `observed_reserve`) ; une
  nouvelle prospection rafraîchit la valeur. Ne modifie jamais la ligne partagée.
- **STUDY** (`target_opportunity_id`, destination facultative = système de la curiosité) : curiosité
  prospectée et jamais étudiée par l’Empire (`opportunity_not_found` 404 indistinct, `already_studied`),
  une sonde ou un extracteur engagé (`study_units`), soute libre ≥ récompense (`cargo_insufficient` :
  une étude ne perd jamais une partie de son résultat). Durée `study_seconds`. Effet : ligne
  `opportunity_studies` (une par Empire et curiosité), Données chargées dans la soute, déchargées par
  la commande habituelle ; progression de dossier rapportée (`index`, `clues`, `studied`).
- Classe **Extracteur** (cargo 400, non militaire, sans relevé) : définie et validée, utilisée par EXTRACT
  en EXP-02b. Valeurs de balance provisoires (`opportunities.json` → `operations`).
- Carte : « Prospecter » sur un système portant des signatures ou des opportunités connues ;
  « Étudier : <curiosité> » par curiosité non étudiée (flotte entière, sa soute rapporte les Données).

## 10. EXP-02b — contrat EXTRACT (09/11/2026)

Règles validées appliquées : partage entre Empires neutres selon les extracteurs présents et la
capacité de transport (A3 remplacé) ; entre ennemis, l’affrontement relève d’EXP-02c (A1 remplacé).

- **Lancement** : `target_opportunity_id` = gisement prospecté par l’Empire (`opportunity_not_found`
  sinon, sa réserve actuelle restant inconnue), `duration_hours` entier de 1 à
  `operations.extract_max_hours` (`invalid_request`), au moins un extracteur (`extract_units`), soute
  libre > 0 (`cargo_insufficient`). La flotte entière part (escortes et cargos ajoutent protection et
  soute). Chemin serveur, 0 saut possible, carburant selon la règle des missions existantes.
- **Durée prévue** = min(heures choisies, temps pour remplir la soute seul au débit
  min(extracteurs × `extraction_per_hour`, débit du gisement)) ; la concurrence ne fait que ralentir.
- **Chantier** (`deposit_claims`, migration 0017) : créé au lancement, actif de l’arrivée à la fin
  prévue ; aucun premier arrivé propriétaire ; jamais visible d’un autre Empire.
- **Règlement** : la ligne du gisement porte `settled_at` et `settle_remainder`. Lancement, fin ou
  rappel verrouillent la ligne du gisement (`FOR UPDATE`, jamais le stream d’un autre Empire) et
  règlent `[settled_at, date]` par segments entre bornes de chantiers : offre = débit × durée (reste
  sous la µ-unité conservé) ; demande = extracteurs × taux × durée, plafonnée par la soute libre ;
  partage au prorata des extracteurs avec redistribution de la part d’un chantier plein ; réserve
  jamais négative. Chaque date de règlement arrondit une fois de plus (au plus une µ-unité par date) :
  résultat fonction des dates persistées seulement, jamais de l’Empire qui règle.
- **Fin** : à l’échéance, le crédit final est chargé en soute. Choix au lancement (`after`) :
  `STAY` (défaut, la flotte reste dans le système) ou `RETURN` (validé par l’utilisateur le
  09/11/2026 : retour automatique vers le système de départ, durée = trajet aller, carburant
  aller-retour payé au lancement comme une attaque ; rapport au retour). Rappel pendant le trajet :
  retour symétrique, fenêtre vide ; rappel pendant l’extraction : arrêt immédiat, ce qui est extrait
  est chargé, puis séjour ou retour selon le choix ; rappel pendant le retour : refusé.
- **Interface** : « Extraire : <gisement> » sur la carte, durée réglable et choix « Rester sur place »
  / « Revenir au point de départ » dans l’étape « Unités » (bornes d’affichage 1–24 h, le serveur
  applique le ruleset).
