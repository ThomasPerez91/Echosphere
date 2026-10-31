"""Fixed Q06 corpus. Run with PYTHONPATH=backend; prints operator metrics, no user data."""

import json
from statistics import mean
from time import perf_counter

from app.colony.rules import load_ruleset
from app.galaxy.generator import GenerationError, generate


def main():
    rules = load_ruleset("v0.3").galaxy
    reports = []
    for count, sites, total in [
        (40, 4, 1000),
        (30, 1, 100),
        (30, 4, 100),
        (50, 1, 100),
        (50, 4, 100),
    ]:
        elapsed, failures, attempts = [], [], []
        for i in range(total):
            seed = f"galaxy-v1-corpus-{i:04d}"
            start = perf_counter()
            try:
                world = generate(seed, rules, system_count=count, starting_site_count=sites)
                attempts.append(world["attempt"])
            except GenerationError as error:
                failures.append({"seed": seed, "constraints": error.constraints})
            elapsed.append((perf_counter() - start) * 1000)
        reports.append(
            {
                "systems": count,
                "sites": sites,
                "seeds": total,
                "failures": failures,
                "failure_count": len(failures),
                "mean_ms": round(mean(elapsed), 3),
                "p95_ms": round(sorted(elapsed)[(95 * total + 99) // 100 - 1], 3),
                "max_attempts": max(attempts, default=0),
            }
        )
    print(json.dumps(reports, indent=2))
    return 1 if any(r["failures"] for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
