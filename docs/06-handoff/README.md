# Passation Space Game / Echosphere

**Statut : documentation durable, mission du 2026-10-28.** GitHub est la source de vérité partagée
pour Work et Codex local ; un historique de chat n’est pas nécessaire pour reprendre le périmètre
consigné. Cette passation n’est pas un export complet des conversations du projet.

## Reprise en sept lectures

1. [AGENTS](../../AGENTS.md) : procédure commune et autorisations.
2. [Contexte](../../context.md) : invariants stables et frontière de mission.
3. [Progression](../../progress.md) : dernier checkpoint vérifiable et prochaine action.
4. [Carte des sources](source-map.md) et [index des décisions](decision-status.md).
5. [Roadmap](../05-project/roadmap.md) et [questions ouvertes](../05-project/open-questions.md).
6. [Vision](../00-product-vision.md), références métier du prochain lot et [ADR](../adr/README.md).
7. [Procédure Work/Codex](work-codex-handoff.md), [audit #5](pr-5-audit.md), [lacunes/risques](known-gaps.md).

## Ce qui est et n’est pas livré

**Implémenté et intégré sur master par PR #5** : fondations, scheduler, shell, domaine Colony v0.1 interne.
Fusion vérifiée le 2026-10-29 : master 8214e0b, CI verte. L’ancien checkpoint de passation
décrivait #5 ouverte ; il reste historique. Vérifier GitHub réel avant d’agir.
**Décisions validées, futures** : compte global, multi-parties, Portal/Game isolables,
Accounts DB/Game DB séparées, interface interne contrôlée et GameSession autonome après handoff.
**Sur PR #7, non intégré** : [socle Portal C01](../03-technical/portal-foundation.md), backend/frontend,
Accounts DB et HTTPS local ; [C02](../03-technical/portal-registration.md) ajoute inscription,
Argon2id, vérification et email durable local. [C03](../03-technical/portal-sessions.md) ajoute connexion/sessions Portal, CSRF et intentions de logout.
[C04](../03-technical/portal-account-security.md) ajoute opérations sensibles sans MFA, step-up et logout global.
**Non implémenté** : MFA, lobby,
handoff, API gameplay et systèmes futurs du MVP. 5B reste seulement partiellement implémenté.

5B autorisé puis consolidé le 2026-10-29 sur work/step-5b-identity-contracts :
[contrats validés](../03-technical/identity-contracts.md), **partiellement implémentés par C02–C04 sur PR #7 seulement**.
5B documentaire terminé et intégré à master via PR #6, merge `63bb7d1` le 2026-10-29.
5C devient le lot courant sur work/step-5c-portal-account-lobby depuis ce merge : premier checkpoint
documentaire et cadrage réalisés, puis C01–C04 autorisés et implémentés ; C05 suit, aucun début de 5D. Le
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
