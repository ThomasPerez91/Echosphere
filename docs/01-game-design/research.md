# Recherche

**Statut : Q05 close ; étape 6 livrée et intégrée via PR #9, merge `437844e4`.**
Contrat validé explicitement ; [réalisation et API](../03-technical/research-api-ui.md).


La recherche est globale à l’empire (précision validée dans la mission de passation du 2026-10-28). Quatre domaines de travail : Ingénierie,
Énergétique, Calcul, Xénoscience. Les noms et les technologies sont provisoires.

## Lisibilité et réversibilité

Un arbre relativement court doit créer des orientations sans condamner un empire sur une décision
précoce. Éviter des centaines de technologies. Le joueur doit comprendre coût, durée et effet avant
confirmation. Une recherche active et la programmation de la suivante font partie du parcours cible.

## Autorité et échéances

Les services Game sont communs aux humains et futures IA, sans bypass, technologie ou ressource
gratuite. Ressources, prérequis et scopes sont vérifiés dans la transaction. Le résultat s’applique
une seule fois à l’échéance ; le navigateur peut estimer le temps mais ne valide pas la technologie.

## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Q05 — contrat validé, 31/10/2026

**Statut : Q05 Clos produit — implémentation étape 6.** Validation explicite utilisateur reçue
après la proposition du 31/10/2026. R02–R09 autorisés sur PR #9 sans nouvel arrêt intermédiaire,
sauf arbitrage produit non couvert. Aucun merge ni étape 7 autorisé.

Les durées et coûts sont **figés à l’acceptation**, même pour la suivante : acquérir Calcul I
entre-temps ne réduit jamais sa durée. Bonus applicables seulement aux nouveaux ordres acceptés.
Même règle pour Ingénierie/Énergétique/Xénoscience ; II remplace I (10 % net, jamais 15 %).


### File et orientation validées

| Sujet | Contrat Q05 |
| --- | --- |
| Parallélisme | **Une recherche active par Empire**, tous domaines confondus ; les constructions Colony continuent indépendamment |
| Programmation | **Deux ordres au total : un actif + un suivant**, jamais deux actifs ni une file par colonie/domaine/joueur |
| Ordre | FIFO ; la suivante démarre automatiquement à la date logique de fin de l’active, sans navigateur, Portal ou nouvelle validation humaine |
| Changer la suivante | Annuler la recherche en attente puis en programmer une autre ; pas de drag/reorder ni réécriture de l’intention existante en MVP |
| Prérequis | Technologies acquises, avec possibilité de programmer une technologie dont le seul prérequis encore manquant est la recherche active ; tous les autres prérequis doivent déjà être acquis |
| Niveaux | Technologies uniques acquises une fois ; pas de niveaux répétés/infinis dans l’étape 6. Des paliers nommés I/II sont deux identifiants distincts reliés par un prérequis |
| Exclusivité | Aucune technologie mutuellement exclusive MVP, aucun choix qui retire des connaissances déjà acquises |
| Orientation | Changer librement de domaine pour les prochains ordres ; les connaissances restent acquises. L’orientation vient du temps et des ressources investis, sans respec ni effacement de branche |

La limite de deux est validée pour Q05, **pas** la règle Colony 3/1 et **pas** les
trois places illustrées par research-view.png. Les domaines restent des catégories de technologies,
jamais quatre ressources ou jauges à récolter. À échéance exacte, traiter la fin avant une annulation :
une technologie déjà acquise ne redevient pas annulable.

### Coût et financement validés

Le code actuel conserve les stocks dans ResourceBalance **par Colony** ; il n’existe aucune caisse
Empire. Pour la première boucle, choisir explicitement **une colonie de financement par ordre**,
appartenant au même Empire et au même Universe. Elle paie l’ensemble du coût : aucune somme magique
de stocks, aucun prélèvement automatique dans d’autres colonies, aucune nouvelle monnaie.

Alliages / Flux / Données uniquement ; Données dominantes pour la recherche, avec coûts secondaires
Alliages/Flux configurables. Les montants et durées exacts sont des paramètres initiaux R02 dans
le catalogue versionné, pas des constantes UI/HTTP. Afficher coût, durée effective, prérequis,
effets et colonie payeuse avant confirmation ; refuser si cette colonie n’a pas les ressources.

**Réserver/prélever intégralement à l’acceptation**, y compris pour la suivante, après rattrapage
des échéances Empire et de la production de la colonie payeuse sous verrous. Aucun second paiement
au démarrage. Les colonies pourront financer des ordres différents, mais partagent la même file
Empire ; changer de colonie affichée ne change ni file, ni connaissances, ni ordre déjà accepté.
Sans colonie de financement autorisée, le catalogue et les acquis restent consultables sous leurs
droits, mais aucun lancement n’est possible ; pas de crédit gratuit de démarrage.

### Annulation et remboursement validés

- En attente : **100 % théorique** du coût réservé. Active : **80 % théorique**, progression abandonnée.
- Retour à la **colonie payeuse de chaque ordre**, plafonné par ressource à sa capacité ; surplus
  définitivement perdu, sans réserve cachée. UI avant confirmation : théorique, récupérable, perte,
  colonie destinataire et tous les ordres affectés. Idempotence : pas de nouveau remboursement sur retry.
- Annuler l’active annule également la suivante **seulement si elle en dépend** ; cette suivante a
  son remboursement queued 100 %. Si elle est indépendante, elle démarre immédiatement à la date
  logique d’annulation, sans nouveau débit. Ne jamais annuler une construction Colony.
- Aucune modification partielle : annulation, remboursements, effets sur la file et acquittement
  de l’ancienne échéance dans une transaction. Répartir la place disponible une seule fois par
  colonie/ressource si plusieurs ordres retournent vers la même colonie.

Ces 100/80 et le plafonnement sont validés pour **Research** par Q05. Q01/Q39 déjà validées ne sont
ni rouvertes ni étendues implicitement : leur application actuelle reste celle de la construction.
Le cycle futur de conquête/abandon/destruction de la colonie payeuse relève de Q07, hors étape 6 ;
aucun remboursement vers un autre Empire par défaut. Si cette appartenance est incohérente, refus
atomique et investigation, sans crédit dans une caisse de remplacement inventée.

### Snapshot, validité et acquis validés

À l’acceptation, conserver identifiant/version de technologie, définition des effets/prérequis,
coûts réellement prélevés, colonie payeuse, durée de base **et durée effective**, vitesse/bonus
appliqués et pourcentages de remboursement. La durée effective est figée aussi pour l’ordre en
attente : un bonus acquis entre-temps ne le reprice/rechronomètre pas. Sa date de début/fin est fixée
lorsqu’il devient actif. Aucun changement de fichier/ruleset ne modifie une commande acceptée.

Acquisition permanente dans le ruleset épinglé, prérequis revérifiés au démarrage. Une annulation
du prédécesseur est gérée par la cascade explicite ci-dessus. Aucun autre cas normal ne retire un
prérequis acquis : pas d’exclusivité ni de migration silencieuse du ruleset d’un univers.

Si un ordre programmé devient malgré tout invalide, **ne pas l’exécuter, débiter à nouveau ou
annuler silencieusement** : état d’attente bloquée expliqué, réservation conservée ; l’utilisateur
peut l’annuler au taux queued tant qu’il s’agit d’une incompatibilité métier récupérable. Aucun
successeur ne passe devant. Corruption/FK/snapshot invalide : mécanisme retry/blocked opérateur
existant, sans contournement joueur. Le contrat technique distinguera ce blocage d’ordre du blocage
d’un événement en erreur ; il ne doit pas rendre une simple annulation métier impossible.

Technologie déjà acquise : refuser un nouvel ordre sans coût. Déjà active/en attente : refuser un
doublon, même demandé depuis une autre colonie ou par un autre participant. Même clé d’intention
et même contenu : rejouer le reçu existant, même après fin/annulation, sans effet supplémentaire ;
même clé avec contenu différent : conflit, jamais remplacement implicite. Un rejeu du même événement
de fin ne doit ni ajouter un second acquis ni appliquer deux fois son effet.

### Petit catalogue et effets validés pour le premier lot

Recommandation : **huit technologies, deux nœuds distincts par domaine**, sans reprise du contenu
illustratif du mockup. Les noms restent balançables et les valeurs initiales 5/10 validées sont versionnées dans game_data.
R02 définit les identifiants, coûts/durées et validation stricte.

| Domaine provisoire | Deux paliers distincts validés | Effet concret, net au palier I / II |
| --- | --- | --- |
| Ingénierie | Fabrication modulaire I / II | Réduction du coût Alliages des nouveaux ordres de construction Colony : 5 % / 10 % |
| Énergétique | Gestion énergétique I / II | Réduction du coût Flux des nouveaux ordres de construction Colony : 5 % / 10 % |
| Calcul | Calcul scientifique I / II | Réduction de la durée des nouveaux ordres Research : 5 % / 10 % |
| Xénoscience | Protocoles d’analyse I / II | Réduction du coût Données des nouveaux ordres Research : 5 % / 10 % |

II nécessite I dans son domaine ; le bénéfice net II **remplace** I (10 % au total, pas 15 %).
Aucun prérequis de flotte, exploration, défense ou laboratoire inexistant. Les effets portent sur
l’Empire et s’appliquent aux **nouveaux ordres acceptés** après acquisition ; jamais aux coûts,
remboursements, dates ou snapshots déjà réservés. Ce choix apporte des effets réellement visibles
dans Colony/Research sans modifier rétroactivement la production de plusieurs streams à une même date.
Le calcul reste serveur en fractions/micro-unités, avec arrondis explicités en R02.
Aucun bonus de production continue, nouveau slot, déblocage de système futur ou bouton inopérant.

### Laboratoires et plusieurs colonies validés

**Aucun laboratoire requis ou construit dans l’étape 6**, vitesse de base instance 1x ; le champ
research_speed réservé ne constitue pas un laboratoire existant. Ne pas réutiliser le bonus industriel
de construction comme bonus Research sans règle spécifique.

Orientation retenue pour le futur lot Laboratoires : le meilleur laboratoire opérationnel de
l’Empire peut fournir un bonus de vitesse global (pas la somme automatique de toutes les colonies),
sans ajouter de recherche simultanée. Valeur appliquée et snapshotée à l’acceptation des nouveaux
ordres ; une amélioration/perte ultérieure ne change pas les ordres déjà acceptés. Aucun laboratoire,
scan de capacités runtime ou bonus fictif ajouté avant ce lot ; ses chiffres resteront dans game_data.
L’état autoritaire et les technologies restent sur Empire, même si la colonie payeuse/laboratoire change.

### Droits et future IA validés

Permissions explicites validées : research.read / research.start / research.cancel, séparées.
L’API applique GameSession → GameAccess/membership → Universe → EmpireBinding → permission → Empire.
Sans lecture autorisée, même réponse qu’un Empire inconnu, sans fuite ; mutations requièrent aussi
research.read. Les mutations de financement/remboursement exigent colony.read sur chaque colonie source,
pour afficher les stocks et pertes sans étendre implicitement research.read. Aucun besoin de colony.construct :
le droit de construire n’est pas le droit de rechercher. Le remboursement utilise les sources
persistées de l’ordre, jamais une destination choisie librement par le client.

Aucun droit implicite d’administrateur plateforme, de controller_type, ni grant automatique aux
bindings Colony existants. La future IA appelle les mêmes services/quotes/prérequis/coûts/files,
avec un contexte serveur de confiance limité à son Empire ; pas de faux User ou de bypass HTTP
pour les humains. Choix de domaine/source financière par ses futurs objectifs, sans ressource/tech gratuite.
La révocation/expiration interdit les nouvelles commandes humaines, pas l’achèvement des ordres
acceptés ; le worker n’a besoin ni de session, ni de présence, ni de Portal.

### Provenance et suite

Validation utilisateur reçue : contrat clos côté produit, implémentation R02–R09 autorisée.
Laboratoires hors étape 6. Future IA soumise aux mêmes services et limites d’information.
