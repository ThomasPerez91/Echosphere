# Défense planétaire — proposition DEF-00 (ruleset v0.13)

**Statut : proposition de Claude du 11/11/2026, à valider par l’utilisateur ; rien n’est
implémenté.** Elle applique les décisions produit closes [Q30–Q38](planetary-defense.md) et chiffre
un premier lot jouable. Les valeurs sont provisoires et réglables dans le ruleset, comme toute la
balance.

## Découpage

| Lot | Contenu | Hors lot |
| --- | --- | --- |
| **DEF-01** | Centre de défense, trois familles de modules, emplacements SURFACE/ORBITAL, combat des modules aux côtés de la garnison, modules endommagés et réparation, entretien en Flux | Boucliers à recharge, états ALERT/COMBAT, renseignement fin, flotte alliée présente |
| DEF-02 | Bouclier (combat-v2 : réserve absorbée avant la coque), états NORMAL/ALERT/COMBAT et surconsommation, Support/Repair | Ciblage fin |
| DEF-03 | Sensor/EW et renseignement daté (Q37), ciblage conditionné (Q36), flotte alliée en défense (Q32) | — |

## DEF-01 en détail

### Réseau et espace (Q30/Q38)

- **Centre de défense** : bâtiment clé unique, sur un emplacement réservé comme les autres clés,
  prérequis Complexe industriel 2. Son niveau N donne la **capacité du réseau** : 2 × N modules.
- Un module **SURFACE** occupe un vrai secteur de la colonie, qui n’accueille alors plus
  d’infrastructure ; un module **ORBITAL** occupe un vrai emplacement orbital. Pas de réserve
  gratuite : défendre coûte de la place à l’économie.
- Construction dans l’onglet **Défense** de la colonie, avec la même file que les infrastructures :
  trois ordres dont un actif, réservation immédiate, annulation 100/80.

### Familles de modules (Q31)

| Module | Famille | Emplacement | Coût (Alliages / Flux / Données) | Durée | Coque / attaque | Efficace contre |
| --- | --- | --- | --- | --- | --- | --- |
| Batterie de défense ponctuelle | Point Defense | SURFACE | 600 / 200 / 0 | 20 min | 400 / 60 | Intercepteurs (×1,5), faible contre croiseurs (×0,75) |
| Canon anti-vaisseaux | Anti-Ship | SURFACE | 900 / 400 / 0 | 30 min | 600 / 180 | Croiseurs (×1,5), faible contre intercepteurs (×0,75) |
| Plateforme orbitale | Anti-Ship | ORBITAL | 1 200 / 600 / 100 | 40 min | 1 200 / 140 | Frégates (×1,5), faible contre intercepteurs (×0,75) |

Bouclier, Sensor/EW et Support/Repair apparaissent dans l’onglet Défense comme « à venir »
(DEF-02/03), sans donnée inventée.

### Combat (Q32/Q35)

- Les modules opérationnels combattent dans le camp du défenseur, avec la garnison, selon le moteur
  actuel : rounds simultanés, meilleure efficacité. Ils ne bougent jamais et ne sont jamais une
  flotte.
- Un module « perdu » au combat devient **DAMAGED** : il ne combat plus et ne coûte plus d’entretien
  jusqu’à sa réparation. Il n’y a ni **DESTROYED** (pas de conquête) ni butin. **DISABLED** est
  réservé au manque de Flux.
- **Réparation** : 40 % du coût et 50 % de la durée, dans la file de la colonie.
- Le rapport de bataille de l’attaquant montre les modules adverses observés, comme pour les
  vaisseaux. Le défenseur voit ses pertes.

### Énergie (Q34, version DEF-01)

- Chaque module opérationnel consomme du Flux en continu (2/h pour la défense ponctuelle, 4/h pour
  le canon, 6/h pour la plateforme), déduit de la production horaire de la colonie : le moteur reste
  à taux constants.
- Si la production nette de Flux devenait négative, des modules passent **DISABLED** dans un ordre
  déterministe (plateformes, puis canons, puis batteries, à l’intérieur par identifiant), jusqu’à
  ce que la production soit de nouveau ≥ 0. Ils se réactivent seuls quand la production le
  permet.
- Les états NORMAL/ALERT/COMBAT et la surconsommation en alerte arrivent en DEF-02.

### IA, interface, portée

- L’IA utilise les mêmes services : construire un Centre de défense quand elle a été attaquée,
  puis une batterie par attaque subie, dans sa limite de capacité.
- L’onglet Défense de la colonie présente la capacité du réseau, les secteurs et emplacements
  orbitaux occupés, les modules avec leur état, la construction et la réparation. Le bloc « Statut
  de défense » de la maquette est rempli avec ces seules données.
- Portée : ruleset **v0.13**, nouvelles parties seulement ; v0.12 et antérieures restent sans
  défense.

[Décisions Q30–Q38](planetary-defense.md) · [Combat](combat.md) · [Colonie v0.11](colony-v011.md)
