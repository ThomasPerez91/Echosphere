"""Pinned strategic data. No economic rule or permission is defined by the AI policy."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GOALS = ("economy", "research", "exploration", "expansion", "logistics")
PROFILES = {"economic_cautious", "expansionist"}
Positive = Annotated[int, Field(strict=True, gt=0, le=1_000_000)]
Weight = Annotated[int, Field(strict=True, ge=0, le=100)]


class AIRules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: Literal["v0.6"]
    policy_version: Literal["utility-goals-v1"]
    profiles: dict[str, dict[str, Weight]]
    cadence_seconds: Literal[600]
    candidate_limit: Literal[128]
    fleet_page_size: Literal[64]
    family_pages: dict[str, Positive]
    economy_target_per_hour: dict[str, Positive]
    research_queued_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]
    expansion_before_survey_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]
    trace_retention: Positive
    observation_bytes: Positive
    result_bytes: Positive

    @model_validator(mode="after")
    def coherent(self):
        if set(self.profiles) != PROFILES:
            raise ValueError("Two explicit profiles required")
        for weights in self.profiles.values():
            if set(weights) != set(GOALS) or sum(weights.values()) != 100:
                raise ValueError("Goal weights must sum to 100")
        if set(self.family_pages) != set(GOALS):
            raise ValueError("Each family needs a bounded circular page")
        if sum(self.family_pages.values()) > self.candidate_limit:
            raise ValueError("Candidate pages exceed the scoring budget")
        if set(self.economy_target_per_hour) != {"alloys", "flux", "data"}:
            raise ValueError("Three real resource rates required")
        return self


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
