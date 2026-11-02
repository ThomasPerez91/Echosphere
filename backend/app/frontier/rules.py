"""Pinned frontier data (13B, ruleset v0.9+). Only validated vocabulary; no balance invented.

Q57: the four protocol names are validated; which of them a ruleset enables is explicit, so a
protocol whose runtime is not implemented (AMBUSH, INTERCEPTION, retreat) cannot be selected.
Q58: detection levels, technology, costs and stealth stay open; nothing numeric lives here yet.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROTOCOLS = ("SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT")
Protocol = Literal["SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"]


class FrontierRules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: str
    frontier_version: Literal["frontier-v1"]
    protocols: list[Protocol] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def coherent(self):
        if len(set(self.protocols)) != len(self.protocols):
            raise ValueError("Repeated protocol")
        if list(self.protocols) != [p for p in PROTOCOLS if p in self.protocols]:
            raise ValueError("Protocols must follow the canonical order")
        return self
