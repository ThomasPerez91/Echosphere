"""galaxy-v1: protected initial lobes, seeded central network, independent acceptance checks.

Pure canonical values only: no DB UUID, wall clock, Python hash or frontend layout. Candidate
sites are geometry/fairness evidence, never reservations. Failed candidates publish nothing.
"""

import hashlib
import json
from collections import deque
from copy import deepcopy
from itertools import combinations

from app.galaxy.rules import GalaxyRules


class GenerationError(ValueError):
    def __init__(self, constraints):
        super().__init__("generation_constraints_unsatisfied")
        self.constraints = constraints


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class StableRandom:
    """Specified SHA-256 counter stream with rejection sampling, versioned by galaxy-v1."""

    def __init__(self, value):
        self.key = canonical(value).encode("utf-8")
        self.counter = 0

    def below(self, bound):
        limit = (1 << 256) - ((1 << 256) % bound)
        while True:
            block = hashlib.sha256(self.key + b"\0" + str(self.counter).encode("ascii")).digest()
            self.counter += 1
            value = int.from_bytes(block, "big")
            if value < limit:
                return value % bound

    def shuffle(self, values):
        values = list(values)
        for i in range(len(values) - 1, 0, -1):
            j = self.below(i + 1)
            values[i], values[j] = values[j], values[i]
        return values

    def weighted(self, weights):
        value = self.below(sum(weights.values()))
        for key in sorted(weights, key=int):
            value -= weights[key]
            if value < 0:
                return int(key)
        raise AssertionError("Unreachable weighted draw")


def adjacency(count, routes):
    graph = [set() for _ in range(count)]
    for a, b in routes:
        graph[a].add(b)
        graph[b].add(a)
    return graph


def distances(graph, source, ignored=None):
    result = {source: 0}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for other in sorted(graph[node]):
            if ignored == tuple(sorted((node, other))) or other in result:
                continue
            result[other] = result[node] + 1
            queue.append(other)
    return result


def two_exits(graph, root, zone):
    """Unit vertex-capacity max flow to distinct vertices outside the radius-two zone."""
    size = 2 * len(graph) + 1
    sink = size - 1
    residual = [dict() for _ in range(size)]

    def edge(a, b, capacity):
        residual[a][b] = capacity
        residual[b].setdefault(a, 0)

    for node in range(len(graph)):
        edge(2 * node, 2 * node + 1, 2 if node == root else 1)
        if node not in zone:
            edge(2 * node + 1, sink, 1)
        else:
            for other in sorted(graph[node]):
                edge(2 * node + 1, 2 * other, 2)
    for _ in range(2):
        parents = {2 * root: None}
        queue = deque([2 * root])
        while queue and sink not in parents:
            node = queue.popleft()
            for other, cap in residual[node].items():
                if cap and other not in parents:
                    parents[other] = node
                    queue.append(other)
        if sink not in parents:
            return False
        node = sink
        while parents[node] is not None:
            parent = parents[node]
            residual[parent][node] -= 1
            residual[node][parent] += 1
            node = parent
    return True


def validate(world, rules):
    """Acceptance does not trust the construction: inspect every final node/edge/world/site."""
    systems, routes, sites = world["systems"], world["routes"], world["starting_sites"]
    count = len(systems)
    errors = set()
    if not rules.min_systems <= count <= rules.max_systems:
        return ["system_count"], {}
    if any(not 0 <= a < b < count for a, b in routes) or len(set(map(tuple, routes))) != len(
        routes
    ):
        return ["route_integrity"], {}
    graph = adjacency(count, routes)
    lengths = [distances(graph, node) for node in range(count)]
    if any(len(row) != count for row in lengths):
        return ["connected"], {}
    degrees = [len(row) for row in graph]
    if min(degrees) < rules.min_degree or max(degrees) > rules.max_degree:
        errors.add("degree")
    degree_sum = sum(degrees)
    if (
        not rules.min_mean_degree_bps * count
        <= degree_sum * 10000
        <= (rules.max_mean_degree_bps * count)
    ):
        errors.add("mean_degree")
    if sum(d >= 3 for d in degrees) * 10000 < count * rules.min_junction_bps:
        errors.add("junctions")
    diameter = max(max(row.values()) for row in lengths)
    path_sum = sum(sum(row.values()) for row in lengths)
    if diameter > (count + rules.diameter_divisor - 1) // rules.diameter_divisor:
        errors.add("diameter")
    if path_sum * 10000 > rules.max_mean_path_bps * count * (count - 1):
        errors.add("mean_path")
    if any(len(distances(graph, a, (a, b))) != count for a, b in routes):
        errors.add("bridges")
    points = [(s["x"], s["y"]) for s in systems]

    def squared(a, b):
        return sum((points[a][i] - points[b][i]) ** 2 for i in (0, 1))

    if any(type(v) is not int or not 0 <= v <= rules.coordinate_limit for p in points for v in p):
        errors.add("positions")
    if any(squared(a, b) < rules.min_separation**2 for a, b in combinations(range(count), 2)):
        errors.add("separation")
    if any(squared(a, b) > rules.max_route_length**2 for a, b in routes):
        errors.add("route_length")
    for system in systems:
        planets = system["planets"]
        if len(planets) not in map(int, rules.planet_counts):
            errors.add("planet_count")
        if not any(
            p["sectors"] >= rules.useful_sectors and p["orbitals"] >= rules.useful_orbitals
            for p in planets
        ):
            errors.add("useful_world")
        if any(
            p["sectors"] not in map(int, rules.sector_capacities)
            or p["orbitals"] not in map(int, rules.orbital_capacities)
            for p in planets
        ):
            errors.add("capacities")
    metrics = []
    if len(sites) != len(set(sites)) or not 1 <= len(sites) <= rules.max_starting_sites:
        errors.add("sites")
    for site in sites:
        zone = {n for n, d in lengths[site].items() if d <= 2}
        planets = [p for n in sorted(zone) for p in systems[n]["planets"]]
        metrics.append(
            [
                len(zone),
                sum(
                    p["sectors"] >= rules.useful_sectors and p["orbitals"] >= rules.useful_orbitals
                    for p in planets
                ),
                sum(p["sectors"] for p in planets),
                sum(p["orbitals"] for p in planets),
            ]
        )
        if len(zone) < rules.min_start_zone_size or degrees[site] < 3:
            errors.add("starting_zone")
        if not two_exits(graph, site, zone):
            errors.add("starting_exits")
        home = systems[site]["planets"][0]
        if (home["sectors"], home["orbitals"]) != (rules.starting_sectors, rules.starting_orbitals):
            errors.add("home")
    if any(lengths[a][b] < rules.min_start_distance for a, b in combinations(sites, 2)):
        errors.add("starting_distance")
    for column in zip(*metrics, strict=True):
        if min(column) <= 0 or max(column) * 10000 > min(column) * rules.fairness_ratio_bps:
            errors.add("fairness")
    return sorted(errors), {
        "diameter": diameter,
        "path_sum": path_sum,
        "pair_count": count * (count - 1),
        "degree_sum": degree_sum,
        "starting_metrics": metrics,
    }


def _candidate(random, count, site_count, rules):
    # Four protected lobes ensure six-hop spacing even at the supported 30-node boundary.
    # Geometry templates are part of galaxy-v1; resource quantities remain pinned data.
    template = [(80, 80), (170, 80), (80, 170), (170, 170), (260, 170), (170, 260), (260, 260)]
    points, routes = [], set()

    def edge(a, b):
        routes.add(tuple(sorted((a, b))))

    for quadrant in range(4):
        offset = len(points)
        for x, y in template:
            points.append((x if quadrant % 2 == 0 else 1000 - x, y if quadrant < 2 else 1000 - y))
        for a, b in [(0, 1), (0, 2), (0, 3), (1, 4), (2, 5), (3, 6), (4, 5), (5, 6), (4, 6)]:
            edge(offset + a, offset + b)
    central = [(330 + 85 * x, 330 + 85 * y) for x in range(5) for y in range(5)]
    # Small central networks start near the center; ties are seeded, never set iteration.
    ranked = random.shuffle(central)
    ranked.sort(key=lambda p: (p[0] - 500) ** 2 + (p[1] - 500) ** 2)
    points += ranked[: count - 28]
    points = [(x + random.below(5) - 2, y + random.below(5) - 2) for x, y in points]
    degrees = [0] * count
    for a, b in routes:
        degrees[a] += 1
        degrees[b] += 1

    def nearby(a, b):
        return sum((points[a][i] - points[b][i]) ** 2 for i in (0, 1)) <= (
            rules.max_route_length**2
        )

    for quadrant in random.shuffle(range(4)):
        used = set()
        for leaf in random.shuffle([quadrant * 7 + 4, quadrant * 7 + 6]):
            choices = random.shuffle(range(28, count))
            choices.sort(key=lambda n: degrees[n])
            node = next(
                (
                    n
                    for n in choices
                    if n not in used and degrees[n] < rules.max_degree and nearby(leaf, n)
                ),
                None,
            )
            if node is None:
                return None
            used.add(node)
            edge(leaf, node)
            degrees[leaf] += 1
            degrees[node] += 1
    target = min((3 * count) // 2, 44 + 2 * (count - 28) - 4)
    while len(routes) < target:
        options = random.shuffle(
            [
                (a, b)
                for a, b in combinations(range(28, count), 2)
                if (a, b) not in routes
                and degrees[a] < rules.max_degree
                and degrees[b] < rules.max_degree
                and nearby(a, b)
            ]
        )
        if not options:
            break
        options.sort(
            key=lambda pair: (min(degrees[n] for n in pair), sum(degrees[n] for n in pair))
        )
        a, b = options[0]
        edge(a, b)
        degrees[a] += 1
        degrees[b] += 1

    def worlds():
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

    # Equal initial resource budgets, with seeded placement permutation within each zone.
    # Correlation deliberately guarantees four-metric fairness without late balance mutations.
    budget = [worlds() for _ in range(7)]
    budget[0][0] = {"sectors": rules.starting_sectors, "orbitals": rules.starting_orbitals}
    systems = []
    for node, (x, y) in enumerate(points):
        planets = deepcopy(budget[node % 7]) if node < 28 else worlds()
        systems.append(
            {
                "name": f"System {random.below(1000000):06d}",
                "x": x,
                "y": y,
                "planets": [dict(p, name=f"World {i + 1}") for i, p in enumerate(planets)],
            }
        )
    return {
        "systems": systems,
        "routes": [list(pair) for pair in sorted(routes)],
        "starting_sites": sorted(random.shuffle([0, 7, 14, 21])[:site_count]),
    }


def generate(seed: str, rules: GalaxyRules, *, system_count=None, starting_site_count=None):
    count = rules.system_count if system_count is None else system_count
    sites = rules.starting_site_count if starting_site_count is None else starting_site_count
    if (
        type(seed) is not str
        or not 1 <= len(seed) <= 200
        or type(count) is not int
        or not rules.min_systems <= count <= rules.max_systems
        or type(sites) is not int
        or not 1 <= sites <= rules.max_starting_sites
    ):
        raise ValueError("Invalid generation input")
    inputs = {
        "seed": seed,
        "galaxy_generator_version": rules.galaxy_generator_version,
        "system_count": count,
        "starting_site_count": sites,
        "data": rules.model_dump(),
    }
    failures = {}
    for attempt in range(rules.max_attempts):
        world = _candidate(StableRandom([inputs, attempt]), count, sites, rules)
        errors, metrics = validate(world, rules) if world else (["layout"], {})
        if not errors:
            return {"inputs": inputs, "world": world, "attempt": attempt + 1, "metrics": metrics}
        for error in errors:
            failures[error] = failures.get(error, 0) + 1
    raise GenerationError(failures)
