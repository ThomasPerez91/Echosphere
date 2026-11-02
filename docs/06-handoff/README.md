# Passation Space Game / Echosphere

**Statut : documentation durable, mission du 2026-10-28, protocole multi-agents du 2026-10-30.**
GitHub est la source de vérité partagée pour ChatGPT Work, Codex local et Claude Code local ; un
historique de chat n’est pas nécessaire pour reprendre le périmètre consigné. Cette passation n’est pas un export complet des conversations du projet.

## Reprise en sept lectures

1. [AGENTS](../../AGENTS.md) : procédure commune et autorisations.
2. [Contexte](../../context.md) : invariants stables et frontière de mission.
3. [Progression](../../progress.md) : dernier checkpoint vérifiable et prochaine action.
4. [Carte des sources](source-map.md) et [index des décisions](decision-status.md).
5. [Roadmap](../05-project/roadmap.md) et [questions ouvertes](../05-project/open-questions.md).
6. [Vision](../00-product-vision.md), références métier du prochain lot et [ADR](../adr/README.md).
7. [Protocole de collaboration et revue croisée](work-codex-handoff.md), [audit #5](pr-5-audit.md),
   [lacunes/risques](known-gaps.md).

## Ce qui est et n’est pas livré

**Implémenté et intégré sur master par PR #5** : fondations, scheduler, shell, domaine Colony v0.1 interne.
Fusion vérifiée le 2026-10-29 : master 8214e0b, CI verte. L’ancien checkpoint de passation
décrivait #5 ouverte ; il reste historique. Vérifier GitHub réel avant d’agir.
**Décisions validées, futures** : compte global, multi-parties, Portal/Game isolables,
Accounts DB/Game DB séparées, interface interne contrôlée et GameSession autonome après handoff.
**Intégré via PR #7 (`ff6ef89`)** : [socle Portal C01](../03-technical/portal-foundation.md), backend/frontend,
Accounts DB et HTTPS local ; [C02](../03-technical/portal-registration.md) ajoute inscription,
Argon2id, vérification et email durable local. [C03](../03-technical/portal-sessions.md) ajoute connexion/sessions Portal, CSRF et intentions de logout.
[C04](../03-technical/portal-account-security.md) ajoute opérations sensibles sans MFA, step-up et logout global.
[C05](../03-technical/portal-mfa.md) ajoute MFA TOTP/WebAuthn, secours et récupération limitée.
[C06](../03-technical/portal-game-control.md) ajoute lobby, outbox et contrôle mTLS, droits effectifs
et marqueurs de révocation acquittés par Game.
[C08](../03-technical/portal-game-ui.md) intègre le contexte au shell et les parcours ;
[C09](../03-technical/portal-operations.md) porte la recette de panne/reprise et de clôture.
**Intégrée via PR #8 (`0e2ca11`)** : [5D API/UI Colony](../03-technical/colony-api-ui.md), première boucle jouable.
**Non implémenté** : création de partie produit et systèmes futurs du MVP (galaxie, flottes…). 5B reste seulement partiellement implémenté.

5B autorisé puis consolidé le 2026-10-29 sur work/step-5b-identity-contracts :
[contrats validés](../03-technical/identity-contracts.md), **partiellement implémentés par C02–C08 sur PR #7 seulement**.
5B documentaire terminé et intégré à master via PR #6, merge `63bb7d1` le 2026-10-29.
5C devient le lot courant sur work/step-5c-portal-account-lobby depuis ce merge : premier checkpoint
documentaire et cadrage réalisés, puis C01–C08 autorisés et implémentés ; C08 livré, recette C09 réalisée, 5C fusionné via PR #7 (`ff6ef89`), puis 5D via PR #8 (`0e2ca11`).
Research est intégrée via PR #9 (`437844e4`), Q05 close ; CI post-merge 41152760101
success (5/5), vérifiée le 31/10/2026. [API/UI Research](../03-technical/research-api-ui.md).
Historique étape 7 (intégrée via #10) : Galaxy + Exploration, branche unique `work/step-7-galaxy-exploration`.
Q06/Exploration validées ; G02–G10 réalisés sur PR #10 ([technique](../03-technical/galaxy-api-ui.md)) ; étape 8 alors non commencée.
État et prochain point d’arrêt dans progress ; les anciens checkpoints restent historiques. Le
[registre Q40–Q56](../05-project/open-questions.md) détaille les décisions closes, travaux techniques
délégués et reports support/email/modes. Corrections finales : effets MFA ciblés sans global sur
ajout de facteur/régénération volontaire des secours avec step-up existant ; plafonds 10/10 configurables et sans effet sur
memberships ; APIs même origine et CORS credentials refusé par défaut. La recette locale, les checks
documentaires et les CI réellement observées restent distingués dans [progress](../../progress.md).

Ce dossier indexe les références canoniques ; il ne remplace ni game_data, ni les ADR, ni le registre
Qxx. Les informations de provenance sont limitées à ce qui a réellement été accessible. Aucun
transcript privé, secret, identifiant privé ou renseignement personnel n’est exporté.

Une reprise fraîche doit pouvoir distinguer état implémenté, validation produit, balance provisoire,
proposition et question ouverte. Une ambiguïté encore présente va dans known-gaps et le registre,
sans transformer une suggestion d’assistant en décision validée.

Plan historique : [plan étape 7](../05-project/step-7-plan.md), Q06/Exploration validées avec amendements le 31/10/2026 ; G02–G10 autorisés après CI préalable 5/5 verte.

## État post-merge étape 7 — 31/10/2026

Étape 7 intégrée via PR #10, merge `773e05c`, CI post-merge 41220568486 success (5/5).
Q06/Q08 et Exploration livrées ; anciens checkpoints ci-dessus historiques.
Étape 8 ensuite menée sur `work/step-8-system-view` (S00–S10).

## État post-merge étape 8 — 31/10/2026

Étape 8 intégrée via PR #11, merge `e011fd3`, CI post-merge 41231820338 success (5/5) ;
System View livrée, anciens checkpoints historiques. Étape 9 ensuite menée sur `work/step-9-fleets`.

## État post-merge étape 9 — 01/11/2026

Étape 9 intégrée via PR #12, merge `3a528b6`, CI post-merge 41322146062 success (5/5). Historique de la reprise suivante :
étape 10 Colonisation, branche `work/step-10-colonization`, PR #13, [plan](../05-project/step-10-plan.md) ;
Q07 close avec amendements, COL02–COL11 réalisés. Étape 11 alors non commencée, aucun merge.

## État post-merge étape 10 — 01/11/2026

Étape 10 intégrée via PR #13, merge `a33a452b416ec83d4e8b91d84292913d18db5a40` ;
CI post-merge 41340653571 success (5/5), vérifiée le 01/11/2026. Colonisation/Q07 et la
sous-décision Q04 v0.5 livrées. Lot courant : **étape 11 Première IA**, branche
`work/step-11-first-ai` depuis master propre. AI00/AI01 documentaires seuls autorisés ;
Q11 ouverte, aucun code IA engageant avant sa validation explicite. Étape 12 Combat non commencée.
[Plan AI00–AIxx](../05-project/step-11-plan.md). Aucun merge ni suppression de branche autorisé.

AI00 publié (`6a09b07`) ; AI01 audit/proposition sur PR Draft #14 :
[Q11 ouverte A1–A10](../01-game-design/artificial-intelligence.md#arbitrages-demandés-avant-ai02),
[audit/architecture](../03-technical/ai-engine.md), [plan AI02–AI11 conditionnel](../05-project/step-11-plan.md).

État courant étape 11 : Q11 close avec amendements le 01/11/2026 ; AI02–AI10 réalisés sur la
PR #14 (reprise Claude Code après limite Codex, travail local préservé), [contrat technique](../03-technical/first-ai.md).
AI11 revue/CI/Ready en cours ; aucun merge ni Combat. Les statuts documentaires AI01 ci-dessus sont historiques.

## État post-merge étape 11 — 02/11/2026

Étape 11 Première IA intégrée via PR #14, merge `f79d9f6d0c3ebd9d230344b5a0c2aeaef9f4ce6b` ;
CI post-merge 41358533969 success (5/5), vérifiée le 02/11/2026 ; Q11 close. Les états courants
étape 11 ci-dessus sont historiques. Lot courant : **étape 12 Combat MVP**, branche
`work/step-12-combat`, PR Draft unique. Q02/Q10 closes pour le Combat MVP v0.7 seulement,
[décisions](../01-game-design/combat.md#q02q10--décisions-combat-mvp-v07-02112026), [plan COM00–COM11](../05-project/step-12-plan.md).
Étape 13 Relations non commencée ; aucun merge ni suppression de branche autorisé.

## État post-merge étape 12 — 02/11/2026

Étape 12 Combat MVP intégrée via PR #15, merge `067a4e58863b910785764591d8bf3af4b0ec18e0` ;
Full CI post-merge 41375165508 success (5/5), vérifiée le 02/11/2026. Les états courants étape 12
ci-dessus sont historiques. Lot courant : **étape 13 Relations IA minimales**, branche
`work/step-13-ai-relations`, PR Draft unique. R00/R01 documentaires : Q18 ouverte,
[proposition B1–B12](../01-game-design/relations.md), [plan R00–R11](../05-project/step-13-plan.md).
Aucun code relations avant validation Q18 ; aucun merge ni suppression de branche autorisé.
