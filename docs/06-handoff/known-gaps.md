# Lacunes, contradictions et risques à reprendre

**Statut : questions/limites explicites au 2026-10-28.** Ce document n’invente pas les réponses.

Actualisation 2026-10-29 : #5 fusionnée, recette locale consignée dans [progress](../../progress.md).
[Contrats 5B](../03-technical/identity-contracts.md) validés et consolidés après arbitrage du bloc
complet corrigé ; 5B documentaire terminé et intégré à master via PR #6 (`63bb7d1`),
contrats d’auth partiellement implémentés sur PR #7 par C02. 5C est le lot courant : checkpoint/cadrage effectués,
[socle C01](../03-technical/portal-foundation.md) et [C02](../03-technical/portal-registration.md) implémentés sur PR #7, avec [C03 sessions/CSRF](../03-technical/portal-sessions.md) et [C05 MFA](../03-technical/portal-mfa.md), avec [C06 lobby/mTLS](../03-technical/portal-game-control.md) et [C07 handoff/sessions Game](../03-technical/game-handoff.md).
HTTPS/routage/isolation de panne des bases testés, pas de confiance navigateur Windows/charge démontrée.
[Q40–Q56](../05-project/open-questions.md) séparent clôtures, détails techniques délégués et reports.
Restent ouverts : procédures support renforcé joueur/privilégié Q48 (aucun déblocage sans procédure
approuvée), fournisseur et configuration production Q49, politiques des modes futurs Q55/Q19–Q29.
Aucun arbitrage produit supplémentaire nécessaire au cadrage 5B identifié ; aucun début de 5D.

Actualisation C08/C09 : [parcours/shell](../03-technical/portal-game-ui.md) et
[recette de clôture](../03-technical/portal-operations.md) sur PR #7. Handoff navigateur HTTPS réel,
Game autonome sous arrêt Portal, construction acceptée terminée par le worker, révocation retardée
acquittée et suivi de statut limité, rotation locale des kids et pg_dump/restore des deux DB de test
recettés. Les anciennes limites de tickets C01–C07 ci-dessous décrivent leurs checkpoints ; ces
nouvelles preuves les remplacent dans leur périmètre, sans prétendre à une recette Windows matérielle.
Restent avant production : fournisseur/domaines, PKI/rotation des secrets mail/MFA, barrière de
restauration et RPO/RTO, archivage anti-rejeu, budgets de charge et observabilité. Aucun prestataire,
procédure support Q48 ou règle des modes Q55 choisi par implication. 5D reste hors lot.

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
| game_data sans paramètres, frontend placeholder, Compose à trois services | État périmé remplacé : v0.1, shell et cinq services Game intégrés ; socle Portal ajouté depuis dans C01 sur PR #7 |
| Neuf tables et migrations 0001–0003 seulement | 13 tables métier sur branche #5, plus alembic_version ; 0004 additive, aucun schéma modifié ici |
| 5B = API/UI Colony directement | **Superseded** par 5B contrats identité/Portal-Game, 5C compte/lobby minimal selon cadrage, 5D API/UI sécurisées |
| Toutes planètes supposées 12/2 | Aucun invariant global : référence initiale v0.1 seulement ; initialiseur actuel limité à cette référence |
| Niveaux I–V limitatifs | **Superseded** par niveaux continus ; chiffres après 5 toujours provisoires |
| develop comme référence permanente, master pour releases | **Superseded** depuis #3 ; master intégration stable, pas de develop permanente |
| Auth entièrement non cadrée | Architecture et contrats 5B validés ; réalisation future, délégation et reports au registre Q40–Q56 |
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
modules de défense et remboursement saturé. Leurs statuts antérieurs sont préservés.
Contrats identité et sécurité 5B clos dans leur périmètre ; cookies protégés/sessions opaques,
ticket signé local, mTLS, livraison/révocation idempotente et règles MFA validés. Détails techniques
à préciser et tester dans les lots dépendants. Reports Q48/Q49/Q55 indiqués ci-dessus, sans fausse
clôture de leurs procédures/fournisseur/règles futures.

Limites d’application à vérifier en 5C/5D : rattachement d’un profil navigateur entre deux origines,
comptage concurrent des caps configurables, révocations ciblées contre tickets en vol et messages
retardés, preuve step-up par action, effets MFA sans global indu sur ajout de facteur/régénération volontaire des secours protégés,
CORS refusé par défaut et recette de clés en panne Portal. Aucun mécanisme n’existe encore.
Les contrats d’autonomie et révocation sont conciliés par la borne non glissante de huit heures,
pas par une promesse de révocation distante instantanée ou de refresh illimité. Un déploiement partagé
ne prouve pas l’isolation CPU/RAM/DB/réseau. Les protections Portal ne dispensent pas Game des siennes.

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

## Limites propres au socle C01

Dépendances frontend Portal indépendantes, npm audit initial 0 vulnérabilité ; cela ne corrige pas
les avis du frontend Game ci-dessus. npm signale encore des dépréciations de développement, dont
ESLint 9 et whatwg-encoding. L’avertissement Starlette/httpx reste présent. Aucun changement d’outil
Game ni nouveau service production engagé. Récepteur email et fournisseur non livrés en C01.
Les tests Chromium Portal interceptent les sondes ; le smoke HTTPS vérifie réellement CA/noms et
pannes croisées. Pas de parcours authentifié réel tant que les tickets dépendants ne sont pas livrés.

## Limites historiques C02

Inscription/vérification locales seulement ; connexion/sessions, MFA et parcours sensibles à suivre.
Contrôle de mots de passe compromis dépendant de Pwned Passwords : panne → refus temporaire 503.
SMTP au moins une fois : doublon possible après acceptation avant commit, jamais double consommation
de preuve. Mailpit local ne prouve pas la délivrabilité publique ; fournisseur Q49 inchangé.
Clé persistante locale hors Git, procédures production de sauvegarde/rotation non livrées.
UI Chromium avec API interceptée et SMTP/API PostgreSQL réels testés séparément ; pas de parcours
complet navigateur hôte HTTPS, tactile ou lecteur d’écran attesté. Warning Starlette/httpx connu.

## Limites historiques C03

C04 lève les limites des opérations sensibles sans MFA et du logout global ; détails dans sa section.

[Sessions Portal/CSRF](../03-technical/portal-sessions.md) livrés sur PR #7, pas sur master.
Logout Portal atomique avec intention durable et génération appareil, mais aucune livraison Game :
état pending et UI fidèle, acquittements/retry/réconciliation à C06/C07. Pas de logout tous appareils
sans le step-up futur, ni MFA/compte sensible/handoff. La preuve multi-onglets couvre rotation/refus
et relecture sans rejeu ; aucun secret en stockage navigateur. Recette complète navigateur HTTPS et
handoff prévue C09 ; smokes TLS/API et UI interceptée sont des preuves séparées.

## Limites historiques C04

[Opérations sensibles](../03-technical/portal-account-security.md) livrées sans MFA seulement ;
comptes avec politique MFA/privilégiée refusés tant que C05 ne fournit pas les preuves. Intentions
globales persistées, aucun transport Game/acquittement, UI en attente. Notifications Mailpit locales,
aucune délivrabilité publique ou procédure support attestée. Plancher anti-énumération des demandes
reset 150 ms configurable, pas de temps constant garanti sous charge. Recette UI interceptée séparée
des intégrations PostgreSQL/API/SMTP et du smoke TLS ; navigateur HTTPS complet à C09.

## Limites historiques après C05

[C05 MFA](../03-technical/portal-mfa.md) lève les limites de preuves MFA/login/step-up de C03/C04.
TOTP/WebAuthn/secours et récupération limitée fonctionnels sur PR #7, non intégrés à master.
Aucun fournisseur email public, console admin ou procédure support Q48 : perte totale bloquée ;
récupération privilégiée ne restaure jamais les droits, verrou persistant sans endpoint de levée.
PORTAL_PRODUCTION=true et domaines/RP/clé séparée à configurer avant exposition. Clés matérielles,
téléphones physiques, Safari/Firefox et navigateur hôte HTTPS complet non attestés. Chromium utilise
un authentificateur virtuel et une API interceptée ; vérifications cryptographiques/PostgreSQL et TLS
Compose testés séparément. Recette complète C09 future. Livraison Game/réconciliation C06/C07 absente,
intentions toujours pending ; aucune fenêtre Game créée ou relancée par un changement MFA.
Cooldown et quotas testés ne constituent pas une preuve de résistance à une charge hostile.

## Limites courantes après C06

[C06](../03-technical/portal-game-control.md) livre la synchronisation et l’acquittement des révocations
compte/appareil, mais aucune GameSession ni ticket : branchement aux sessions et révocation de session
précise restent C07. Lobby réel, aucune entrée jouable/catalogue/join ou monde créé par défaut.
État d’acquittement daté ; pas de disponibilité Game instantanée garantie. Le message après logout
reste pending, suivi anonyme/complet à C07/C08 ; le lobby connecté expose les acquittements réels.
PKI de développement et empreintes TLS testées, feuilles 30 jours sans renouvellement silencieux ;
rotation/configuration production et recette opérationnelle avant exposition, C09/Q49. Adaptateur
H11 dépend de la version Uvicorn figée, recette mTLS obligatoire à sa mise à jour. Aucun test de charge,
perte physique de DB, restauration de sauvegarde, handoff ou navigateur complet de partie attesté.
Source pending vers cible retirée/renommée ou état Game contradictoire supérieur : intervention
opérateur, jamais abandon de révocation ou abaissement silencieux. Q48/Q49/Q55 et Q19–Q29 conservées.
