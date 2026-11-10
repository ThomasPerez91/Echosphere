"""Generate game_data/rulesets/v0.12 from v0.11 (recette 10/11/2026: research tiers III and IV).

Run from the repository root: python3 scripts/rulesets/make_v012.py
Balance values are provisional. Tier III strengthens the domain effect (it replaces tier II);
tier IV opens a new effect and also needs tier II of a neighbour domain. Relations gain the
relation score terms (`standing`).
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "game_data" / "rulesets"
SOURCE, TARGET = ROOT / "v0.11", ROOT / "v0.12"

TIER3 = {"cost": {"alloys": 600, "flux": 480, "data": 1200}, "duration_seconds": 1200}
TIER4 = {"cost": {"alloys": 1800, "flux": 1440, "data": 3600}, "duration_seconds": 3600}
NEW = {
    "engineering_3": ("Fabrication modulaire III", "colony_alloys", 1500, ["engineering_2"]),
    "engineering_4": ("Assemblage orbital", "ship_cost", 1500, ["engineering_3", "energy_2"]),
    "energy_3": ("Gestion énergétique III", "colony_flux", 1500, ["energy_2"]),
    "energy_4": ("Chaînes de propulsion", "ship_duration", 2000, ["energy_3", "engineering_2"]),
    "computation_3": ("Calcul scientifique III", "research_duration", 1500, ["computation_2"]),
    "computation_4": ("Planification prédictive", "colony_duration", 1500,
                      ["computation_3", "xenoscience_2"]),
    "xenoscience_3": ("Protocoles d’analyse III", "research_data", 1500, ["xenoscience_2"]),
    "xenoscience_4": ("Résonance des échos", "research_data", 2500,
                      ["xenoscience_3", "computation_2"]),
}


# Relation score read from dated facts (Relations view), provisional values.
STANDING = {
    "pact": 40,
    "pact_per_day": 2,
    "pact_max_bonus": 20,
    "notice": -30,
    "proposal_received": 10,
    "hostile_received_recent": -50,
    "hostile_received_old": -20,
    "hostile_given_recent": -15,
    "recent_days": 7,
    "old_days": 30,
    "thresholds": [-50, -15, 14, 49],
}


def main():
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    for path in TARGET.glob("*.json"):
        data = json.loads(path.read_text())
        if data.get("version") == "v0.11":
            data["version"] = "v0.12"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    path = TARGET / "research.json"
    research = json.loads(path.read_text())
    for key, (name, effect, bps, requires) in NEW.items():
        domain, tier = key.rsplit("_", 1)
        base = TIER3 if tier == "3" else TIER4
        research["technologies"][key] = {
            "name": name,
            "domain": domain,
            "tier": int(tier),
            "requires": requires,
            "cost": dict(base["cost"]),
            "duration_seconds": base["duration_seconds"],
            "effect": effect,
            "reduction_bps": bps,
        }
    research["facility"]["levels"].update({"3": 5, "4": 8})
    path.write_text(json.dumps(research, ensure_ascii=False, indent=2) + "\n")
    path = TARGET / "opportunities.json"
    opportunities = json.loads(path.read_text())
    opportunities["dossiers"]["reveal_hops"] = 3
    path.write_text(json.dumps(opportunities, ensure_ascii=False, indent=2) + "\n")
    path = TARGET / "relations.json"
    relations = json.loads(path.read_text())
    relations["standing"] = STANDING
    path.write_text(json.dumps(relations, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
