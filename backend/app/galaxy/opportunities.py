"""EXP-01 opportunities-v1: deposits and curiosities layered on an already generated galaxy.

Pure canonical values only (no database, clock, UUID or Python hash). The galaxy-v1 world, its
digest and its starting sites are inputs, never modified: an opportunity universe has exactly the
same systems, routes and planets as a galaxy-v1 universe of the same seed. Values are whole
resource units and seconds from the pinned ruleset (provisional balance); services convert to
micro-units. Design: docs/01-game-design/operational-expansion.md.
"""

import hashlib
from collections import deque
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.galaxy.generator import StableRandom, adjacency, canonical
from app.simulation.production import RESOURCES

Positive = Annotated[int, Field(strict=True, gt=0, le=10**9)]
Bps = Annotated[int, Field(strict=True, ge=0, le=10000)]
Range = Annotated[list[Positive], Field(min_length=2, max_length=2)]
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]

FAMILIES = ("deposit", "curiosity")
MAX_SITES = 3


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _range(value: Range):
    if value[0] > value[1]:
        raise ValueError("Range minimum above maximum")


class DepositKind(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    resource: Literal["alloys", "flux", "data"]
    weight: Positive
    reserve: Range
    throughput_per_hour: Range

    @model_validator(mode="after")
    def coherent(self):
        _range(self.reserve)
        _range(self.throughput_per_hour)
        return self


class CuriosityKind(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    weight: Positive
    study_seconds: Range
    data: Range

    @model_validator(mode="after")
    def coherent(self):
        _range(self.study_seconds)
        _range(self.data)
        return self


class Remarkable(StrictModel):
    chance_bps: Bps
    multiplier_bps: Annotated[int, Field(strict=True, ge=10000, le=100000)]
    max_per_100_systems: Annotated[int, Field(strict=True, ge=0, le=20)]
    min_start_distance: Annotated[int, Field(strict=True, ge=1, le=10)]


class Dossiers(StrictModel):
    per_100_systems: Annotated[int, Field(strict=True, ge=0, le=20)]
    clues: Annotated[int, Field(strict=True, ge=2, le=6)]
    reward_data: Positive


class Operations(StrictModel):
    """EXP-02 missions: prospection length, the civilian extractor class and its hourly rate."""

    prospect_seconds: Positive
    extractor_class: Key
    extraction_per_hour: Positive
    extract_max_hours: Positive


class OpportunityRules(StrictModel):
    version: str
    opportunity_generator_version: Literal["opportunities-v1"]
    sites_per_system: dict[str, Bps]
    family_weights: dict[str, Bps]
    deposits: dict[Key, DepositKind] = Field(min_length=1, max_length=12)
    curiosities: dict[Key, CuriosityKind] = Field(min_length=1, max_length=12)
    remarkable: Remarkable
    dossiers: Dossiers
    starting_zone_radius: Annotated[int, Field(strict=True, ge=1, le=3)]
    starting_zone_deposits: Annotated[int, Field(strict=True, ge=0, le=2)]
    operations: Operations

    @model_validator(mode="after")
    def coherent(self):
        sites = self.sites_per_system
        keys_ok = all(k.isdecimal() and int(k) <= MAX_SITES for k in sites)
        if not keys_ok or sum(sites.values()) != 100:
            raise ValueError("Sites per system: integer keys 0-3 totalling 100")
        if set(self.family_weights) != set(FAMILIES) or sum(self.family_weights.values()) != 100:
            raise ValueError("Family weights: deposit and curiosity totalling 100")
        if {d.resource for d in self.deposits.values()} - RESOURCES:
            raise ValueError("Deposits use the three existing resources only")
        if set(self.deposits) & set(self.curiosities):
            raise ValueError("Opportunity kinds must be unique across families")
        return self


def _pick(rng, weights):
    """Weighted draw over named keys in sorted order (StableRandom.weighted needs integers)."""
    value = rng.below(sum(weights.values()))
    for key in sorted(weights):
        value -= weights[key]
        if value < 0:
            return key
    raise AssertionError("Unreachable weighted draw")


def _draw(rng, bounds):
    low, high = bounds
    return low + rng.below(high - low + 1)


def _scaled(value, bps):
    return value * bps // 10000


def nearest_start(count, routes, sites):
    """Hop distance from each system to the nearest starting site (unreachable: None)."""
    graph = adjacency(count, routes)
    distance = dict.fromkeys(sites, 0)
    queue = deque(sorted(sites))
    while queue:
        node = queue.popleft()
        for other in sorted(graph[node]):
            if other not in distance:
                distance[other] = distance[node] + 1
                queue.append(other)
    return [distance.get(node) for node in range(count)]


def _opportunity(rng, rules, family, kind, remarkable):
    bps = rules.remarkable.multiplier_bps if remarkable else 10000
    item = {"family": family, "kind": kind, "tier": "remarkable" if remarkable else "common"}
    if family == "deposit":
        spec = rules.deposits[kind]
        item.update(
            resource=spec.resource,
            reserve=_scaled(_draw(rng, spec.reserve), bps),
            throughput_per_hour=_draw(rng, spec.throughput_per_hour),
        )
    else:
        spec = rules.curiosities[kind]
        item.update(
            study_seconds=_draw(rng, spec.study_seconds),
            data=_scaled(_draw(rng, spec.data), bps),
        )
    return item


def _common_deposits(placed, zone):
    return sum(o["family"] == "deposit" and o["tier"] == "common" for n in zone for o in placed[n])


def generate_opportunities(seed, world, rules):
    """Deterministic opportunities for one generated world (`generator.generate()["world"]`)."""
    systems, routes, sites = world["systems"], world["routes"], world["starting_sites"]
    count = len(systems)
    digest = hashlib.sha256(canonical(world).encode()).hexdigest()
    rng = StableRandom(
        {"generator": rules.opportunity_generator_version, "seed": seed, "world": digest}
    )
    start_distance = nearest_start(count, [tuple(r) for r in routes], sites)
    cap = count * rules.remarkable.max_per_100_systems // 100
    placed, remarkable = [[] for _ in range(count)], 0
    for node in range(count):
        for _ in range(int(_pick(rng, rules.sites_per_system))):
            family = _pick(rng, rules.family_weights)
            kinds = rules.deposits if family == "deposit" else rules.curiosities
            kind = _pick(rng, {key: spec.weight for key, spec in kinds.items()})
            lucky = rng.below(10000) < rules.remarkable.chance_bps
            eligible = (
                start_distance[node] is not None
                and start_distance[node] >= rules.remarkable.min_start_distance
                and remarkable < cap
            )
            remarkable += bool(lucky and eligible)
            placed[node].append(_opportunity(rng, rules, family, kind, lucky and eligible))
    # Fairness: every starting zone holds an ordinary deposit, whatever the draws gave.
    graph = adjacency(count, [tuple(r) for r in routes])
    for site in sorted(sites):
        zone, frontier = {site}, {site}
        for _ in range(rules.starting_zone_radius):
            frontier = {n for f in frontier for n in graph[f]} - zone
            zone |= frontier
        while _common_deposits(placed, zone) < rules.starting_zone_deposits:
            room = [n for n in sorted(zone) if n != site and len(placed[n]) < MAX_SITES]
            if not room:
                break
            node = room[rng.below(len(room))]
            kind = _pick(rng, {key: spec.weight for key, spec in rules.deposits.items()})
            placed[node].append(_opportunity(rng, rules, "deposit", kind, False))
    opportunities = [
        {"system": node, "index": index, **item}
        for node in range(count)
        for index, item in enumerate(placed[node])
    ]
    # Dossiers: clues on curiosities of distinct systems, never invented if too few exist.
    wanted = count * rules.dossiers.per_100_systems // 100
    candidates = rng.shuffle(
        [i for i, o in enumerate(opportunities) if o["family"] == "curiosity"]
    )
    dossiers, used = [], set()
    for number in range(wanted):
        clues = []
        for i in candidates:
            system = opportunities[i]["system"]
            if i in used or any(system == opportunities[j]["system"] for j in clues):
                continue
            clues.append(i)
            if len(clues) == rules.dossiers.clues:
                break
        if len(clues) < rules.dossiers.clues:
            break
        used.update(clues)
        for position, i in enumerate(sorted(clues)):
            opportunities[i]["dossier"], opportunities[i]["clue"] = number, position
        dossiers.append(
            {
                "index": number,
                "clues": [
                    [opportunities[i]["system"], opportunities[i]["index"]] for i in sorted(clues)
                ],
                "reward_data": rules.dossiers.reward_data,
            }
        )
    return {
        "version": rules.opportunity_generator_version,
        "world_digest": digest,
        "opportunities": opportunities,
        "dossiers": dossiers,
    }


def strategic_marks(system_ids, routes):
    """Position interest from a route graph (the caller passes only routes the Empire knows):
    `crossroads` for four routes or more. Never a stored bonus, recomputed from knowledge."""
    degree = dict.fromkeys(system_ids, 0)
    for a, b in routes:
        if a in degree:
            degree[a] += 1
        if b in degree:
            degree[b] += 1
    return {s: ["crossroads"] for s, d in degree.items() if d >= 4}
