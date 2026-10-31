"""Pinned Galaxy/Exploration data; no economic floats or implicit version adoption."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.simulation.production import MAX_AMOUNT, MICRO_UNITS, RESOURCES, amount

Positive = Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT)]
Nonnegative = Annotated[int, Field(strict=True, ge=0, le=MAX_AMOUNT)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class GalaxyRules(StrictModel):
    version: str
    galaxy_generator_version: Literal["galaxy-v1"]
    system_count: Positive
    min_systems: Positive
    max_systems: Positive
    starting_site_count: Positive
    max_starting_sites: Positive
    max_attempts: Positive
    min_degree: Positive
    max_degree: Positive
    min_mean_degree_bps: Positive
    max_mean_degree_bps: Positive
    min_junction_bps: Positive
    max_mean_path_bps: Positive
    diameter_divisor: Positive
    coordinate_limit: Positive
    min_separation: Positive
    max_route_length: Positive
    detected_cell_size: Positive
    min_start_distance: Positive
    min_start_zone_size: Positive
    fairness_ratio_bps: Positive
    planet_counts: dict[str, Positive]
    sector_capacities: dict[str, Positive]
    orbital_capacities: dict[str, Positive]
    useful_sectors: Positive
    useful_orbitals: Nonnegative
    starting_sectors: Positive
    starting_orbitals: Nonnegative

    @model_validator(mode="after")
    def coherent(self):
        if not 30 <= self.min_systems <= self.system_count <= self.max_systems <= 50:
            raise ValueError("Invalid galaxy-v1 system bounds")
        if not 1 <= self.starting_site_count <= self.max_starting_sites <= 4:
            raise ValueError("Invalid candidate site count")
        if self.max_attempts > 64 or not 2 <= self.min_degree <= self.max_degree <= 4:
            raise ValueError("Invalid generation bounds")
        if not self.min_mean_degree_bps <= self.max_mean_degree_bps:
            raise ValueError("Invalid degree interval")
        for weights in [self.planet_counts, self.sector_capacities, self.orbital_capacities]:
            if sum(weights.values()) != 100 or any(not k.isdecimal() for k in weights):
                raise ValueError("Weights require integer keys and total 100")
        if any(not 2 <= int(k) <= 5 for k in self.planet_counts):
            raise ValueError("Invalid planet count")
        if self.min_separation > self.max_route_length or self.fairness_ratio_bps < 10000:
            raise ValueError("Invalid geometry or fairness interval")
        return self


class ExplorationRules(StrictModel):
    version: str
    engagement_version: Literal["abstract-expedition-v1"]
    active_limit: Literal[1]
    cost: dict[str, Nonnegative]
    flux_per_hop: Nonnegative
    leg_seconds: Positive
    survey_seconds: Positive

    @model_validator(mode="after")
    def coherent(self):
        if set(self.cost) != RESOURCES or not any(self.cost.values()):
            raise ValueError("Exploration requires explicit resource costs")
        for value in self.cost.values():
            amount(value * MICRO_UNITS)
        return self

    def quote(self, hops: int):
        if type(hops) is not int or hops < 1:
            raise ValueError("Exploration requires a positive route length")
        cost = {r: amount(v * MICRO_UNITS) for r, v in self.cost.items()}
        cost["flux"] = amount(cost["flux"] + self.flux_per_hop * hops * MICRO_UNITS)
        duration = amount((2 * hops * self.leg_seconds + self.survey_seconds) * MICRO_UNITS)
        return cost, duration
