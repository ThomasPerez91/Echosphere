# C08 — parcours compte/lobby et contexte Game

**Statut : implémenté sur PR #7, non intégré à master ; recette de clôture C09 réalisée.**
[Contrats 5B](identity-contracts.md), [handoff C07](game-handoff.md) et
[guide visuel](../visual-reference/README.md) conservés.

Le handoff traverse les origines par formulaires POST automatiquement soumis par un script local
à nonce CSP. Chaque page conserve son bouton de secours sans JavaScript ; aucun ticket dans URL,
stockage navigateur ou script. Origines exactes/CSRF, referrer strict-origin et contrôles C07 inchangés.
Erreurs de navigation HTML : explication et retour lobby, sans réafficher le ticket ou corps soumis.

L’échange ouvre `/#universe/<uuid>/empire`, dans le shell React existant. Le nom réel et les échéances
proviennent de Game. Sept domaines globaux conservés, liens internes gardant le scope univers,
responsive et clavier ; aucune projection économique ni commande Colony livrée. Les stocks restent
indisponibles ; présence d’une session ne signifie pas présence d’un Empire/colonie jouable.
`/api/game/<uuid>/view` reste un point d’entrée compatible, redirigeant vers le shell.

Lecture GET protégée par header bootstrap, aucune activité. Action explicite de navigation ou
actualisation : POST même origine, CSRF, corps JSON exactement vide. Session expirée/révoquée,
service indisponible, réponse malformée et changement de cookie sont distincts d’un accès confirmé ;
retry en lecture seulement, aucune mutation automatiquement rejouée. Dates serveur, pas de timestamp
d’activité client. Les timers de limite relisent le serveur sans renouveler session/droits.
Logout Game JSON invalide la session sans effacer un éventuel nouveau cookie reçu dans un autre
onglet pendant la réponse. Le cookie devenu inutilisable sera remplacé au prochain handoff. Même règle pour le logout Portal :
invalidation serveur immédiate, sans Set-Cookie tardif effaçant une connexion plus récente.

Portal vérifie explicitement le compte au démarrage : panne ≠ déconnexion. Les résultats annulés
ou dépassés ne remplacent pas une lecture plus récente, y compris sous StrictMode. Refus 401 au
lobby ramenant à la connexion ; échec de lecture masquant les liens d’entrée non reconfirmés.

## Suivi de déconnexion

Logout Portal courant ou tous appareils délivre un reçu chiffré **quinze minutes absolues**, cookie
`__Host-portal-revocation` Secure/HttpOnly/host-only. Clé Fernet dédiée `receipt.key`, distincte de
mail/MFA/ticket/mTLS, dans le volume privé Portal, jamais en DB ou Git. Le reçu lie uniquement
purpose/version, source durable, portée et expiration ; aucune API d’authentification ne l’accepte.
Un login normal ou une autre opération sensible efface un ancien reçu afin de ne jamais confondre
son acquittement avec une nouvelle demande. Pas de nouvelle table/migration. Source LogoutRequest ou AccountRevocation créée par l’opération
authentifiée ; aucun endpoint permettant au navigateur de choisir un identifiant de suivi.

GET `/auth/revocation-status` : header bootstrap/origine Portal, seulement état/portée/expiration,
sans identité, compte, liste de sessions ou privilèges. Acquittement de **toutes** les livraisons C06
requis pour afficher terminé. Actualisation de statut sans activité/renouvellement ; absent/expiré
n’est jamais présenté comme un succès. Une panne de génération du reçu n’annule pas une révocation
persistée : message prudent et suivi après reconnexion au lobby. Les autres changements sensibles
continuent d’indiquer leur attente ; leur détail est consultable après la nouvelle connexion requise.

## Recette

Tests ciblés JSON/CSRF/corps/origines, erreurs HTML, reçu falsifié/expiré/sans pouvoir d’authentification,
UI chargement/erreurs/expiration/logout/retry sans POST automatique ; suites précédentes conservées.
Chromium réel via scripts/smoke_handoff_compose.py : entrée automatique vers le shell, deux origines
HTTPS, 320/1440, retour lobby, activité explicite et logout. Résultats exacts dans progress ; C09
porte la recette finale, les limites opérationnelles et la décision de clôture pour revue.
