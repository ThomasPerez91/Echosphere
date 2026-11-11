"""Planetary defense (DEF-01, ruleset v0.13, validated by the user on 11/11/2026). Integers only.

A Défense center (key building) gives the network capacity: `capacity_per_level` modules per
level. Modules are infrastructures of the colony catalogue built through the colony queue, level
1 only: a SURFACE module on a real sector, an ORBITAL module on a real orbital slot (sector index
ORBITAL_BASE + k). Each fights as one unit of its combat class beside the garrison. An
operational module costs `upkeep_flux` Flux per hour, deducted from the colony's production;
when the net Flux production would fall below zero, modules are DISABLED in `disable_order`
(then by sector) until it no longer does. A module lost in battle is DAMAGED (no fight, no
upkeep) until repaired for `repair_cost_bps` of its cost and `repair_duration_bps` of its time.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[int, Field(strict=True, gt=0, le=1_000_000)]
Bps = Annotated[int, Field(strict=True, gt=0, le=10000)]
ORBITAL_BASE = 1000  # orbital slot k (1-based) is stored as sector_index ORBITAL_BASE + k
CONDITIONS = ("operational", "disabled", "damaged")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DefenseModule(StrictModel):
    family: Literal["point_defense", "anti_ship"]
    placement: Literal["surface", "orbital"]
    combat_class: str
    upkeep_flux: Positive  # units of Flux per hour


class DefenseRules(StrictModel):
    version: str
    defense_version: Literal["defense-v1"]
    center: str
    capacity_per_level: Positive
    modules: dict[str, DefenseModule] = Field(min_length=1)
    disable_order: list[str]
    repair_cost_bps: Bps
    repair_duration_bps: Bps

    @model_validator(mode="after")
    def coherent(self):
        if sorted(self.disable_order) != sorted(self.modules):
            raise ValueError("Disable order lists every module exactly once")
        if self.center in self.modules:
            raise ValueError("The defense center is not a module")
        if len({m.combat_class for m in self.modules.values()}) != len(self.modules):
            raise ValueError("One combat class per module")
        return self

    def capacity(self, center_level: int) -> int:
        return self.capacity_per_level * center_level
