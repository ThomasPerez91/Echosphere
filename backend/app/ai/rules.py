"""Pinned strategic data. No economic rule or permission is defined by the AI policy."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GOALS = ("economy", "research", "exploration", "expansion", "logistics")
# v0.7 (utility-goals-v2) adds a defensive military goal; never an offensive one.
GOALS_V2 = (*GOALS, "military")
# v0.8 (utility-goals-v3) adds diplomacy: answering and proposing pacts, never breaking one.
GOALS_V3 = (*GOALS_V2, "diplomacy")
PROFILES = {"economic_cautious", "expansionist"}
# Q11 bootstrap order; never the order of a pinned dict (JSONB reorders object keys).
BOOTSTRAP_ORDER = ("alloys", "flux", "data")
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
    producers: dict[str, str]
    industry_kind: str
    storage_kind: str
    industry_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]
    storage_threshold_bps: Annotated[int, Field(strict=True, ge=1, le=10000)]
    project_turn_limit: Positive
    trace_retention: Positive
    observation_bytes: Positive
    result_bytes: Positive

    @property
    def goals(self):
        return GOALS

    @model_validator(mode="after")
    def coherent(self):
        if set(self.profiles) != PROFILES:
            raise ValueError("Two explicit profiles required")
        for weights in self.profiles.values():
            if set(weights) != set(self.goals) or sum(weights.values()) != 100:
                raise ValueError("Goal weights must sum to 100")
        if set(self.family_pages) != set(self.goals):
            raise ValueError("Each family needs a bounded circular page")
        if sum(self.family_pages.values()) > self.candidate_limit:
            raise ValueError("Candidate pages exceed the scoring budget")
        if set(self.economy_target_per_hour) != {"alloys", "flux", "data"}:
            raise ValueError("Three real resource rates required")
        if set(self.producers) != set(BOOTSTRAP_ORDER):
            raise ValueError("Three producer references required")
        return self


class MilitaryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    ship_class: str
    target_per_colony: Annotated[int, Field(strict=True, ge=1, le=20)]
    order_quantity: Annotated[int, Field(strict=True, ge=1, le=20)]
    baseline_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]
    alert_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]


class AIRulesV2(AIRules):
    """v0.7: separate model so v0.6 dumps (and pinned policy digests) never change."""

    version: Literal["v0.7"]
    policy_version: Literal["utility-goals-v2"]
    military: MilitaryPolicy

    @property
    def goals(self):
        return GOALS_V2


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class DiplomacyPolicy(BaseModel):
    """Q18 B8. Incoming answers are priority candidates; a spontaneous proposal follows the
    profile rule: `no_recent_grievance` (no hostile act of that contact within the window) or
    `past_grievance_only` (an attack suffered from that contact, older than the window)."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    grievance_seconds: Positive
    response_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]
    proposal_utility: Annotated[int, Field(strict=True, ge=0, le=1000)]
    proposal_rules: dict[str, Literal["no_recent_grievance", "past_grievance_only"]]


class AIRulesV3(AIRulesV2):
    """v0.8: separate model so v0.6/v0.7 dumps (and pinned policy digests) never change."""

    version: Literal["v0.8"]
    policy_version: Literal["utility-goals-v3"]
    diplomacy: DiplomacyPolicy

    @property
    def goals(self):
        return GOALS_V3

    @model_validator(mode="after")
    def diplomatic(self):
        if set(self.diplomacy.proposal_rules) != PROFILES:
            raise ValueError("Each profile needs an explicit proposal rule")
        # One slot answers the oldest incoming proposal, the others page own contacts.
        if self.family_pages["diplomacy"] < 2:
            raise ValueError("Diplomacy page must hold an answer and a proposal")
        return self

