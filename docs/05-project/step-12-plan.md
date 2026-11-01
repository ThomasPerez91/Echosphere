# Étape 12 — Combat MVP

**État courant : COM00 checkpoint post-merge ; COM01 audit en cours.**
Base master `f79d9f6d0c3ebd9d230344b5a0c2aeaef9f4ce6b` : étape 11 Première IA intégrée via PR #14,
CI post-merge 41358533969 success 5/5 vérifiée le 02/11/2026, Q11 close. Branche unique
`work/step-12-combat`, une PR Draft vers master. Claude Code seul écrivain du lot. Aucun merge
autorisé ; étape 13 Relations non commencée.

Sortie roadmap : résolution et rapports militaires simples ; Q02/Q10 arbitrées, simulation et rejeu
des résultats. **Q02 et Q10 sont closes pour le Combat MVP v0.7 seulement** par validation
utilisateur explicite du 02/11/2026 : [décisions transcrites](../01-game-design/combat.md#q02q10--décisions-combat-mvp-v07-02112026).
COM01 n'est pas un gate produit : seule une contradiction structurelle arrêterait le lot.

| Ticket | Travail et preuve attendue |
| --- | --- |
| COM00 | Synchro post-merge, branche, PR Draft, statuts canoniques, transcription Q02/Q10, ce plan |
| COM01 | Audit du code intégré, réponse prouvée à la question de la fence temporelle |
| COM02 | Ruleset v0.7 (copie v0.6, classes militaires, `combat.json`) et résolveur pur déterministe |
| COM03 | Migration 0012, persistance des engagements/alertes/rapports, `combat.read`/`combat.attack` (15) |
| COM04 | Mission ATTACK (lancement sans fuite, défenseur lié, 0 saut, carburant aller-retour), alerte, rappel |
| COM05 | Fence temporelle et orchestrateur Combat `app.combat.worker` hors handler |
| COM06 | Pertes (plus fort reste), DESTROYED, rapports datés, retour |
| COM07 | API et UI (Flottes, System View « Attaquer… », alertes Colony), responsive |
| COM08 | IA v0.7 : objectif défensif `military`, sans offensive |
| COM09 | Concurrence, Fog, rejeu, régressions et compatibilité v0.1–v0.6 |
| COM10 | Recette Compose réelle Combat |
| COM11 | Revue indépendante, CI, docs, passation ; Ready ; aucun merge |

Hors périmètre : étape 13, relations, diplomatie, commerce, conquête, occupation, siège,
bombardement, butin, modules de défense, espionnage, moral, designer, XP, réparation, entretien,
conditions de victoire. Q03, Q04 global, Q14, Q18 et Q25 restent ouvertes ou futures.
