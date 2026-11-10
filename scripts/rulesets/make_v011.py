"""Generate game_data/rulesets/v0.11 from v0.10 (COL-11, colony v0.11 design).

Run from the repository root: python3 scripts/rulesets/make_v011.py
Balance values are provisional (design doc docs/01-game-design/colony-v011.md); the early pace was
checked with a greedy simulation (action every ~8 min the first 2 h, ~20 min up to 12 h).
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "game_data" / "rulesets"
SOURCE, TARGET = ROOT / "v0.10", ROOT / "v0.11"
EXPLICIT = 10  # explicit levels, then constant scaling
COST_G, DURATION_G, PRODUCTION_G = 1.35, 1.55, 1.1
UNIQUE_G = 1.45


def ratio(value):
    return {"numerator": round(value * 100), "denominator": 100}


def levels(cost, duration0, growth, production=None, bonus=None, capacity=None):
    rows = []
    for n in range(1, EXPLICIT + 1):
        c = {r: round(v * growth ** (n - 1)) for r, v in zip(("alloys", "flux", "data"), cost)}
        rows.append({
            "cost": c,
            "duration_seconds": round(duration0 * DURATION_G ** (n - 1)),
            "production": {production[0]: round(production[1] * n * PRODUCTION_G ** (n - 1))}
            if production else {},
            "construction_bonus_bps": bonus * n if bonus else 0,
            "capacity": round(capacity * 1.5 ** (n - 1)) if capacity else None,
        })
    return rows


def rule(cost, duration0, *, unique=False, requires=None, production=None, bonus=None,
         capacity=None):
    growth = UNIQUE_G if unique else COST_G
    return {
        "max_per_colony": 1 if unique else None,
        "requires": requires or {},
        "explicit_levels": levels(cost, duration0, growth, production, bonus, capacity),
        "scaling_after_level": EXPLICIT,
        "scaling": {
            "cost": ratio(growth),
            "duration": ratio(1.35),
            "production": ratio(1.15 if production else 1),
            "capacity": ratio(1.3 if capacity else 1),
            "bonus_increment_bps": 500 if bonus else 0,
        },
    }


def main():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    for path in TARGET.glob("*.json"):
        data = json.loads(path.read_text())
        data["version"] = "v0.11"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def update(name, change):
        path = TARGET / f"{name}.json"
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def colony(d):
        d["initial_stocks"] = {"alloys": 800, "flux": 500, "data": 300}
        d["initial_infrastructures"] = ["extraction_complex", "flux_reactor", "data_node"]
        d["level_cap"] = {"base": 14, "sectors_divisor": 2}
    update("colony", colony)

    def infrastructures(d):
        d["infrastructures"] = {
            "extraction_complex": rule((40, 15, 0), 60, production=("alloys", 75)),
            "flux_reactor": rule((40, 10, 0), 60, production=("flux", 62)),
            "data_node": rule((45, 20, 0), 60, production=("data", 30)),
            "industrial_complex": rule((120, 60, 20), 120, unique=True, bonus=500),
            "logistics_center": rule((150, 80, 20), 180, unique=True,
                                     requires={"extraction_complex": 3}, capacity=20000),
            "orbital_shipyard": rule((150, 80, 30), 120, unique=True,
                                     requires={"industrial_complex": 2}),
            "research_center": rule((120, 60, 60), 120, unique=True,
                                    requires={"data_node": 3}),
        }
    update("infrastructures", infrastructures)

    shipyard = {"probe": 1, "freighter": 1, "extractor": 2, "colonizer": 3, "interceptor": 2,
                "frigate": 4, "cruiser": 6}

    def fleets(d):
        for key, level in shipyard.items():
            d["classes"][key]["requires"] = {"orbital_shipyard": level}
    update("fleets", fleets)

    def research(d):
        d["facility"] = {"kind": "research_center", "levels": {"1": 1, "2": 3}}
    update("research", research)

    def ai(d):
        d["unlocks"] = {"orbital_shipyard": 700, "research_center": 600}
    update("ai", ai)


if __name__ == "__main__":
    main()
