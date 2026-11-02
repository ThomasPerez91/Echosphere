"""Pinned frontier data (13B, ruleset v0.9+). Only validated vocabulary; no balance invented.

Q57: the four protocol names are validated; which of them a ruleset enables is explicit, so a
protocol whose runtime is not implemented cannot be selected.
D4 (02/11/2026): AMBUSH engages a known Empire whose resolved hostile act against the watcher is
younger than `ambush_hostility_seconds` at the logical encounter instant (72 h in v0.9).
Q58: detection levels, technology, costs and stealth stay open (level 0 for all, D1).
"""

from typing import Literal

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROTOCOLS = ("SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT")
Protocol = Literal["SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"]


class FrontierRules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: str
    frontier_version: Literal["frontier-v1"]
    protocols: list[Protocol] = Field(min_length=1, max_length=4)
    ambush_hostility_seconds: int = Field(strict=True, gt=0, le=30 * 24 * 3600)

    @property
    def ambush_window(self) -> timedelta:
        return timedelta(seconds=self.ambush_hostility_seconds)

    @model_validator(mode="after")
    def coherent(self):
        if len(set(self.protocols)) != len(self.protocols):
            raise ValueError("Repeated protocol")
        if list(self.protocols) != [p for p in PROTOCOLS if p in self.protocols]:
            raise ValueError("Protocols must follow the canonical order")
        return self
