"""Galaxy shapes (v0.12, recette 11/11/2026): systems spread over a density map like the reference
carte-galaxie.html: elliptical, two- or four-armed spiral, irregular, star clusters.

Ported from the reference `makeShape`/`generate`: a density over a normalised disc (u, v) with
a vertical squash (tilt), stars sampled by density with a minimum distance, candidate routes from
the Gabriel graph (planar: no two candidates cross) and a few long links joining what density
left apart (clusters). The shape parameters are drawn as integers (thousandths) so that the
client draws the same density as a backdrop (`layout`, see frontend `galaxy/shape.ts`).
"""

import math

SHAPES = ("elliptical", "spiral2", "spiral4", "irregular", "clusters")
SQ = 740  # vertical squash of the disc, thousandths (reference SQ = 0.74)
EXTENT = 1.3  # sampled half-width of the normalised disc
MASK = 0xFFFFFFFF
STRAY = 6  # components smaller than this are stray stars, resampled elsewhere


def _imul(a, b):
    return ((a & MASK) * (b & MASK)) & MASK


def hash2(x, y, s):
    h = _imul(x, 374761393) ^ _imul(y, 668265263) ^ _imul(s + 1, 1442695041)
    h = _imul(h ^ (h >> 13), 1274126177)
    h ^= h >> 16
    return h / 4294967296


def vnoise(x, y, s):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b = hash2(xi, yi, s), hash2(xi + 1, yi, s)
    c, d = hash2(xi, yi + 1, s), hash2(xi + 1, yi + 1, s)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm(x, y, s, octaves):
    total, amp, f, n = 0.0, 0.5, 1.0, 0.0
    for i in range(octaves):
        total += amp * vnoise(x * f, y * f, s + i * 17)
        n += amp
        amp *= 0.5
        f *= 2.03
    return total / n


def smooth(a, b, v):
    t = min(1.0, max(0.0, (v - a) / (b - a)))
    return t * t * (3 - 2 * t)


def draw_params(random, shape):
    """Integer parameters (thousandths) of one shape; `ns` seeds the noise."""
    params = {"ns": random.below(997) + 11}
    if shape == "elliptical":
        params.update(e=780 + random.below(141), rot=random.below(3142))
    elif shape in ("spiral2", "spiral4"):
        params.update(rot=random.below(6283))
    elif shape == "irregular":
        params.update(ox=random.below(60000), oy=random.below(60000), sx=800 + random.below(451))
    else:
        wanted, centres = 5 + random.below(4), []
        for _ in range(800):
            if len(centres) == wanted:
                break
            a = random.below(6283) / 1000
            r = math.sqrt(random.below(1001) / 1000) * 0.8
            x, y = round(math.cos(a) * r * 1000), round(math.sin(a) * r * 1000)
            if all(math.hypot(cx - x, cy - y) > 380 for cx, cy, _ in centres):
                centres.append([x, y, 75 + random.below(81)])
        params["clusters"] = centres
    return params


def density(shape, params):
    """Density in [0, 1] at (u, v) of the normalised disc, same formulas as the reference."""
    ns = params["ns"]
    if shape == "elliptical":
        e, rot = params["e"] / 1000, params["rot"] / 1000
        c, s = math.cos(rot), math.sin(rot)

        def at(u, v):
            a, b = u * c + v * s, (-u * s + v * c) / e
            noise = 0.8 + 0.4 * fbm(u * 2.4 + ns, v * 2.4, ns, 3)
            return min(1.0, math.exp(-(a * a + b * b) / 0.32) * 1.25 * noise)

        return at
    if shape in ("spiral2", "spiral4"):
        arms = 2 if shape == "spiral2" else 4
        twist, w0 = (5.4, 0.075) if arms == 2 else (4.2, 0.058)
        rot = params["rot"] / 1000

        def at(u, v):
            r = math.hypot(u, v)
            if r > 1.3:
                return 0.0
            th = math.atan2(v, u) + 0.45 * (fbm(u * 2.3 + ns, v * 2.3, ns, 3) - 0.5)
            best = 9.0
            for k in range(arms):
                d = th - (r * twist + rot + k * 2 * math.pi / arms)
                d = ((d + math.pi) % (2 * math.pi) + 2 * math.pi) % (2 * math.pi) - math.pi
                best = min(best, abs(d))
            lin, w = best * max(r, 0.1), w0 + 0.055 * r
            arm = math.exp(-lin * lin / (2 * w * w)) * smooth(1.12, 0.68, r)
            core = math.exp(-((r / 0.15) ** 2))
            disk = 0.07 * math.exp(-((r / 0.75) ** 2))
            return min(1.0, max(core, arm * 0.95) + disk)

        return at
    if shape == "irregular":
        ox, oy, sx = params["ox"] / 1000, params["oy"] / 1000, params["sx"] / 1000

        def at(u, v):
            r, n = math.hypot(u * sx, v), fbm(u * 1.3 + ox, v * 1.3 + oy, ns, 4)
            return smooth(0.46, 0.64, n + 0.32 * (0.68 - r)) * smooth(1.25, 0.82, r)

        return at
    centres = [(x / 1000, y / 1000, sg / 1000) for x, y, sg in params["clusters"]]

    def at(u, v):
        m = 0.0
        for x, y, sg in centres:
            dx, dy = u - x, v - y
            m = max(m, math.exp(-(dx * dx + dy * dy) / (2 * sg * sg)))
        return min(1.0, m * 1.15) + 0.012 * smooth(1.1, 0.4, math.hypot(u, v))

    return at


def _rf(random):
    return random.below(1 << 53) / (1 << 53)


def place(random, count, shape, rules):
    """`count` points by density with the minimum distance, Gabriel candidate pairs plus long
    links for connectivity, and the layout the client draws; None when the shape cannot hold
    `count` systems (another attempt follows)."""
    params = draw_params(random, shape)
    at = density(shape, params)
    sq = SQ / 1000
    step = 0.04
    grid = [i * step - EXTENT for i in range(int(2 * EXTENT / step) + 1)]
    area = sum(at(u, v) for u in grid for v in grid) * step * step
    # Mean spacing a little above the lattice spacing: the densest spots keep min_separation.
    spacing = rules.spacing * 1.1
    radius = spacing * math.sqrt(count / (area * sq))
    cx = round(EXTENT * radius + rules.spacing)
    cy = round(EXTENT * radius * sq + rules.spacing)
    floor = rules.min_separation / 0.82 + 1
    dmin = max(0.74 * spacing, floor)
    cell = dmin
    buckets, points = {}, []

    def too_close(x, y, limit):
        i, j = int(x // cell), int(y // cell)
        for b in range(j - 2, j + 3):
            for a in range(i - 2, i + 3):
                for px, py in buckets.get((a, b), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < limit * limit:
                        return True
        return False

    def sample():
        nonlocal dmin
        fails, tries = 0, 0
        while len(points) < count and tries < count * 4000:
            tries += 1
            u, v = (2 * _rf(random) - 1) * EXTENT, (2 * _rf(random) - 1) * EXTENT
            d = min(1.0, at(u, v))
            if d < 0.05 or _rf(random) >= d:
                continue
            x, y = round(cx + u * radius), round(cy + v * radius * sq)
            if too_close(x, y, max(rules.min_separation + 1, dmin * (1.12 - 0.3 * d))):
                fails += 1
                if fails > count * 40:
                    dmin, fails = max(floor, dmin * 0.93), 0
                continue
            buckets.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
            points.append((x, y))

    # Stray stars (a lone point far from any other) would need a too long route: they are
    # dropped and the count refilled where density allows, a few rounds at most.
    for _ in range(6):
        sample()
        if len(points) < count:
            return None
        pairs = gabriel(points, rules.shapes.max_route_length)
        groups = _groups(len(points), pairs)
        stray = {n for g in groups if len(g) < STRAY and len(groups) > 1 for n in g}
        if not stray:
            break
        points[:] = [p for n, p in enumerate(points) if n not in stray]
        buckets.clear()
        for x, y in points:
            buckets.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
    else:
        return None
    pairs |= _joins(points, pairs)
    layout = {
        "shape": shape,
        "cx": cx,
        "cy": cy,
        "radius": round(radius),
        "squash": SQ,
        "params": params,
    }
    return points, sorted(pairs), layout


def gabriel(points, limit):
    """Pairs within `limit` whose diametral circle holds no other point (planar graph)."""
    cell = limit
    buckets = {}
    for i, (x, y) in enumerate(points):
        buckets.setdefault((int(x // cell), int(y // cell)), []).append(i)

    def near(x, y):
        i, j = int(x // cell), int(y // cell)
        for b in range(j - 1, j + 2):
            for a in range(i - 1, i + 2):
                yield from buckets.get((a, b), ())

    result = set()
    for i, (ax, ay) in enumerate(points):
        for j in near(ax, ay):
            if j <= i:
                continue
            bx, by = points[j]
            d2 = (ax - bx) ** 2 + (ay - by) ** 2
            if d2 > limit * limit:
                continue
            mx, my, r2 = (ax + bx) / 2, (ay + by) / 2, d2 / 4
            if all(
                k in (i, j) or (points[k][0] - mx) ** 2 + (points[k][1] - my) ** 2 >= r2 * 1.02
                for k in near(mx, my)
            ):
                result.add((i, j))
    return result


def _groups(count, pairs):
    parent = list(range(count))

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for a, b in pairs:
        parent[find(a)] = find(b)
    groups = {}
    for n in range(count):
        groups.setdefault(find(n), []).append(n)
    return list(groups.values())


def _joins(points, pairs):
    """Shortest links merging every component into the largest one (reference union-find)."""
    parent = list(range(len(points)))

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for a, b in pairs:
        parent[find(a)] = find(b)
    added = set()
    while True:
        groups = {}
        for n in range(len(points)):
            groups.setdefault(find(n), []).append(n)
        if len(groups) <= 1:
            return added
        ordered = sorted(groups.values(), key=lambda g: (-len(g), g[0]))
        main = ordered[0]
        # Every other component joins the largest one by its own shortest link, in one pass.
        for group in ordered[1:]:
            best = None
            for i in group:
                for j in main:
                    d = (points[i][0] - points[j][0]) ** 2 + (points[i][1] - points[j][1]) ** 2
                    if best is None or d < best[0]:
                        best = (d, min(i, j), max(i, j))
            added.add(best[1:])
            parent[find(best[1])] = find(best[2])
