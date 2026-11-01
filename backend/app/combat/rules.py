"""Pinned Combat data (v0.7+). Integers only; stats live here, never in the Fleet class format."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[int, Field(strict=True, gt=0, le=1_000_000)]
Bps = Annotated[int, Field(strict=True, gt=0, le=100_000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ShipStats(StrictModel):
    hull: Positive
    attack: Positive


class CombatRules(StrictModel):
    version: str
    combat_version: Literal["combat-v1"]
    min_warning_seconds: Positive
    max_rounds: Positive
    # Canonical class order: the only tie-break for targeting and every serialized listing.
    classes: list[str] = Field(min_length=1, max_length=16)
    stats: dict[str, ShipStats]
    matchups_bps: dict[str, dict[str, Bps]]

    @model_validator(mode="after")
    def coherent(self):
        names = set(self.classes)
        if len(names) != len(self.classes) or not all(
            re.fullmatch(r"[a-z][a-z0-9_]{0,31}", c) for c in self.classes
        ):
            raise ValueError("Military classes must be distinct identifiers")
        if set(self.stats) != names or set(self.matchups_bps) != names:
            raise ValueError("Stats and matchups required for every military class")
        if any(set(row) != names for row in self.matchups_bps.values()):
            raise ValueError("Complete matchup matrix required")
        return self
