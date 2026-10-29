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
**Non implémenté** : Portal/auth/lobby, API gameplay et systèmes futurs du MVP.

Préparation 5B autorisée le 2026-10-29 sur work/step-5b-identity-contracts :
[contrats](../03-technical/identity-contracts.md), non implémentés, avec arbitrages utilisateur
partiels Q40–Q44, comportement Q45 validé et mécanismes encore proposés. Q46–Q56 restent ouvertes ; PR #6 non fusionnée.
La recette locale et ses limites figurent dans [progress](../../progress.md).

Ce dossier indexe les références canoniques ; il ne remplace ni game_data, ni les ADR, ni le registre
Qxx. Les informations de provenance sont limitées à ce qui a réellement été accessible. Aucun
transcript privé, secret, identifiant privé ou renseignement personnel n’est exporté.

Une reprise fraîche doit pouvoir distinguer état implémenté, validation produit, balance provisoire,
proposition et question ouverte. Une ambiguïté encore présente va dans known-gaps et le registre,
sans transformer une suggestion d’assistant en décision validée.
