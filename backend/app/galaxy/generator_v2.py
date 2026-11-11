"""galaxy-v2 (Q61, 09/11/2026): 100 to 2 000 systems, regions joined by few routes, dead ends and
chokepoints, never an isolated Empire.

Pure canonical values only, same contract as galaxy-v1 (`systems`, `routes`, `starting_sites`) so
the persistence and every later domain stay unchanged. Construction:

1. a seeded blob of lattice cells (spacing and jitter from the ruleset: no two systems too close);
2. regions of about `region_size` systems (farthest-point seeds, contiguous growth);
3. inside a region: a random spanning tree, then extra routes, a share of leaves kept as dead ends;
4. between regions: a spanning tree of single routes (chokepoints), plus a few extra links so
   that not every frontier is a bottleneck;
5. starting sites spread over distinct regions, each with two exits within its zone and an
   identical core zone budget (Équitable placement, Q61).

Acceptance is independent from construction (`validate_v2`): connected graph, bounded degrees, no
crossing routes inside a lattice square, dead ends and bridges present, starts far enough apart
and never isolated, identical core zones.
"""

import hashlib
import math
from collections import deque
from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.galaxy.generator import GenerationError, StableRandom, adjacency, canonical, two_exits
from app.rules_dump import omit_unset_extensions

Positive = Annotated[int, Field(strict=True, gt=0, le=10**6)]
Bps = Annotated[int, Field(strict=True, ge=0, le=10000)]
SIZES = ("100", "300", "500", "1000", "2000")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class GalaxyRulesV2(StrictModel):
    version: str
    galaxy_generator_version: Literal["galaxy-v2"]
    sizes: dict[str, Positive]
    default_size: Positive
    max_humans: Annotated[int, Field(strict=True, ge=1, le=10)]
    max_ai: Annotated[int, Field(strict=True, ge=0, le=30)]
    region_size: Annotated[int, Field(strict=True, ge=10, le=60)]
    spacing: Positive
    jitter: Annotated[int, Field(strict=True, ge=0, le=40)]
    min_separation: Positive
    max_route_length: Positive
    max_degree: Annotated[int, Field(strict=True, ge=3, le=6)]
    extra_route_bps: Bps
    dead_end_bps: Bps
    region_link_bps: Bps
    max_attempts: Annotated[int, Field(strict=True, ge=1, le=32)]
    detected_cell_size: Positive
    min_start_distance: Annotated[int, Field(strict=True, ge=5, le=20)]
    min_start_zone_size: Annotated[int, Field(strict=True, ge=4, le=12)]
    planet_counts: dict[str, Positive]
    sector_capacities: dict[str, Positive]
    # v0.12 (11/11/2026): system names made of syllables, from their own stream so every other
    # generated value is unchanged; omitted (catalogue numbers) in earlier rulesets.
    naming: Literal["syllables"] | None = None
    serialize_extensions = omit_unset_extensions("naming")
    orbital_capacities: dict[str, Positive]
    useful_sectors: Positive
    useful_orbitals: Annotated[int, Field(strict=True, ge=0, le=10)]
    starting_sectors: Positive
    starting_orbitals: Annotated[int, Field(strict=True, ge=0, le=10)]

    @model_validator(mode="after")
    def coherent(self):
        if set(self.sizes) != set(SIZES) or str(self.default_size) not in self.sizes:
            raise ValueError("galaxy-v2 offers exactly the sizes 100, 300, 500, 1000 and 2000")
        if any(cap > self.max_humans + self.max_ai or cap < 2 for cap in self.sizes.values()):
            raise ValueError("Empire caps must stay within humans + AI")
        if any(cap * self.region_size > int(size) for size, cap in self.sizes.items()):
            raise ValueError("Every Empire needs its own region")
        # Lattice neighbours (diagonals included) must be joinable, jittered points never too close.
        if self.min_separation > self.spacing - 2 * self.jitter:
            raise ValueError("Jitter breaks the minimum separation")
        if self.max_route_length < math.isqrt(2 * self.spacing**2) + 1 + 3 * self.jitter:
            raise ValueError("Routes cannot reach diagonal neighbours")
        for weights in [self.planet_counts, self.sector_capacities, self.orbital_capacities]:
            if sum(weights.values()) != 100 or any(not k.isdecimal() for k in weights):
                raise ValueError("Weights require integer keys and total 100")
        if any(not 2 <= int(k) <= 5 for k in self.planet_counts):
            raise ValueError("Invalid planet count")
        return self

    def empire_cap(self, size: int) -> int:
        return self.sizes[str(size)]


NEIGHBOURS = [(1, 0), (0, 1), (1, 1), (1, -1)]


def _blob(random, count):
    """`count` lattice cells around the centre, slightly irregular, 8-connected by construction."""
    side = math.isqrt(count * 2) + 4
    centre = side / 2
    order = sorted(
        ((x, y) for x in range(side) for y in range(side)),
        key=lambda c: ((c[0] + 0.5 - centre) ** 2 + (c[1] + 0.5 - centre) ** 2) * 64
        + random.below(64 * max(1, side // 3)),
    )
    chosen = [order[0]]
    taken = {order[0]}
    frontier = {order[0]}
    rank = {cell: i for i, cell in enumerate(order)}
    # Grow by rank but only through 8-neighbours: the blob stays one piece.
    candidates = set()
    while len(chosen) < count:
        for x, y in frontier:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cell = (x + dx, y + dy)
                    if cell in rank and cell not in taken:
                        candidates.add(cell)
        best = min(candidates, key=rank.__getitem__)
        candidates.discard(best)
        taken.add(best)
        chosen.append(best)
        frontier = {best}
    return sorted(chosen)


def _bridges(count, graph):
    """Tarjan, iterative: routes whose removal disconnects the graph."""
    order, low, result, clock = [-1] * count, [0] * count, set(), 0
    for root in range(count):
        if order[root] >= 0:
            continue
        stack = [(root, -1, iter(sorted(graph[root])))]
        order[root] = low[root] = clock
        clock += 1
        while stack:
            node, parent, children = stack[-1]
            advanced = False
            for other in children:
                if other == parent:
                    continue
                if order[other] < 0:
                    order[other] = low[other] = clock
                    clock += 1
                    stack.append((other, node, iter(sorted(graph[other]))))
                    advanced = True
                    break
                low[node] = min(low[node], order[other])
            if not advanced:
                stack.pop()
                if stack:
                    up = stack[-1][0]
                    low[up] = min(low[up], low[node])
                    if low[node] > order[up]:
                        result.add(tuple(sorted((up, node))))
    return result


def _distances(graph, source):
    result = {source: 0}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for other in sorted(graph[node]):
            if other not in result:
                result[other] = result[node] + 1
                queue.append(other)
    return result


def _zone(graph, site, radius=2):
    found = _distances_limited(graph, site, radius)
    return sorted(found, key=lambda n: (found[n], n))


def _distances_limited(graph, source, limit):
    result = {source: 0}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        if result[node] == limit:
            continue
        for other in sorted(graph[node]):
            if other not in result:
                result[other] = result[node] + 1
                queue.append(other)
    return result


def _worlds(random, rules):
    result = [
        {
            "sectors": random.weighted(rules.sector_capacities),
            "orbitals": random.weighted(rules.orbital_capacities),
        }
        for _ in range(random.weighted(rules.planet_counts))
    ]
    if not any(
        p["sectors"] >= rules.useful_sectors and p["orbitals"] >= rules.useful_orbitals
        for p in result
    ):
        result[0] = {"sectors": rules.useful_sectors, "orbitals": rules.useful_orbitals}
    return result


def _candidate(random, count, empires, rules):
    cells = _blob(random, count)
    index = {cell: i for i, cell in enumerate(cells)}
    points = [
        (
            rules.spacing * (x + 1) + random.below(2 * rules.jitter + 1) - rules.jitter,
            rules.spacing * (y + 1) + random.below(2 * rules.jitter + 1) - rules.jitter,
        )
        for x, y in cells
    ]
    pairs = []
    for i, (x, y) in enumerate(cells):
        for dx, dy in NEIGHBOURS:
            j = index.get((x + dx, y + dy))
            if j is not None:
                pairs.append((min(i, j), max(i, j)))
    # Regions: farthest-point seeds over lattice distance, then contiguous multi-source growth.
    regions = max(empires, -(-count // rules.region_size))
    lattice = adjacency(count, pairs)
    seeds = [random.below(count)]
    nearest = _distances(lattice, seeds[0])
    while len(seeds) < regions:
        far = max(range(count), key=lambda n: (nearest.get(n, 0), -n))
        seeds.append(far)
        for node, d in _distances(lattice, far).items():
            nearest[node] = min(nearest.get(node, d), d)
    owner = dict.fromkeys(range(count), -1)
    queue = deque()
    for r, seed in enumerate(seeds):
        owner[seed] = r
        queue.append(seed)
    while queue:
        node = queue.popleft()
        for other in sorted(lattice[node]):
            if owner[other] < 0:
                owner[other] = owner[node]
                queue.append(other)
    degree = [0] * count
    routes = set()

    def blocked(a, b):
        (ax, ay), (bx, by) = cells[a], cells[b]
        if abs(ax - bx) == 1 and abs(ay - by) == 1:
            c, d = index.get((ax, by)), index.get((bx, ay))
            if c is not None and d is not None and tuple(sorted((c, d))) in routes:
                return True
        return degree[a] >= rules.max_degree or degree[b] >= rules.max_degree

    def add(a, b):
        routes.add((a, b))
        degree[a] += 1
        degree[b] += 1

    parent = list(range(count))

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def orthogonal(pair):
        (ax, ay), (bx, by) = cells[pair[0]], cells[pair[1]]
        return ax == bx or ay == by

    inner = [p for p in pairs if owner[p[0]] == owner[p[1]]]
    shuffled = random.shuffle(inner)
    shuffled.sort(key=lambda p: not orthogonal(p))
    for a, b in shuffled:
        if find(a) != find(b) and not blocked(a, b):
            parent[find(a)] = find(b)
            add(a, b)
    # Dead ends: a share of the tree leaves never receives a second route.
    leaves = [n for n in range(count) if degree[n] == 1]
    kept = {n for n in leaves if random.below(10000) < rules.dead_end_bps}
    for a, b in random.shuffle(inner):
        if (a, b) in routes or a in kept or b in kept:
            continue
        if random.below(10000) < rules.extra_route_bps and not blocked(a, b):
            add(a, b)
    # Between regions: one route per link of a region spanning tree (chokepoints), extra links.
    between = {}
    for a, b in random.shuffle([p for p in pairs if owner[p[0]] != owner[p[1]]]):
        key = tuple(sorted((owner[a], owner[b])))
        between.setdefault(key, []).append((a, b))
    region_parent = list(range(regions))

    def region_find(n):
        while region_parent[n] != n:
            region_parent[n] = region_parent[region_parent[n]]
            n = region_parent[n]
        return n

    def link(options):
        options = sorted(options, key=lambda p: (a_kept(p), not orthogonal(p)))
        for a, b in options:
            if not blocked(a, b):
                add(a, b)
                return True
        return False

    def a_kept(pair):
        return pair[0] in kept or pair[1] in kept

    keys = random.shuffle(sorted(between))
    for key in keys:
        if region_find(key[0]) != region_find(key[1]) and link(between[key]):
            region_parent[region_find(key[0])] = region_find(key[1])
    if len({region_find(r) for r in range(regions)}) != 1:
        return None
    tree_links = {
        tuple(sorted((owner[a], owner[b]))) for a, b in routes if owner[a] != owner[b]
    }
    for key in keys:
        if key not in tree_links and random.below(10000) < rules.region_link_bps:
            link(between[key])
    graph = adjacency(count, sorted(routes))
    # Starting sites: spread over regions, then the most central eligible system of each.
    region_nodes = {r: [n for n in range(count) if owner[n] == r] for r in range(regions)}
    chosen_regions = [random.below(regions)]
    while len(chosen_regions) < empires:
        best = max(
            (r for r in range(regions) if r not in chosen_regions),
            key=lambda r: (
                min(
                    abs(cells[seeds[r]][0] - cells[seeds[c]][0])
                    + abs(cells[seeds[r]][1] - cells[seeds[c]][1])
                    for c in chosen_regions
                ),
                -r,
            ),
        )
        chosen_regions.append(best)
    sites = []
    for r in chosen_regions:
        home = cells[seeds[r]]
        for node in sorted(
            region_nodes[r],
            key=lambda n: (abs(cells[n][0] - home[0]) + abs(cells[n][1] - home[1]), n),
        ):
            zone = set(_zone(graph, node))
            if (
                degree[node] >= 3
                and len(zone) >= rules.min_start_zone_size
                and two_exits(graph, node, zone)
                and all(not zone & set(_zone(graph, s)) for s in sites)
            ):
                sites.append(node)
                break
        else:
            return None
    # Équitable: identical core zone budget (start home planet fixed), random worlds elsewhere.
    budget = [_worlds(random, rules) for _ in range(rules.min_start_zone_size)]
    budget[0][0] = {"sectors": rules.starting_sectors, "orbitals": rules.starting_orbitals}
    planets = [None] * count
    for site in sites:
        for rank, node in enumerate(_zone(graph, site)[: rules.min_start_zone_size]):
            planets[node] = deepcopy(budget[rank])
    names = set()
    systems = []
    words = StableRandom(["names", random.key.decode("utf-8")]) if rules.naming else None
    for node, (x, y) in enumerate(points):
        while True:
            name = syllable_name(words) if words else f"System {random.below(1000000):06d}"
            if name not in names:
                names.add(name)
                break
        worlds = planets[node] if planets[node] is not None else _worlds(random, rules)
        systems.append(
            {
                "name": name,
                "x": x,
                "y": y,
                "planets": [dict(p, name=f"World {i + 1}") for i, p in enumerate(worlds)],
            }
        )
    return {
        "systems": systems,
        "routes": [list(pair) for pair in sorted(routes)],
        "starting_sites": sorted(sites),
    }


SYLLABLES = (
    "ka reth el yn dra tha los vey is ha ra no vis sa thir mi rel or a tan cae lis ty xan dor "
    "zy ron ve ga al tar ri on pha lu sol nyx qua ser mon kel vi an ze yr ul ith ae dun cor "
    "bel sy os qui ren tes mar lo ix"
).split()
SUFFIXES = ("Prime", "II", "III", "Majoris", "Minoris")


def syllable_name(random):
    """Two or three syllables (4 to 9 letters), sometimes a suffix: Kareth, Vislor Prime."""
    while True:
        parts = 2 if random.below(10) < 7 else 3
        word = "".join(SYLLABLES[random.below(len(SYLLABLES))] for _ in range(parts))
        if 4 <= len(word) <= 9:
            break
    name = word[0].upper() + word[1:]
    if random.below(100) < 8:
        name += " " + SUFFIXES[random.below(len(SUFFIXES))]
    return name


def validate_v2(world, rules, empires):
    """Acceptance does not trust the construction."""
    systems, routes, sites = world["systems"], world["routes"], world["starting_sites"]
    count = len(systems)
    if any(not 0 <= a < b < count for a, b in routes) or len({tuple(r) for r in routes}) != len(
        routes
    ):
        return ["route_integrity"], {}
    graph = adjacency(count, [tuple(r) for r in routes])
    errors = set()
    if len(_distances(graph, 0)) != count:
        return ["connected"], {}
    degrees = [len(g) for g in graph]
    if min(degrees) < 1 or max(degrees) > rules.max_degree:
        errors.add("degree")
    points = [(s["x"], s["y"]) for s in systems]
    buckets = {}
    for i, (x, y) in enumerate(points):
        buckets.setdefault((x // rules.spacing, y // rules.spacing), []).append(i)
    for i, (x, y) in enumerate(points):
        cx, cy = x // rules.spacing, y // rules.spacing
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in buckets.get((cx + dx, cy + dy), []):
                    if j > i and (x - points[j][0]) ** 2 + (y - points[j][1]) ** 2 < (
                        rules.min_separation**2
                    ):
                        errors.add("separation")
    if any(
        (points[a][0] - points[b][0]) ** 2 + (points[a][1] - points[b][1]) ** 2
        > rules.max_route_length**2
        for a, b in routes
    ):
        errors.add("route_length")
    dead_ends = sum(d == 1 for d in degrees)
    bridges = _bridges(count, graph)
    if not dead_ends:
        errors.add("dead_ends")
    if not [b for b in bridges if min(degrees[b[0]], degrees[b[1]]) > 1]:
        errors.add("chokepoints")  # at least one bottleneck that is not a mere dead end
    if len(sites) != empires or len(set(sites)) != empires:
        errors.add("sites")
    core = []
    for site in sites:
        zone = _zone(graph, site)
        if len(zone) < rules.min_start_zone_size or degrees[site] < 3:
            errors.add("starting_zone")
        if not two_exits(graph, site, set(zone)):
            errors.add("starting_exits")
        home = systems[site]["planets"][0]
        if (home["sectors"], home["orbitals"]) != (rules.starting_sectors, rules.starting_orbitals):
            errors.add("home")
        core.append(
            canonical(
                [
                    [(p["sectors"], p["orbitals"]) for p in systems[n]["planets"]]
                    for n in zone[: rules.min_start_zone_size]
                ]
            )
        )
        reach = _distances(graph, site)
        if any(reach.get(other, 0) < rules.min_start_distance for other in sites if other != site):
            errors.add("starting_distance")
    if len(set(core)) > 1:
        errors.add("fairness")
    for system in systems:
        planets = system["planets"]
        if len(planets) not in map(int, rules.planet_counts):
            errors.add("planet_count")
        if not any(
            p["sectors"] >= rules.useful_sectors and p["orbitals"] >= rules.useful_orbitals
            for p in planets
        ):
            errors.add("useful_world")
    return sorted(errors), {"dead_ends": dead_ends, "bridges": len(bridges), "routes": len(routes)}


def generate_v2(seed: str, rules: GalaxyRulesV2, *, size=None, empires=None):
    size = rules.default_size if size is None else size
    if type(size) is not int or str(size) not in rules.sizes:
        raise ValueError("Invalid generation input")
    cap = rules.empire_cap(size)
    empires = cap if empires is None else empires
    if type(seed) is not str or not 1 <= len(seed) <= 200 or type(empires) is not int or not (
        1 <= empires <= cap
    ):
        raise ValueError("Invalid generation input")
    inputs = {
        "seed": seed,
        "galaxy_generator_version": rules.galaxy_generator_version,
        "system_count": size,
        "starting_site_count": empires,
        "data": rules.model_dump(),
    }
    failures = {}
    for attempt in range(rules.max_attempts):
        world = _candidate(StableRandom([inputs, attempt]), size, empires, rules)
        errors, metrics = validate_v2(world, rules, empires) if world else (["layout"], {})
        if not errors:
            digest = hashlib.sha256(canonical(world).encode()).hexdigest()
            return {
                "inputs": inputs,
                "world": world,
                "attempt": attempt + 1,
                "metrics": {**metrics, "digest": digest},
            }
        for error in errors:
            failures[error] = failures.get(error, 0) + 1
    raise GenerationError(failures)
