"""Strict versioned data and deterministic, bounded fixed-point progression."""

import json
import os
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.galaxy.rules import ExplorationRules, GalaxyRules
from app.simulation.production import MAX_AMOUNT, MICRO_UNITS, RESOURCES, amount

Positive = Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT)]
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=MAX_AMOUNT)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Ratio(StrictModel):
    numerator: Positive
    denominator: Positive

    def apply(self, value: int, *, ceiling: bool = False) -> int:
        product = value * self.numerator
        return amount(
            (product + self.denominator - 1) // self.denominator
            if ceiling
            else product // self.denominator
        )


class Level(StrictModel):
    cost: dict[str, Nonnegative]
    duration_seconds: Positive
    production: dict[str, Nonnegative]
    construction_bonus_bps: Nonnegative
    capacity: Positive | None

    @model_validator(mode="after")
    def resources_valid(self):
        if set(self.cost) != RESOURCES or not set(self.production) <= RESOURCES:
            raise ValueError("Invalid level resource keys")
        return self


class Scaling(StrictModel):
    cost: Ratio
    duration: Ratio
    production: Ratio
    capacity: Ratio
    bonus_increment_bps: Nonnegative

    @model_validator(mode="after")
    def nondecreasing(self):
        for ratio in [self.cost, self.duration, self.production, self.capacity]:
            if ratio.numerator < ratio.denominator:
                raise ValueError("Progression factors must be >= 1")
        # Positive growth bounds evaluation of impossible levels before a lengthy loop.
        if self.cost.numerator == self.cost.denominator:
            raise ValueError("Cost growth must be > 1")
        return self


class InfrastructureRule(StrictModel):
    max_per_colony: Positive | None
    requires: dict[str, Positive]
    explicit_levels: list[Level] = Field(min_length=1)
    scaling_after_level: Positive
    scaling: Scaling

    @model_validator(mode="after")
    def levels_valid(self):
        if len(self.explicit_levels) != self.scaling_after_level:
            raise ValueError("Scaling boundary must equal explicit level count")
        if not any(self.explicit_levels[-1].cost.values()):
            raise ValueError("Scaling anchor needs a positive cost")
        return self


class ResourceRules(StrictModel):
    version: str
    resources: list[str]


class ColonyRules(StrictModel):
    version: str
    sectors: Positive
    orbital_slots: Nonnegative
    queue_limit: Positive
    base_capacity: Positive
    initial_stocks: dict[str, Nonnegative]
    initial_infrastructures: list[str] = Field(min_length=1)
    refund_queued_bps: Annotated[int, Field(strict=True, ge=0, le=10000)]
    refund_active_bps: Annotated[int, Field(strict=True, ge=0, le=10000)]
    speeds: dict[str, Ratio]


class InfrastructureRules(StrictModel):
    version: str
    infrastructures: dict[str, InfrastructureRule] = Field(min_length=1)


class Quote(StrictModel):
    cost: dict[str, Nonnegative]  # micro-units
    base_duration_us: Positive
    production: dict[str, Nonnegative]  # micro-units/hour
    construction_bonus_bps: Nonnegative
    capacity: Positive | None  # micro-units per resource


class Technology(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    domain: Literal["engineering", "energy", "computation", "xenoscience"]
    tier: Literal[1, 2]
    requires: list[str]
    cost: dict[str, Nonnegative]
    duration_seconds: Positive
    effect: Literal["colony_alloys", "colony_flux", "research_duration", "research_data"]
    reduction_bps: Annotated[int, Field(strict=True, ge=0, lt=10000)]


class ResearchRules(StrictModel):
    version: str
    queue_limit: Literal[2]
    refund_queued_bps: Annotated[int, Field(strict=True, ge=0, le=10000)]
    refund_active_bps: Annotated[int, Field(strict=True, ge=0, le=10000)]
    technologies: dict[str, Technology] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_catalogue(self):
        catalogue = self.technologies
        seen = set()
        for key, tech in catalogue.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key):
                raise ValueError("Invalid technology identifier")
            if set(tech.cost) != RESOURCES or not any(tech.cost.values()):
                raise ValueError("Technology requires three resources and a positive cost")
            for value in tech.cost.values():
                amount(value * MICRO_UNITS)
            amount(tech.duration_seconds * MICRO_UNITS)
            if (
                len(set(tech.requires)) != len(tech.requires)
                or not set(tech.requires) <= catalogue.keys()
            ):
                raise ValueError("Unknown or duplicate prerequisite")
            if (tech.domain, tech.tier) in seen:
                raise ValueError("Duplicate domain tier")
            seen.add((tech.domain, tech.tier))
        visiting, visited = set(), set()

        def visit(key):
            if key in visiting:
                raise ValueError("Cyclic technology prerequisites")
            if key in visited:
                return
            visiting.add(key)
            for required in catalogue[key].requires:
                visit(required)
            visiting.remove(key)
            visited.add(key)

        for key in catalogue:
            visit(key)
        return self


class Ruleset(StrictModel):
    resources: ResourceRules
    colony: ColonyRules
    catalogue: InfrastructureRules
    research: ResearchRules | None = None
    galaxy: GalaxyRules | None = None
    exploration: ExplorationRules | None = None

    @property
    def version(self) -> str:
        return self.resources.version

    @model_validator(mode="after")
    def coherent(self):
        if not re.fullmatch(r"v\d+\.\d+", self.version):
            raise ValueError("Invalid ruleset version")
        if self.version != self.colony.version or self.version != self.catalogue.version:
            raise ValueError("Mixed ruleset versions")
        if set(self.resources.resources) != RESOURCES or len(self.resources.resources) != 3:
            raise ValueError("Exactly three distinct resources required")
        if self.version == "v0.1" and self.research is not None:
            raise ValueError("Research is unavailable in v0.1")
        if self.version != "v0.1" and (
            self.research is None or self.research.version != self.version
        ):
            raise ValueError("Missing or mixed Research version")
        if self.version in {"v0.1", "v0.2"} and (self.galaxy or self.exploration):
            raise ValueError("Galaxy unavailable in historical rulesets")
        if self.version == "v0.3" and (
            self.galaxy is None
            or self.exploration is None
            or self.galaxy.version != self.version
            or self.exploration.version != self.version
        ):
            raise ValueError("Missing or mixed Galaxy/Exploration version")
        c, catalogue = self.colony, self.catalogue.infrastructures
        if set(c.initial_stocks) != RESOURCES or set(c.speeds) != {
            "economy",
            "construction",
            "research",
            "fleet",
        }:
            raise ValueError("Missing stocks or instance speeds")
        if len(c.initial_infrastructures) > c.sectors:
            raise ValueError("Initial sectors exceed capacity")
        for key in c.initial_infrastructures:
            if key not in catalogue:
                raise ValueError("Unknown initial infrastructure")
        for key, rule in catalogue.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key):
                raise ValueError("Invalid infrastructure identifier")
            if not set(rule.requires) <= catalogue.keys():
                raise ValueError("Unknown prerequisite")
            if rule.max_per_colony and c.initial_infrastructures.count(key) > rule.max_per_colony:
                raise ValueError("Initial uniqueness violated")
            for level in range(1, len(rule.explicit_levels) + 1):
                self.quote(key, level)
        amount(c.base_capacity * MICRO_UNITS)
        for value in c.initial_stocks.values():
            amount(value * MICRO_UNITS)
            if value > c.base_capacity:
                raise ValueError("Initial stock exceeds base capacity")
        return self

    def quote(self, kind: str, level: int) -> Quote:
        if type(level) is not int or level < 1:
            raise ValueError("Target level must be a positive integer")
        if kind not in self.catalogue.infrastructures:
            raise ValueError("Unknown infrastructure")
        rule = self.catalogue.infrastructures[kind]
        base = rule.explicit_levels[min(level, rule.scaling_after_level) - 1]
        result = Quote(
            cost={k: amount(v * MICRO_UNITS) for k, v in base.cost.items()},
            base_duration_us=amount(base.duration_seconds * 1_000_000),
            production={k: amount(v * MICRO_UNITS) for k, v in base.production.items()},
            construction_bonus_bps=base.construction_bonus_bps,
            capacity=amount(base.capacity * MICRO_UNITS) if base.capacity else None,
        )
        for _ in range(max(0, level - rule.scaling_after_level)):
            result = Quote(
                cost={k: rule.scaling.cost.apply(v, ceiling=True) for k, v in result.cost.items()},
                base_duration_us=rule.scaling.duration.apply(result.base_duration_us, ceiling=True),
                production={
                    k: rule.scaling.production.apply(v) for k, v in result.production.items()
                },
                construction_bonus_bps=amount(
                    result.construction_bonus_bps + rule.scaling.bonus_increment_bps
                ),
                capacity=rule.scaling.capacity.apply(result.capacity) if result.capacity else None,
            )
        return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate configuration key: {key}")
        result[key] = value
    return result


def load_ruleset(version: str = "v0.1", *, root: Path | None = None) -> Ruleset:
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise ValueError("Invalid ruleset version")
    location = root or Path(
        os.environ.get("ECHOSPHERE_GAME_DATA", Path(__file__).resolve().parents[3] / "game_data")
    )
    try:
        parts = {
            key: json.loads(
                (location / "rulesets" / version / f"{name}.json").read_text(),
                object_pairs_hook=_unique_object,
            )
            for key, name in [
                ("resources", "resources"),
                ("colony", "colony"),
                ("catalogue", "infrastructures"),
            ]
        }
        if version != "v0.1":
            parts["research"] = json.loads(
                (location / "rulesets" / version / "research.json").read_text(),
                object_pairs_hook=_unique_object,
            )
        if version == "v0.3":
            for name in ("galaxy", "exploration"):
                parts[name] = json.loads(
                    (location / "rulesets" / version / f"{name}.json").read_text(),
                    object_pairs_hook=_unique_object,
                )
        rules = Ruleset.model_validate(parts)
        if rules.version != version:
            raise ValueError("Directory/version mismatch")
        return rules
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid ruleset {version}: {error}") from error
