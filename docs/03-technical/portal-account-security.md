# Opérations sensibles du compte — C04 de 5C

**Statut : implémenté sur work/step-5c-portal-account-lobby / PR #7, non intégré à master.**
2026-10-30, Codex local ; instruction utilisateur « enchaine » après C03.
[Contrats 5B](identity-contracts.md) · [Plan 5C](../05-project/step-5c-plan.md) ·
[Sessions C03](portal-sessions.md) · [Emails C02](portal-registration.md).

## Périmètre livré et dépendances

Réauthentification par action, changement de mot de passe, récupération par email, changement
email avec preuves liées et déconnexion de tous les appareils. Le sous-ticket C04 initial était
sans MFA ; [C05](portal-mfa.md) raccorde désormais TOTP/WebAuthn au login, step-up et mutations.
Les politiques MFA/privilégiées exigent leurs preuves ; reset du mot de passe autorisé sans
désactiver les facteurs, reconnexion normale avec MFA ensuite obligatoire. Aucun bypass MFA
ni procédure support inventée.
Aucune route publique ne permet de modifier ces flags, compte/génération ou privilèges.

Les opérations révoquent les sessions Portal et persistent l’intention de révocation Game ; leur
livraison/acquittement reste à C06/C07. L’UI distingue Portal déconnecté et parties en attente.
Aucun membership, Empire, état gameplay, worker Game, handoff ou API Colony modifié.

## Step-up par action

Mot de passe actuel ressaisi, PortalSession valide, CSRF et Origin exacts. Preuve opaque 256 bits,
empreinte seule en DB, cinq minutes absolues depuis création, usage unique ; liaison SQL au
compte/session/appareil, à l’action et aux paramètres. Actions C04 : password_change, email_change,
logout_all. Pas de preuve réutilisable entre deux actions, paramètres, sessions ou après rotation.

Les paramètres sont liés par HMAC-SHA-256 avec le secret de session HttpOnly comme clé et un contexte
versionné/action/JSON canonique. **Aucun mot de passe ni checksum de mot de passe non salé en DB** ;
une lecture de la DB seule ne donne pas un oracle de dictionnaire plus faible qu’Argon2id.
La preuve et les mots de passe restent uniquement en mémoire du navigateur, jamais URL/localStorage.
Émission et consommation sous verrou User ; expiration/session/politique recontrôlées à la mutation,
après le contrôle de compromis/KDF si celui-ci a pris du temps. Consommation atomique avec l’effet,
pas avant commit ; échec d’écriture : aucune preuve brûlée ou révocation partielle.

Step-up réussi et demande email sont des interactions explicites datées serveur. Aucune limite
absolue de session n’est prolongée. Les GET, bootstrap, polling et flags/timestamps client conservent
les règles C03. MFA/step-up privilégié et actions de gestion MFA : [extension C05](portal-mfa.md).

## Mot de passe

### Récupération

Demande email : réponse 202 request_received, même corps pour compte connu, inconnu ou politique
non disponible. Quotas persistants par opération/IP/sujet. Plancher de temps de réponse configurable
150 ms pour les demandes valides, dans les deux cas ; pas une garantie de temps constant en charge.
Aucun compte verrouillé ni session révoquée par la simple demande. La file est committée avant réponse.

Jeton 256 bits, digest SHA-256, trente minutes absolues, usage unique. Nouvelle demande sous verrou :
ancienne génération immédiatement invalidée et anciens messages encore en attente annulés/effacés.
Le worker ne prolonge pas l’expiration pendant ses retries. À now >= expires_at : refus.

Confirmation : nouveau mot de passe conforme à C02 (15–128 caractères, Argon2id et contrôle de
compromis sans texte brut transmis au tiers). Le formulaire demande une seconde saisie ; le serveur
applique seul la politique. Dans une transaction : credential remplacé, tous les resets restants et
changements email pending invalidés, step-ups invalidés, **toutes** PortalSessions révoquées, génération
compte incrémentée, intention Game et notification email persistées. Email_verified_at inchangé : un
reset n’est pas une vérification initiale. Nouvelle connexion normale obligatoire, aucun auto-login.

### Changement volontaire

Session + CSRF + step-up password_change lié au nouveau mot de passe. Même politique et effets
que le reset : révocation globale y compris session courante, invalidation des parcours concurrents,
notification sans mot de passe. Un mot de passe nouveau n’est jamais dans un email ou un log.

## Changement d’adresse sans MFA

1. Session valide, mot de passe actuel via step-up email_change lié à la nouvelle adresse.
2. Demande unique pending, deux secrets distincts old/new dans **la même demande**, date commune
   une heure après création. La nouvelle adresse ne devient pas encore l’adresse du compte.
3. Chaque lien ouvre une page sans mutation automatique, puis POST explicite de confirmation.
   Le token est retiré du fragment immédiatement et gardé en mémoire. Les liens peuvent être ouverts
   ailleurs ; la session à l’origine de la demande doit rester valide côté serveur jusqu’à finalisation.
4. Deux confirmations du même parcours avant échéance : nouvelle adresse active/vérifiée,
   global_user_id conservé, PortalSessions toutes révoquées, intention Game globale et notifications
   à l’ancienne **et** nouvelle adresse. Nouvelle connexion normale avec la nouvelle adresse.

Réémission : ancienne demande/liens/confirmation partielle invalidés ; deux nouvelles confirmations
obligatoires, aucun assemblage de demandes. Une confirmation ne relance aucun délai. Reset/changement
mot de passe annule le parcours email. Session d’origine révoquée/expirée : aucune finalisation ;
rouvrir un parcours autorisé. Absence d’accès à l’ancienne adresse : pas de bypass mot de passe seul.
Variante MFA remplaçant la preuve ancienne adresse : livrée par [C05](portal-mfa.md),
avec mot de passe/facteur et toujours confirmation de la nouvelle adresse.

Unicité PostgreSQL de l’adresse normalisée : aucun transfert/fusion de comptes. Demande initiale
sans révélation d’une adresse déjà attribuée ; conflit à la finalisation : erreur générique et
rollback, identité/session/credential inchangés. Le changement réussi invalide aussi les anciennes
preuves de vérification et récupération ; ancienne adresse jamais restaurée sur un simple lien.

Notifications finales sans credential ou token sensible. Lien non secret « opération non reconnue »
vers le parcours de sécurité : connexion/changement de mot de passe, logout global ou demande de
récupération. Aucune restauration automatique, ticket support traité ou secours MFA prétendu ; Q48
conserve ses procédures distinctes à définir.

## Révocation globale et courses

AccountRevocation contient compte/epoch/raison/date/état pending, atomiquement avec la révocation
Portal. security_epoch est monotone sous verrou User, distinct de l’epoch appareil C03. C06/C07 devront
lier ces générations aux accès/sessions Game et reprendre les intentions jusqu’à acquittement.
Aucun nouveau délai de huit heures n’est créé ici et aucune révocation distante instantanée annoncée.

Le login relit credential, adresse normalisée, politique et génération après verrou : un login
commencé avant un reset, changement email ou logout global ne restaure pas une ancienne session.
Les deux resets concurrents ne réussissent qu’une fois ; confirmations email et finalisation sont
sérialisées avec leurs invalidations. Les opérations ne conservent pas automatiquement la session
courante. Les réponses sensibles ne suppriment pas aveuglément un cookie : une réponse retardée ou
un reset anonyme sur un autre compte ne doit pas effacer une connexion plus récente/non ciblée.
L’invalidation serveur fait autorité ; le prochain login normal remplace le cookie désormais invalide.

L’epoch global ne devra **pas** être incrémenté pour un ajout MFA/régénération volontaire de secours
avec step-up existant, conformément à la correction 5B. Raisons et preuves MFA sont ajoutées par
migration C05 p0004_mfa ; ne pas détourner les raisons password_change/reset pour ces opérations.

## Stockage, livraison et API

Migration additive **p0003_account_security**, p0000–p0002 inchangées. User reçoit security_epoch et
les garde-fous de politique mfa_enabled/platform_privileged, initialisés sans créer de privilèges.
Cinq tables : step_up_grants, password_reset_requests, email_change_requests, account_revocations,
security_email_outbox. FK locales/composites, unicités partielles, échéances et scopes ; downgrade
peuplé refusé, tests uniquement sur base Accounts *_test.

La nouvelle file réutilise le transport local et la clé Fernet C02, pas une clé de secret MFA.
Payload chiffré lié à ses identifiants/type/destinataire/jeton, vérifié avant envoi ; effacement après
SMTP/annulation/expiration. Retry exponentiel borné sans extension des délais, Message-ID stable,
**au moins une fois**, doublon possible après acceptation avant commit. Notifications initialement
retentées jusqu’à 24 h (paramètre technique configurable), jamais de mot de passe/token dedans.
Le worker alterne les files initiale et sécurité pour éviter une starvation d’un type de message.
Aucun fournisseur de production, achat ou envoi externe : Mailpit local seulement.

Routes backend, sous /api sur l’origine Portal HTTPS ; JSON/Origin et corps 8 Kio, erreurs génériques
sans entrée privée, no-store. Les actions à session nécessitent X-CSRF-Token ; les confirmations par
lien/reset sont des preuves de capacité autonomes, n’utilisent pas le cookie pour autoriser l’action.

| Route | Corps / effet |
| --- | --- |
| POST /security/step-up | action/current_password et new_password ou new_email selon action ; proof/expiration |
| POST /security/password/change | proof/new_password ; mutation et révocation globale |
| POST /security/logout-all | proof ; toutes sessions Portal et intention Game tous appareils/univers |
| POST /security/password/reset/request | email ; 202 générique, aucun auto-login |
| POST /security/password/reset/confirm | token/new_password ; reset et effets globaux |
| POST /security/email/request | proof/new_email ; confirmation_required, pas adresse active |
| POST /security/email/confirm | token ; additional_confirmation_required ou email_changed |

Paramètres PORTAL_SECURITY_IP_LIMIT=30/h, SECURITY_SUBJECT_LIMIT=10/h, RESET_RESPONSE_FLOOR_MS=150,
SECURITY_NOTICE_HOURS=24. Limites par opération, distinctes du login/inscription. Aucun verrouillage
permanent ; CORS credentials refusé par défaut, pas d’origine Game autorisée par implication.

Validation : concurrence/rollback/délais exacts/scopes de preuves, interdiction MFA/password-only,
révocation/login en vol, notifications sans secrets, SMTP en panne/retry et deux workers, UI mobile/
clavier. Résultats réellement exécutés dans progress et CI de la PR. UI avec API interceptée distincte
des intégrations API/PostgreSQL et smokes TLS ; recette navigateur HTTPS complète à C09.
C05 et son intégration aux guards C04 sont livrés ; suite : **C06 lobby/interface interne**. 5D exclu, PR #7 non fusionnée.

Sources : [OWASP récupération](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html),
[OWASP autorisation d’action](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html),
[HMAC Python](https://docs.python.org/3/library/hmac.html). Aucune décision produit 5B modifiée.
