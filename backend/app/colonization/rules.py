"""Pinned expansion rules (v0.5+): exact integers, versioned balance, never product constants."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.simulation.production import MAX_AMOUNT, MICRO_UNITS, RESOURCES, amount

Nonnegative = Annotated[int, Field(strict=True, ge=0, le=MAX_AMOUNT)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ColonizationRules(StrictModel):
    version: str
    colonization_version: Literal["colonize-v1"]
    colonizer_class: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    colonizer_max_quantity: Literal[1]
    cost_step_bps: Annotated[int, Field(strict=True, ge=0, le=100000)]
    max_colonies: Annotated[int, Field(strict=True, ge=1, le=1000)]
    max_active_missions: Literal[1]  # also guaranteed by a partial unique index
    minimum_package: dict[str, Nonnegative]

    @model_validator(mode="after")
    def coherent(self):
        if set(self.minimum_package) != RESOURCES:
            raise ValueError("Minimum package requires the three resources")
        for value in self.minimum_package.values():
            amount(value * MICRO_UNITS)
        return self

    def package_minimum(self):
        return {r: amount(v * MICRO_UNITS) for r, v in self.minimum_package.items()}

    def multiplier_bps(self, rank: int) -> int:
        """Progressive colonizer price 1 + step × (N − 1); N counts colonies + colonizers."""
        if type(rank) is not int or rank < 1:
            raise ValueError("Invalid colonizer rank")
        return amount(10000 + self.cost_step_bps * (rank - 1))
