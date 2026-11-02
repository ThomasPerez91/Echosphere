"""Pure deterministic Utility/Goals. Inputs/outputs contain JSON values only, no DB callbacks."""

from copy import deepcopy

from app.ai.rules import canonical


def circular_page(items, cursor, size):
    """Bounded reference-family traversal; no quotes or candidates materialized before visiting.

    `items` is a bounded authorized identifier collection, not a Fleet×Planet product.
    A stable family of M references is completely visited in ceil(M/size) visits.
    """
    if not items:
        return [], 0
    start = cursor % len(items)
    count = min(size, len(items))
    return [items[(start + i) % len(items)] for i in range(count)], (start + count) % len(items)


def choose(observation, memory, profile, rules):
    # Canonical serialization also rejects arbitrary non-JSON objects, NaN and ORM values.
    canonical(observation)
    canonical(memory)
    if profile not in rules.profiles or len(observation["candidates"]) > rules.candidate_limit:
        raise ValueError("Invalid profile or candidate budget")
    rows = []

    # Bootstrap (Q11) or, in v0.7, an under-defended colony under an announced attack: an
    # eligible priority candidate preempts the others. v0.6 candidates carry no `priority` key.
    def first(c):
        return c["bootstrap"] or c.get("priority", False)

    urgent = any(first(c) and c["reason"] is None for c in observation["candidates"])
    for c in observation["candidates"]:
        utility = c["utility"]
        if type(utility) is not int or not 0 <= utility <= 1000 or c["goal"] not in rules.goals:
            raise ValueError("Invalid utility feature")
        if (
            set(c["cost"]) != {"alloys", "flux", "data"}
            or any(type(v) is not int or v < 0 for v in c["cost"].values())
            or type(c["duration_us"]) is not int
            or c["duration_us"] < 0
        ):
            raise ValueError("Costs and durations must be nonnegative integers")
        reason = c["reason"] or ("bootstrap_priority" if urgent and not first(c) else None)
        rows.append(
            {
                "key": c["key"],
                "goal": c["goal"],
                "utility": utility,
                "score": rules.profiles[profile][c["goal"]] * utility,
                "reason": reason,
                "cost": c["cost"],
                "duration_us": c["duration_us"],
            }
        )
    ranked = sorted(
        (r for r in rows if r["reason"] is None and r["utility"] > 0),
        key=lambda r: (
            -r["score"],
            tuple(r["cost"][v] for v in ("alloys", "flux", "data")),
            r["duration_us"],
            r["key"],
        ),
    )
    return {
        "choice": ranked[0]["key"] if ranked else None,
        "goals": list(rules.goals),
        "evaluated": deepcopy(rows),
        "tie_break": ["score_desc", "alloys", "flux", "data", "duration_us", "key"],
    }
