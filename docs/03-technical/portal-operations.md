# C09 — recette de clôture et opérations Portal/Game

**Statut : recette C09 réalisée sur PR #7 et relancée par Claude Code sur le contenu final le 2026-10-30 ; 5C prêt pour revue finale, CI du SHA final consignée dans PR #7. Aucune exposition production autorisée.**
Ce document précise les opérations déléguées de 5C, sans fermer les reports Q48/Q49/Q55 ou modifier
les [décisions 5B](identity-contracts.md). [Parcours C08](portal-game-ui.md), [plan 5C](../05-project/step-5c-plan.md).

## Recette reproductible

Lire AGENTS et le checkpoint avant toute commande. Un seul écrivain ; bases des suites *_test
et opt-in RUN_DB_TESTS=1, jamais les bases à conserver. Exécuter suites backend Game et Portal,
lint/tests/build et Chromium des deux frontends, documentation/liens/diff. Puis seulement les smokes
qui arrêtent volontairement PostgreSQL : ne pas les superposer aux suites utilisant le même serveur.

Après Compose build/up --wait : alembic check sur chacun des backends, smokes Game, Portal, contrôle
mTLS et handoff. La dernière recette utilise un projet aléatoire sans port hôte et supprime ses
propres volumes ; aucune suppression des volumes de la pile courante.

`python3 scripts/smoke_handoff_compose.py` exerce désormais :

- login réel, entrée automatique dans le shell, scopes/cookies/échéances, 320/1440 et clavier ;
- arrêt réel de Portal API et du worker de contrôle, session Game existante utilisable localement ;
- construction acceptée créée uniquement comme fixture dans Game *_test ; le worker temporel réel
  doit la terminer pendant la panne Portal, avec règles 5A inchangées et sans API Colony ;
- reprise API Portal en maintenant la liaison de contrôle arrêtée, logout Portal affichant pending ;
- reprise du worker de contrôle, révocation persistée livrée/acquittée, reçu UI affichant terminé
  puis refus 401 de l’ancienne session Game ;
- pg_dump/pg_restore des deux bases dans des bases *_test distinctes, vérification des têtes Alembic,
  sans exposer les snapshots restaurés comme services authentifiés.

Les fixtures sont réservées au projet temporaire et au nom de DB test contrôlé ; aucun compte,
monde ou commande de démonstration dans la pile conservée. Résultats réellement exécutés et SHA/CI
dans progress/PR ; aucun test matériel Windows, tactile, lecteur d’écran ou charge hostile déduit.

## Rotation des tickets

Les clés de signature sont indépendantes des certificats mTLS, des clés mail, MFA et reçu. Manipuler
les fichiers/volumes dans l’environnement autorisé, jamais les valeurs dans le chat ou Git.

1. Créer une nouvelle paire Ed25519 avec la bibliothèque de l’environnement ; identifiant distinct.
   Clé privée 0600 dans le secret store Portal, public seul dans Game.
2. Prédistribuer le nouveau public dans HANDOFF_PUBLIC_KEYS de chaque processus API Game, en
   conservant l’ancien ; redémarrer/recharger les processus et vérifier l’admission du nouveau kid.
3. Activer PORTAL_HANDOFF_KEY_ID et sa clé privée côté Portal seulement après ce contrôle.
4. Conserver le recouvrement des tickets 60 s et des sessions souhaitées, au plus leurs échéances
   initiales. Retirer l’ancien kid invalide ses sessions au prochain usage ; informer les opérateurs.
5. Clé compromise : retirer immédiatement son kid de la configuration Game et relancer ces processus,
   traiter les sessions affectées et révoquer compte/appareil selon le périmètre identifié. Nouveau
   handoff obligatoire ; aucun fallback sur une URL ou clé apportée par le ticket.

La recette PostgreSQL C09 teste recouvrement et retrait local de kid avec deux clés temporaires.
Pas de rotation automatique silencieuse ni de fournisseur de clés production imposé.

## Certificats mTLS et clés de chiffrement

Les CA privées du développement ne sont montées que dans init ; chaque service possède sa clé privée
et les seules CA/publics nécessaires. Feuilles dev 30 jours ; init refuse une feuille expirée ou un
public divergent. Avant échéance : préparer CA/feuilles de remplacement sur environnement autorisé,
prédistribuer la confiance, épingler le nouveau certificat Portal avec control_next_peer_cert, faire
la bascule puis retirer l’ancien. Tester CA, DNS, EKU, pin et reprise d’outbox avec la recette mTLS.
Ne pas retirer une cible de livraison pour masquer une révocation non acquittée.

Clés mail/MFA/reçu distinctes : les sauvegarder comme secrets séparés des DB. Rotation de mail/MFA
requiert lecture sous ancienne clé et rechiffrement transactionnel des secrets en attente ; aucun
outil automatique de migration de ces clés livré par 5C. La clé reçu ne protège que des capacités
quinze minutes : son remplacement invalide ce suivi, sans annuler les révocations persistées ni
rétablir de session. Configurer et recetter ces procédures avant production sous Q49.

## Sauvegarde, restauration et anti-rejeu

Sauvegarder Accounts et Game indépendamment avec leurs WAL/PITR et les secrets nécessaires dans un
stockage protégé ; politique/fréquence/rétention de production avant exposition, pas de prestataire
ou infrastructure payante déduits de 5C. La recette pg_dump/restore valide un aller-retour local,
pas un RPO/RTO de production ni une restauration après destruction physique.

Ne jamais remettre directement en ligne une ancienne sauvegarde avec ses cookies/tickets anciens.
Isoler les endpoints authentifiés durant la restauration ; conserver/restaurer les générations,
ledger et intentions durables ; réconcilier l’intention Accounts et l’état Game sans abaisser les
révisions. Invalider les preuves d’avant restauration (rotation du kid et des sessions Portal/Game,
révocations persistées), traiter les accès contradictoires, puis seulement réouvrir après recette.
Si une clé MFA/mail manque, bloquer le parcours concerné : aucun bypass email ou nouveau secret
régénéré silencieusement. Une restauration coordonnée et sa barrière de sécurité opérationnelle
restent une exigence avant production ; les DB de test restaurées ici ne sont jamais exposées.

Audit sécurité : rétention initiale 90 j ; ne pas confondre avec les marqueurs minimaux anti-rejeu.
Aucune purge automatique des generations, consommations ou ledger dans 5C. L’archivage/nettoyage
sous charge devra prouver l’absence de résurrection de droits avant activation. Les échéances de
session sont vérifiées même sans purge ; supprimer une ligne pour réduire la taille n’est pas un
mécanisme d’expiration. Ne pas appliquer down -v/downgrade sur données à conserver.

## Conditions de sortie 5C et limites

5C livre comptes/sécurité/lobby/handoff/contexte, pas une partie jouable ou une API économique.
Clôture pour revue finale après suites et CI du SHA publié, migrations sans dérive, recettes de
reprise et documentation cohérente. Revue indépendante possible selon le protocole, jamais simulée.
Aucun merge, déploiement, tag/release ou début de 5D sans instruction explicite.

Restent hors clôture locale : fournisseur/domaines/email et secrets/PKI/limites/observabilité de
production Q49, support renforcé Q48, modes Q55/Q19–Q29/Empire partagé Q21, commandes Colony 5D,
charge hostile et isolation d’hôte/réseau étape 17. Ces limites ne sont pas des mécanismes livrés
ou des arbitrages fermés par implication. Aucun feu vert d’exposition publique n’est donné par 5C.
