# Lacunes, contradictions et risques à reprendre

**Statut : questions/limites explicites au 2026-10-28.** Ce document n’invente pas les réponses.

Actualisation 2026-10-29 : #5 fusionnée, recette locale consignée dans [progress](../../progress.md).
[Contrats 5B](../03-technical/identity-contracts.md) : login MVP, principes de récupération,
limites de sessions/ticket et fenêtre non glissante de huit heures validés sur arbitrage utilisateur
pour PR #6 ; seules ces parties de Q40–Q44 sont closes. Activité explicite validée Q41/Q43, comportement de déconnexion validé Q45 ; regroupement appareil, stockage, transport
interne, clés, propagation et protections restent à arbitrer. Q46–Q56 demeurent ouvertes.
Complément Q40/Q49 : récupération 30 min/unique, réémission et effets du reset validés ;
Flux email sans MFA également validé : double confirmation/pending, notifications et réauthentification.
Demande email unique 1 h absolue, remplacement complet et révocation globale après succès validés.
Q49 reste partiellement ouverte (fournisseur/livraison et mécanismes). Variante MFA sous Q48 non livrée ; sans accès ancien, pas de bypass mot de passe seul.
Q48 partiellement arbitrée : MFA facultative joueurs MVP, obligatoire pour privilèges plateforme,
step-up des comptes équipés sur actions sensibles. Facteur/récupération et mécanismes restent ouverts.

## Accès incomplet aux sources

- Pas d’accès direct à toutes les conversations Space Game ou à un export intégral du projet.
- Recherche contextuelle : extraits et synthèses utiles, pas lecture des conversations originales.
  Une source de fichier signalée par cette recherche n’a pas été ouverte intégralement ici.
- Certains choix initiaux (palette, ratio 80/20, noms de rôles et tailles standard 100–150) ne sont
  retrouvés précisément que dans les docs/PR GitHub ; leur validation d’origine n’est pas attestée.
  Ils restent propositions/repères selon le document canonique, sans promotion en décision produit.
- Pas d’export automatique des décisions futures de ChatGPT vers GitHub. Toute nouvelle décision
  doit être transcrite explicitement dans sa référence canonique, son statut et progress.
- Aucune information personnelle, secret, identifiant privé ou sujet hors Echosphere transféré.
  Les extraits privés, prompts bruts et résultats de recherche ne sont pas ajoutés au dépôt.

## Contradictions repérées et traitement documentaire

| Ancienne formulation | Correction / statut actuel |
| --- | --- |
| Plateforme entière dans un backend / une DB définitifs | **Superseded partiellement** : ADR 0008 sépare Portal/Game ; monolithe modulaire gameplay maintenu, code actuel inchangé |
| ADR 0002 indexé « implémentation future » | Historique bootstrap conservé comme tel ; scheduler livré depuis #3, index actuel corrigé |
| game_data sans paramètres, frontend placeholder, Compose à trois services | État périmé remplacé : v0.1, shell et cinq services actuels ; aucun Portal ajouté |
| Neuf tables et migrations 0001–0003 seulement | 13 tables métier sur branche #5, plus alembic_version ; 0004 additive, aucun schéma modifié ici |
| 5B = API/UI Colony directement | **Superseded** par 5B contrats identité/Portal-Game, 5C compte/lobby minimal selon cadrage, 5D API/UI sécurisées |
| Toutes planètes supposées 12/2 | Aucun invariant global : référence initiale v0.1 seulement ; initialiseur actuel limité à cette référence |
| Niveaux I–V limitatifs | **Superseded** par niveaux continus ; chiffres après 5 toujours provisoires |
| develop comme référence permanente, master pour releases | **Superseded** depuis #3 ; master intégration stable, pas de develop permanente |
| Auth entièrement non cadrée | Architecture globale désormais validée ; mécanismes concrets restent ouverts en Q16/Q40–Q56 |
| Cascade d’annulation implicitement validée produit | Code présent ; proposition produit à confirmer sous Q01, distincte des 100/80 % demandés |

Les descriptions historiques de PR fusionnées ne sont pas réécrites pour simuler leur état actuel.
Les ADR historiques portent une note d’évolution ; le nouvel index explique quelle décision fait foi.

## Limites techniques réelles de 5A, sans correctif dans cette mission

Voir [audit #5](pr-5-audit.md) : Q39 non arbitré ; initialisation de référence seulement ; bornes de
secteur contrôlées au service et contournables par SQL direct ; copie du ruleset immuable par
contrat applicatif et non par contrainte DB ; migration de ruleset/vitesse actif et des timelines
anciennes hors lot. Ces limites doivent être considérées avant nouveaux imports/admin/API.
Les tests de concurrence/idempotence ne prouvent pas la sécurité d’une API d’identité inexistante.

## Validation produit et technique à venir

Q01–Q39 conservées : protection offline et nouveau joueur, économie/entretien/balance, taille des
planètes, recherche, génération, colonisation, fog, flottes, combat, IA, victoire, modes, late join,
modules de défense et remboursement saturé. Les parties restantes de Q40–Q44 et Q46–Q56 cadrent
les mécanismes Portal/Game ; login, limites temporelles, activité et comportements de déconnexion sont précisés comme indiqué
ci-dessus. Aucun cookie, format de ticket, stockage, rôle, facteur MFA, fournisseur email, anti-bot ou crypto choisi.

L’autonomie d’une GameSession et la révocation d’un accès devront être conciliées : aucune promesse
de révocation instantanée/refresh illimité pendant panne Portal. Un déploiement partagé ne prouve
pas l’isolation CPU/RAM/DB/réseau. Les protections Portal ne dispensent pas Game de se protéger.

Pas de recette réelle Windows 11/WSL2/Docker Desktop attestée dans cette passation. Pas de test
lecteur d’écran/tactile, Safari/Firefox, charge massive ou simulation économique de plusieurs années.
Les commandes de reprise sont une procédure, pas la preuve de leur exécution à domicile.

## Constats de la reprise locale du 2026-10-29

La mention précédente décrit la passation du 28/10 : depuis, Compose/Alembic/smoke, 101 tests backend,
11 frontend et 5 Chromium ont été exécutés localement sous WSL2, avec les limites détaillées dans
progress. Cela n’atteste toujours pas les parcours graphiques Windows ou une intégration Portal/Game.

Deux adaptations de la procédure de tests Docker ont été nécessaires : le montage des seuls tests
backend ne conserve pas le chemin relatif vers game_data utilisé par un test d’intégration ;
monter l’arborescence complète en lecture seule résout ce cas. L’image frontend Alpine n’a pas apt-get
pour les dépendances Playwright ; les E2E ont réussi dans un conteneur Debian jetable.
Ces constats ne justifient aucune modification de code ou d’image dans le lot 5B documentaire.

`npm audit` signale 3 dépendances de développement affectées : @vitest/mocker (modérée), tinypool
et vitest (critiques selon le rapport npm, vitest héritant aussi de ses dépendances).
Avis retournés : [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9),
[GHSA-qxg6-89mg-rqv8](https://github.com/advisories/GHSA-qxg6-89mg-rqv8),
[GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3),
[GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr).
Exposition effective et trajectoire de mise à jour à examiner dans un lot de maintenance explicite ;
aucun exploit démontré ici, aucun npm audit fix ni changement de lockfile effectué.
Un avertissement de dépréciation Starlette/httpx est également remonté sans échec des tests.
