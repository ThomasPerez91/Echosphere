"""Generate game_data/rulesets/v0.13 from v0.12 (DEF-01, planetary defense, validated 11/11/2026).

Run from the repository root: python3 scripts/rulesets/make_v013.py
Balance values are provisional. v0.13 = v0.12 plus a Défense center (key building), three
defense modules in the infrastructure catalogue (two SURFACE, one ORBITAL), their combat-v1
classes and the defense rules (capacity, upkeep, disable order, repair). Shields, alert states,
sensors and support modules are DEF-02/03.
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "game_data" / "rulesets"
SOURCE, TARGET = ROOT / "v0.12", ROOT / "v0.13"


def level(cost, seconds):
    return {"cost": dict(zip(("alloys", "flux", "data"), cost, strict=True)),
            "duration_seconds": seconds, "production": {}, "construction_bonus_bps": 0,
            "capacity": None}


def building(cost, seconds, *, unique=False, requires=None, orbital=False, growth=130):
    rule = {
        "max_per_colony": 1 if unique else None,
        "requires": requires or {},
        "explicit_levels": [level(cost, seconds)],
        "scaling_after_level": 1,
        "scaling": {
            "cost": {"numerator": growth, "denominator": 100},
            "duration": {"numerator": 120, "denominator": 100},
            "production": {"numerator": 100, "denominator": 100},
            "capacity": {"numerator": 100, "denominator": 100},
            "bonus_increment_bps": 0,
        },
    }
    if orbital:
        rule["placement"] = "orbital"
    return rule


BUILDINGS = {
    "defense_center": building((1500, 800, 300), 900, unique=True,
                               requires={"industrial_complex": 2}, growth=160),
    "point_defense": building((600, 200, 0), 1200, requires={"defense_center": 1}),
    "anti_ship_battery": building((900, 400, 0), 1800, requires={"defense_center": 1}),
    "orbital_platform": building((1200, 600, 100), 2400, requires={"defense_center": 1},
                                 orbital=True),
}
DEFENSE = {
    "defense_version": "defense-v1",
    "center": "defense_center",
    "capacity_per_level": 2,
    "modules": {
        "point_defense": {"family": "point_defense", "placement": "surface",
                          "combat_class": "point_defense", "upkeep_flux": 2},
        "anti_ship_battery": {"family": "anti_ship", "placement": "surface",
                              "combat_class": "anti_ship", "upkeep_flux": 4},
        "orbital_platform": {"family": "anti_ship", "placement": "orbital",
                             "combat_class": "orbital_platform", "upkeep_flux": 6},
    },
    # Platforms first, then cannons, then batteries (DEF-00), by sector inside a family.
    "disable_order": ["orbital_platform", "anti_ship_battery", "point_defense"],
    "repair_cost_bps": 4000,
    "repair_duration_bps": 5000,
}
MODULES = {
    "point_defense": ({"hull": 400, "attack": 60}, {"interceptor": 15000, "frigate": 10000, "cruiser": 7500}),
    "anti_ship": ({"hull": 600, "attack": 180}, {"interceptor": 7500, "frigate": 10000, "cruiser": 15000}),
    "orbital_platform": ({"hull": 1200, "attack": 140}, {"interceptor": 7500, "frigate": 15000, "cruiser": 10000}),
}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    for path in TARGET.glob("*.json"):
        data = json.loads(path.read_text())
        if data.get("version") == "v0.12":
            data["version"] = "v0.13"
        write(path, data)
    path = TARGET / "infrastructures.json"
    catalogue = json.loads(path.read_text())
    catalogue["infrastructures"].update(BUILDINGS)
    write(path, catalogue)
    path = TARGET / "combat.json"
    combat = json.loads(path.read_text())
    ships = list(combat["classes"])
    combat["modules"] = {name: stats for name, (stats, _) in MODULES.items()}
    every = ships + list(MODULES)
    for ship in ships:
        combat["matchups_bps"][ship].update(dict.fromkeys(MODULES, 10000))
    for name, (_, against) in MODULES.items():
        combat["matchups_bps"][name] = {c: against.get(c, 10000) for c in every}
    write(path, combat)
    write(TARGET / "defense.json", {"version": "v0.13", **DEFENSE})
    path = TARGET / "ai.json"
    ai = json.loads(path.read_text())
    # DEF-00: a Défense center once attacked, then one battery per attack suffered.
    ai["defense"] = {"center_utility": 800, "module_kind": "point_defense", "module_utility": 700}
    write(path, ai)


if __name__ == "__main__":
    main()
