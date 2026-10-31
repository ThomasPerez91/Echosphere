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
Lot courant : étape 7 Galaxy + Exploration, branche unique `work/step-7-galaxy-exploration`.
G00/G01 autorisés, validation Q06/Exploration requise avant code engageant ; étape 8 non commencée.
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

Cadrage courant : [plan étape 7](../05-project/step-7-plan.md), propositions Q06/Exploration non validées ; arrêt produit G01.
