"""Planetary defense (DEF-01, ruleset v0.13, validated 11/11/2026). Integers only.

A Défense center (key building) gives the network capacity; modules are infrastructures of the
colony catalogue (levels, costs, the construction queue), SURFACE on a real sector or ORBITAL on
a real orbital slot. A module's level is its strength: level n fights as n units of its combat
class, a shield generator of level n adds n x `shield` points absorbed before any hull. Each level
costs Flux upkeep per hour, deducted from the colony's production; when production would fall
below zero, modules are DISABLED in `disable_order` (then by sector) until it is not.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[int, Field(strict=True, gt=0, le=1_000_000)]
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=1_000_000)]
Bps = Annotated[int, Field(strict=True, gt=0, le=10000)]
ORBITAL_BASE = 1000  # orbital slot k is stored as sector_index ORBITAL_BASE + k


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DefenseModule(StrictModel):
    family: Literal["point_defense", "anti_ship", "shield", "sensor", "support"]
    placement: Literal["surface", "orbital"]
    combat_class: str | None
    shield: Nonnegative
    upkeep_flux: Positive  # units of Flux per hour and per level

    @model_validator(mode="after")
    def fights_or_shields(self):
        if (self.combat_class is None) == (self.shield == 0):
            raise ValueError("A module either fights (combat class) or shields, exactly one")
        return self


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
        return self

    def capacity(self, center_level: int) -> int:
        return self.capacity_per_level * center_level
