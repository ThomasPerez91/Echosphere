# MFA Portal — C05 de 5C

**Statut : implémenté sur work/step-5c-portal-account-lobby / PR #7, non intégré à master.**
2026-10-30, Codex local ; instruction utilisateur « Vasy enchaine » après C04.
[Contrats 5B inchangés](identity-contracts.md) · [Plan 5C](../05-project/step-5c-plan.md) ·
[Sessions](portal-sessions.md) · [Opérations sensibles](portal-account-security.md).

## Parcours et autorité

MFA facultative pour les joueurs, obligatoire à la connexion normale et au step-up après activation.
Mot de passe toujours requis ; aucune passkey ne devient ici une identité ou connexion sans mot de
passe. Un TOTP actif maximum, jusqu’à cinq credentials WebAuthn nommables ; ajout et remplacement
vérifient le nouveau facteur avant de modifier les facteurs actifs. Aucun changement de global_user_id,
email, membership, Empire ou gameplay. Aucune API d’attribution de privilèges ou console admin.

Le step-up C04 est étendu aux actions mfa_enroll, mfa_remove, mfa_disable et mfa_backup_codes.
Mot de passe actuel + facteur existant si MFA active ; activation initiale : mot de passe puis preuve
du nouveau facteur. Preuve cinq minutes, usage unique, liée à la session/action/paramètres importants
(type, nom et facteur remplacé/supprimé). L’assurance password/totp/webauthn est persistée et la
politique courante recontrôlée à la consommation. Toute consommation et mutation sont sous verrou
User et transaction Accounts ; erreur : rollback des preuves, facteurs, secours et révocations.

TOTP : PyOTP 2.10, secret aléatoire 160 bits, six chiffres/30 secondes, tolérance ±1 pas, dernier pas
accepté stocké sous verrou compte ; un code/pas accepté ne peut être rejoué, même entre login et
step-up ou en concurrence. Clé de saisie manuelle et URI d’enrôlement renvoyées uniquement lors de la
création ; aucun endpoint de lecture du secret actif. Le formulaire ne persiste ni secret ni URI.

WebAuthn : py_webauthn 2.8 et @simplewebauthn/browser 14, sans vérificateur cryptographique maison.
Challenges 256 bits, cinq minutes absolues, usage unique, liés au compte, à sa génération, au secret
de pré-auth/session et à l’action/paramètres. RP et origine exacts, présence et **user verification**
obligatoires pour inscription et assertion ; clés ES256/RS256. UserHandle, s’il est fourni, doit être
le UUID du compte. Credential ID unique, clé publique et compteur conservés, jamais la clé privée.
Compteurs contrôlés par la bibliothèque ; un compteur nul reste compatible avec les passkeys
synchronisées et ne fournit pas une détection universelle de clonage. Attestation none, aucun
contrôle de fabricant ni synchronisation de passkey géré par Echosphere.

RP de développement : portal.echosphere.localhost ; origine https://portal.echosphere.localhost:8443.
PORTAL_WEBAUTHN_RP_ID doit correspondre au hostname exact de PORTAL_PUBLIC_ORIGIN ; configuration
incohérente refusée, sans repli vers Game ou une origine générique. Domaines/RP/HTTPS de production
à configurer avant exposition (Q49) ; pas de migration silencieuse d’un credential entre RP.

## Effets des modifications

| Opération | Sessions Portal / intention Game |
| --- | --- |
| Activation initiale | Révocation globale, session courante comprise |
| Remplacement TOTP/WebAuthn, suppression d’un facteur, désactivation | Révocation globale |
| Ajout d’un facteur supplémentaire avec facteur existant vérifié | Sessions conservées, epoch inchangé |
| Régénération volontaire des secours avec facteur existant vérifié | Sessions conservées, epoch inchangé ; anciens secours invalidés |
| Récupération avec code de secours | Révocation globale à l’entrée et à la restauration du facteur |

Toutes ces opérations sont auditées et notifient l’adresse du compte, sans secret dans la notification.
Les effets globaux annulent les parcours reset/email pending et step-ups, incrémentent security_epoch
et persistent AccountRevocation dans la transaction. Livraison Game C06/C07 encore absente : **pending**,
aucun acquittement inventé ni nouvelle fenêtre de huit heures. Les univers/workers restent indépendants.

C04 est raccordé : MFA obligatoire pour les actions sensibles d’un compte équipé. Changement email
avec preuve MFA forte : ancienne adresse considérée confirmée dans cette demande, seule la nouvelle
adresse reçoit un lien à confirmer avant l’échéance commune d’une heure ; notifications finales aux
deux adresses et révocation globale conservées. Sans MFA : toujours les deux liens. Reset du mot de
passe par email autorisé mais ne désactive ni ne remplace la MFA ; reconnexion normale avec facteur
ensuite obligatoire, aucun auto-login ni bypass.

## Secours et récupération limitée

Dix codes de secours **160 bits aléatoires chacun**, groupés pour la lecture ; SHA-256 seul en DB,
aucune copie exploitable dans les logs, audits, notifications ou localStorage/sessionStorage. Affichés
uniquement à l’activation/régénération/restauration, conservés en mémoire le temps de cet écran et
masquables ; fermeture/rechargement ne permet pas de les relire. Régénération invalide tout le jeu
précédent. Le secret TOTP n’est jamais utilisé comme preuve de récupération.

Mot de passe + code de secours unique + pré-auth navigateur/CSRF autorisent une session de récupération
**quinze minutes absolues**, cookie distinct __Host-portal-recovery. Aucune PortalSession normale
n’est créée. Cette capacité ne permet que l’enrôlement d’un nouveau facteur ; les routes compte,
sessions et actions sensibles normales la refusent. Les facteurs perdus sont supprimés à l’entrée,
la MFA reste exigée ; un compte sans facteur restauré ne devient jamais password-only. Les autres
secours permettent de recommencer si la capacité expire/se perd ; le code déjà consommé reste
inutilisable. Restauration réussie : remplacement de tous les secours et nouvelle connexion normale.

Autre authentificateur encore disponible : connexion et remplacement normaux. Perte de tous les
facteurs/secours : **blocage**, aucune récupération par email + mot de passe ni procédure support
inventée. Q48 conserve cette procédure distincte différée.

## Comptes privilégiés

Politique serveur : au moins un WebAuthn ; PORTAL_PRODUCTION=true impose deux credentials WebAuthn.
TOTP seul ne satisfait jamais une preuve privilégiée. Suppression sous ce minimum ou désactivation
refusées. Aucun endpoint public ne promeut un compte ; enrôler avant d’attribuer des privilèges via
un futur circuit d’administration contrôlé. Les rôles gameplay ne sont pas des privilèges plateforme.

Une récupération privilégiée impose WebAuthn pour rétablir un facteur et active
privilege_recovery_required. Ce verrou persiste après restauration : aucune connexion privilégiée
ni réactivation automatique ; il faut encore la procédure privilégiée approuvée, actuellement
absente. Aucun endpoint ne lève ce verrou. En production le minimum de deux credentials devra aussi
être satisfait avant rétablissement futur des fonctions privilégiées.

## Stockage, exploitation et API

Migration additive **p0004_mfa**, p0000–p0003 immuables. Six tables : totp_credentials,
webauthn_credentials, mfa_backup_codes, mfa_challenges, mfa_recovery_sessions, auth_failures.
Assurance ajoutée aux step-ups/demandes email ; raisons MFA et notifications étendues ; verrou de
récupération privilégiée sur User. FK uniquement Accounts. Downgrade peuplé refusé ; roundtrip
uniquement sur base dédiée *_test. Aucun changement SQL/code Game.

Seeds TOTP actifs/provisoires chiffrés Fernet avec **clé distincte de l’email**, fichier privé
/run/portal-secrets/mfa.key (PORTAL_MFA_KEY_FILE), jamais en DB/Git/VITE. Init crée la clé manquante
sans écraser une clé existante ; API/worker la montent en lecture seule. Sauvegarde/rotation de clés
production à définir avant déploiement ; perdre la clé n’autorise pas un contournement. Worker :
effacement des seeds provisoires expirés, purge des challenges/récupérations expirés et compteurs
anciens après un jour ; audit 90 jours distinct des epochs anti-rejeu persistants.

Quotas existants par opération/IP/sujet, plus cooldown persistant progressif sur échecs login,
step-up, MFA et récupération : 100/200/400/800/1000 ms, plafond configurable, retour 429 si trop tôt.
Une tentative avant échéance ne repousse pas celle-ci ; pas de verrouillage permanent automatique.
Paramètres PORTAL_AUTH_DELAY_BASE_MS=100, PORTAL_AUTH_DELAY_MAX_MS=1000 ; compteurs réinitialisés après
quinze minutes sans échec. Limites techniques initiales à mesurer avant exposition, pas de preuve
DDoS ou de temps constant sous charge. Échecs associés à un compte connu audités sans secret (90 jours), compteurs de cooldown séparés.
Réponses publiques génériques sans contenu privé des preuves.

API sous /api sur la même origine Portal ; Origin/JSON/CSRF, no-store, Secure/HttpOnly/host-only,
SameSite strict et aucune autorité d’un timestamp client. Corps MFA bornés à 64 Kio pour WebAuthn ;
corps inscription/auth/sécurité restent à 8 Kio. Pas de CORS credentials ouvert.

| Route | Autorité / effet |
| --- | --- |
| GET /mfa/status | Session normale, bootstrap explicite, lecture sans prolongation d’inactivité |
| POST /mfa/assertion/options | Mot de passe et contexte pré-auth login ou session ; challenge lié à l’action |
| POST /auth/login | Mot de passe et factor optionnel ; exigé si MFA active |
| POST /security/step-up | Action/paramètres et factor si équipé ; assurance persistée |
| POST /mfa/enroll/begin | Session + step-up d’enrôlement ; TOTP provisoire ou options WebAuthn |
| POST /mfa/enroll/finish | Même session + challenge + preuve du nouveau facteur |
| POST /mfa/manage | Session + step-up lié ; suppression, désactivation ou secours |
| POST /mfa/recovery/start | Pré-auth + mot de passe + code de secours ; capacité limitée 15 min |
| POST /mfa/recovery/enroll/begin et /finish | Cookie/CSRF de récupération seulement ; aucun accès Portal normal |

Le step-up et les actions de sécurité sont des interactions explicites datées serveur ; GET status,
options/retry automatiques et trafic ambiant n’entretiennent pas les sessions. L’échéance absolue et
les règles d’inactivité C03 restent inchangées. WebAuthn peut être annulé côté navigateur ; les
challenges serveur conservent leur expiration, aucun succès n’est supposé après timeout.

## Preuves et limites

Tests PostgreSQL : activation/ajout/remplacement/désactivation, plafonds, signatures WebAuthn réelles,
RP/origine/UV/rejeu/scopes, TOTP concurrent, transaction interrompue, récupération 15 min et cookies
sans autorité normale, privilèges bloqués, email avec MFA, cooldown et purge. UI testée séparément ;
Chromium exécute la bibliothèque navigateur avec un authentificateur virtuel réel (API interceptée),
mobile 320 px et absence de stockage navigateur. Aucun vérificateur cryptographique backend simulé.
Résultats, counts et CI réellement observés dans [progress](../../progress.md).

Smokes Compose : TLS réel, bases/migrations et résilience des services. Ces preuves séparées ne sont
pas une recette complète navigateur HTTPS → vraie API → authentificateur matériel : C09 doit la
compléter. Aucun test Safari/Firefox, téléphone physique, clé matérielle ou délivrabilité publique
attesté. Support renforcé Q48, configuration production Q49 et modes Q55 restent différés.
**Suite C06** lobby/interface interne, puis C07 handoff ; 5D exclu, aucune fusion PR #7 autorisée.

Références techniques : [PyOTP](https://pyauth.github.io/pyotp/),
[py_webauthn](https://duo-labs.github.io/py_webauthn/),
[SimpleWebAuthn navigateur](https://simplewebauthn.dev/docs/packages/browser),
[OWASP MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html).
Les règles produit viennent des arbitrages 5B, pas de ces bibliothèques.
