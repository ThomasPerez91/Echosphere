# Exploration

**Statut : contrat minimal étape 7 validé explicitement le 31/10/2026 ; implémenté sur PR #10, [contrat technique](../03-technical/galaxy-api-ui.md). Q09 reste totalement ouverte.**


Explorer transforme l'incertitude en information utile : routes, systèmes, planètes, traits,
anomalies et présences étrangères. Les anomalies sont envisagées ; leur contenu avancé est post-MVP.
Le joueur compare des directions possibles puis engage des moyens dans une mission asynchrone.

## Résolution envisagée

Vérifier une destination atteignable et les moyens requis, réserver la flotte puis enregistrer
une échéance. À la résolution, produire un rapport et actualiser les connaissances autorisées.
Le niveau de détail dépendra du type de mission et des capteurs (Q08).

## Limites

Pas de découverte obtenue gratuitement par un clic sur la carte. Les IA explorent aussi et peuvent
ignorer un voisin. Une information ancienne ne donne pas automatiquement l'état actuel d'un système.
Le coût, la durée, les risques et les moyens minimums restent à définir avec les flottes.

## Validation future

Tests de découverte répétée, de rapport périmé, d'accès interdit à un système inconnu et de reprise
d'une mission après redémarrage. Ne rien implémenter de ce domaine à l'étape 0.


## Références

- [Vision](../00-product-vision.md) · [Questions ouvertes](../05-project/open-questions.md)
- [Boucle](core-loop.md) · [Équilibrage](balance-philosophy.md)
- [Temps serveur](../03-technical/event-engine.md)

## Proposition Exploration minimale — G01, 31/10/2026

**Contrat validé par l’utilisateur le 31/10/2026 avec amendements.** Le texte historique
« réserver la flotte » ci-dessus décrit la cible Fleet, hors étape 7. L’intitulé G01 est conservé
pour les liens. Le [plan étape 7](../05-project/step-7-plan.md) porte la réalisation G02–G10 autorisée
après CI préalable verte, sans validation intermédiaire sauf nouvelle décision produit réelle.

### Moyen engagé et prix proposés

Une **capacité d’expédition abstraite**, limitée à une mission active par Empire, sans file suivante.
Elle représente la préparation/engagement d’une expédition, pas une unité possédée : aucun vaisseau,
spawn, moteur, équipement, cargo, mouvement Fleet, combat ou inventaire militaire caché.
Le coût et l’occupation de cette capacité sont les moyens engagés réellement persistés.
Ce mécanisme est explicitement transitoire pour étape 7 ; Fleet pourra fournir un autre engagement
au domaine Exploration dans un futur contrat validé. Les missions/rapports/connaissances et les
missions en vol garderont leur contrat/snapshot d’origine, sans conversion silencieuse en flottes.
Humains et futures IA utiliseront ce même service/coût/capacité.

| Sujet | Proposition initiale balançable |
| --- | --- |
| Source | Colonie explicitement choisie, appartenant à l’Empire, dans la galaxie générée ; origine = son système |
| Coût | 50 Alliages, `50 + 10 × h` Flux, 25 Données ; `h` = sauts aller du chemin validé |
| Durée | `15 min × (2 × h + 1)` : aller + retour + étude ; premier voisin = 45 min |
| Réservation | Débit intégral et capacité engagée à l’acceptation ; rien à payer au handler de fin |
| Résolution | Une échéance à la fin de l’expédition ; pas de révélation intermédiaire à l’aller |
| Risques/rappel | Succès déterministe si commande acceptée ; aucune perte aléatoire, annulation, rappel ou remboursement dans étape 7 |
| Bonus/vitesse | Aucun bonus Research actuel appliqué implicitement ; profil initial 1x, coûts/durée issus des nouvelles données épinglées |

Nouveau ruleset complet validé `v0.3` avec Galaxy/Exploration, v0.1 et v0.2 immuables.
Micro-unités et microsecondes entières, dépassements refusés, dates UTC serveur ; aucun tarif
copié en constante de service. Les vitesses accélérées de recette restent test-only.
Les anciennes parties gardent leurs versions et ne reçoivent ni galaxie ni engagement gratuit.
L’absence d’annulation est un choix proposé ici, pas une déduction des règles de remboursement Colony.

### Frontière explorable et connaissance initiale

Initialisation explicite après affectation d’une vraie colonie de départ : système d’origine
MONITORED pour les informations effectivement observables depuis sa colonie, structure cartographiée ;
voisins directs DETECTED avec identifiant opaque et position approximative ; routes incidentes
connues uniquement entre l’origine connue et ces voisins. Tout le reste UNKNOWN, absent des réponses.
Aucun autre site de départ, total de systèmes, seed ou paramètre de génération envoyé au client.

Destination validée : un système DETECTED atteint depuis une colonie de l’Empire par des routes
connues, avec tous les systèmes intermédiaires MAPPED ou MONITORED. UNKNOWN refusé comme identifiant
inexistant, pas de recherche de chemin omnisciente. Système déjà MAPPED/MONITORED : pas de mission
d’étude répétée dans cette étape ; les mécanismes de surveillance active future restent distincts.
Serveur calcule le plus court chemin de ce sous-graphe autorisé, départage stable interne ;
client ne choisit ni raccourci, ni durée, ni coûts. Devis daté dans la projection puis recalcul sous
verrou à l’acceptation ; changements exposés avant confirmation d’une nouvelle intention si nécessaire.

Fin : destination MAPPED durablement, nom/position exacte/planètes/capacités structurelles connues ;
voisins directs de la destination deviennent DETECTED s’ils étaient UNKNOWN, routes incidentes
révélées avec les deux extrémités maintenant connues. Aucune route entre deux systèmes restés UNKNOWN,
aucun voisinage récursif. Fusion monotone : découverte répétée ne rabaisse pas MONITORED ou MAPPED.
Les informations d’un autre Empire ne sont jamais fusionnées automatiquement.

Rapport persistant unique par mission : date logique de fin, chemin connu, découvertes autorisées,
structure observée ; lecture ultérieure ne joint pas l’état omniscient courant pour enrichir ce rapport.
Pas de présence étrangère/force militaire/stock actuel inventé. Les seules données dynamiques
initiales surveillées concernent ses propres colonies ; toute observation dynamique est limitée
par son contrat et datée. En perte de surveillance, MONITORED → MAPPED, structure et dernier
`last_seen_at` conservés ; information ancienne explicitement étiquetée. Exploration ne fournit
aucun monitoring permanent à distance. Le worker tardif ne prétend pas avoir observé le présent :
`observed_at = due_at`, `processed_at` séparé ; structure générée immuable dans ce lot.

### Mission, temps et autorité

Commande atomique : autorisation, rattrapage complet, contrôle destination/chemin/capacité/stock,
réservation, mission et ScheduledEvent `EXPLORATION_COMPLETE`. Snapshot immuable du ruleset,
chemin, coûts, durée effective, origine/destination, type d’engagement et version du résultat.
État active/completed ; échec technique du scheduler reste retry/blocked opérateur avec engagement
conservé, jamais faux succès ou remboursement silencieux. Une corruption persistée doit faire rollback.

Un EventStream Exploration par Empire lie explicitement Empire/Universe ; la connaissance et les
rapports de cet Empire sont écrits sous ce même stream, sans verrou de stream d’un autre Empire.
Le handler vérifie mission/universe/stream/clé/date/snapshot, écrit rapport + découvertes + fin de
mission + libération de capacité dans la transaction scheduler. Aucun commit interne, débit tardif,
appel Portal ou second stream. Un crash avant commit ne produit aucun effet ; après commit, rejeu
sans double rapport/découverte/coût. Navigateur fermé ou session expirée n’interrompt pas la mission.

Ordre validé des locks, sous réserve des tests pour les commandes : principal Game → Exploration → Research → Colony
source (sources triées par UUID si plusieurs deviennent nécessaires). Initialisation des adaptateurs
à sérialiser sur Empire avant tout stream ; préférer leur création explicite au provisionnement.
Research précède toujours Colony comme aujourd’hui. Aucun chemin Research/Colony ne prend ensuite
Exploration ; les handlers conservent leur seul stream. Les lectures Galaxy rattrapent uniquement
Exploration avant projection ; les devis financiers coordonnent aussi Research/Colony dans cet ordre.
Les mutations de connaissance futures devront respecter cette autorité ; aucun verrou multi-Empires
dans étape 7. Recette et tests doivent vérifier cet ordre réel, y compris premières initialisations.

Idempotence HTTP par membership + clé d’intention ; même corps rejoué retrouve sa mission même
terminée sans repayer ; contenu différent avec même clé → conflit. Deux participants d’un même
Empire partagent la capacité mais ont des espaces de clés séparés. Un second Empire garde sa propre
connaissance et sa propre capacité. Toute commande rejouée reste soumise aux droits/session actuels.

Permissions validées : `galaxy.read`, `exploration.read`, `exploration.start`, sans attribution aux
bindings existants. Lecture de carte/détail depuis la connaissance de l’Empire lié ; lecture des
missions exige exploration.read ; démarrage exige ces trois droits et colony.read sur sa source.
Ni colony.construct ni privilège plateforme implicite. GameSession/access/binding/universe,
CSRF/origin, non-fuite et sérialisation révocation repris de 5D/Research. Worker sans session humaine.
Les payloads internes/snapshots complets ne deviennent jamais des DTO publics.

### Amendements validés et portée

Le système de sa propre colonie reste MONITORED tant qu’une présence propre légitime fournit
l’observation locale ; aucun timer artificiel de dégradation. À disparition d’une vraie source,
MONITORED → MAPPED avec structure/last_seen_at conservés. Aucun monitoring distant permanent.
Débit une fois, durée snapshotée, aucun bonus implicite, aucune annulation/rappel/remboursement
ou perte aléatoire. UNKNOWN = absence de Knowledge ; un rapport immuable par mission,
observed_at = due_at et processed_at séparé. Relations typées et FK Universe/Empire cohérentes.
Q04/Q07 hors portée et Q09 totalement ouverte ; pas de Fleet, IA, colonisation, combat, espionnage,
anomalie avancée, capteur avancé ou System View complète. Étape 8 non commencée.
