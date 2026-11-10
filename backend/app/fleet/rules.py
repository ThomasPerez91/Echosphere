"""Pinned Fleet catalogue (v0.4+): exact integers, no implicit bonus or speed on production."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.rules_dump import omit_unset_extensions
from app.simulation.production import MAX_AMOUNT, MICRO_UNITS, RESOURCES, amount

Positive = Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT)]
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=MAX_AMOUNT)]
Bps = Annotated[int, Field(strict=True, ge=0, le=10000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ShipClass(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    cost: dict[str, Nonnegative]
    build_seconds: Positive
    hop_seconds: Positive
    flux_per_hop: Nonnegative
    cargo: Nonnegative
    survey: bool
    # v0.11 (COL-11): infrastructure levels of the building colony that unlock this class
    # (the Forge orbitale); empty before v0.11.
    requires: dict[str, Positive] = Field(default_factory=dict)
    serialize_extensions = omit_unset_extensions("requires")


class FleetRules(StrictModel):
    version: str
    engagement_version: Literal["fleet-v1"]
    survey_version: Literal["fleet-survey-v1"]
    queue_limit: Literal[3]
    max_quantity: Annotated[int, Field(strict=True, ge=1, le=1000)]
    refund_queued_bps: Bps
    refund_active_bps: Bps
    survey_seconds: Positive
    survey_cost: dict[str, Nonnegative]
    classes: dict[str, ShipClass] = Field(min_length=1)

    @model_validator(mode="after")
    def coherent(self):
        if set(self.survey_cost) != RESOURCES:
            raise ValueError("Survey cost requires the three resources")
        if not any(c.survey for c in self.classes.values()):
            raise ValueError("A survey-capable class is required")
        for key, ship in self.classes.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", key):
                raise ValueError("Invalid ship class identifier")
            if set(ship.cost) != RESOURCES or not any(ship.cost.values()):
                raise ValueError("Ship class requires three resources and a positive cost")
            # Bound every product the services compute so overflow is a load-time error.
            self.order_quote(key, self.max_quantity)
            amount(ship.hop_seconds * MICRO_UNITS)
            amount(ship.cargo * MICRO_UNITS * self.max_quantity)
        amount(self.survey_seconds * MICRO_UNITS)
        return self

    def order_quote(self, ship_class: str, quantity: int):
        """Total cost and duration of one atomic batch; Fleet speed never applies here."""
        if ship_class not in self.classes:
            raise ValueError("Unknown ship class")
        if type(quantity) is not int or not 1 <= quantity <= self.max_quantity:
            raise ValueError("Invalid quantity")
        ship = self.classes[ship_class]
        cost = {r: amount(v * MICRO_UNITS * quantity) for r, v in ship.cost.items()}
        return cost, amount(ship.build_seconds * MICRO_UNITS * quantity)

    def cargo_capacity(self, stacks: dict[str, int]) -> int:
        return amount(sum(self.classes[c].cargo * MICRO_UNITS * n for c, n in stacks.items()))

    def mission_quote(self, stacks: dict[str, int], hops: int, speed, survey: bool):
        """Fuel and durations from the slowest class; positions never matter, only hops."""
        if type(hops) is not int or hops < 1 or not stacks:
            raise ValueError("Mission requires units and a positive route length")
        slowest = max(self.classes[c].hop_seconds for c in stacks)
        base = amount(hops * slowest * MICRO_UNITS)
        numerator, denominator = base * speed.denominator, speed.numerator
        travel = amount(max(1, (numerator + denominator - 1) // denominator))
        flux = sum(self.classes[c].flux_per_hop * n for c, n in stacks.items())
        cost = dict.fromkeys(sorted(RESOURCES), 0)
        cost["flux"] = amount(hops * flux * MICRO_UNITS)
        survey_us = 0
        if survey:
            survey_us = amount(self.survey_seconds * MICRO_UNITS)
            for r, v in self.survey_cost.items():
                cost[r] = amount(cost[r] + v * MICRO_UNITS)
        return cost, travel, survey_us
