"""Pure deterministic Combat resolver: versioned JSON in, JSON out, no DB, clock or randomness.

Simultaneous rounds: counts are frozen at the start of a round, each living class aims at the
living enemy class with its best matchup (ties: canonical class order), integer damage
count x attack x matchup_bps accumulates per target class, one unit costs hull x 10000, losses
apply at the end of the round. Surplus on an extinct class is lost; no retargeting in a round.
"""

from copy import deepcopy

SIDES = ("attacker", "defender")
OUTCOMES = ("attacker_win", "defender_win", "mutual_destruction", "unopposed")


class CombatInputError(ValueError):
    pass


def _forces(raw, classes, side):
    if not isinstance(raw, dict) or not set(raw) <= set(classes):
        raise CombatInputError(f"Invalid {side} composition")
    if any(type(v) is not int or v < 0 for v in raw.values()):
        raise CombatInputError(f"Invalid {side} counts")
    return {c: raw.get(c, 0) for c in classes}


def resolve(spec):
    """`spec`: combat_version, classes, stats, matchups_bps, max_rounds, attacker, defender.

    combat-v2 (DEF-01, v0.13) adds `defender_shield`: points (hull units) absorbed, round after
    round, from the damage aimed at the defender before any hull, in canonical class order; the
    shield never regenerates within a battle. Every other rule is combat-v1's.
    """
    spec = deepcopy(spec)
    classes = spec["classes"]
    stats, matchups, max_rounds = spec["stats"], spec["matchups_bps"], spec["max_rounds"]
    version = spec.get("combat_version")
    if version not in ("combat-v1", "combat-v2") or type(max_rounds) is not int or max_rounds < 1:
        raise CombatInputError("Unsupported combat specification")
    shield = spec.get("defender_shield", 0) if version == "combat-v2" else 0
    if type(shield) is not int or shield < 0 or (
        "defender_shield" in spec and version != "combat-v2"
    ):
        raise CombatInputError("Invalid defender shield")
    shield *= 10000  # same scale as hull x 10000
    initial_shield = shield
    if set(stats) != set(classes) or set(matchups) != set(classes):
        raise CombatInputError("Incomplete combat specification")
    counts = {side: _forces(spec[side], classes, side) for side in SIDES}
    if not any(counts["attacker"].values()):
        raise CombatInputError("An attack engages at least one military unit")
    initial = deepcopy(counts)
    pending = {side: dict.fromkeys(classes, 0) for side in SIDES}
    rounds = []
    if not any(counts["defender"].values()):
        outcome = "unopposed"
    else:
        while any(counts["attacker"].values()) and any(counts["defender"].values()):
            if len(rounds) >= max_rounds:
                raise CombatInputError("Combat exceeded its round bound")
            before = deepcopy(counts)
            targets, damage = {}, {}
            for side, enemy in (("attacker", "defender"), ("defender", "attacker")):
                targets[side], damage[side] = {}, dict.fromkeys(classes, 0)
                alive = [c for c in classes if before[enemy][c]]
                for shooter in classes:
                    if not before[side][shooter]:
                        continue
                    # Best multiplier; max() keeps the first maximum in canonical class order.
                    target = max(alive, key=lambda t, s=shooter: matchups[s][t])
                    targets[side][shooter] = target
                    damage[side][target] += (
                        before[side][shooter] * stats[shooter]["attack"] * matchups[shooter][target]
                    )
            absorbed = 0
            if shield:
                for target in classes:
                    taken = min(shield, damage["attacker"][target])
                    damage["attacker"][target] -= taken
                    shield -= taken
                    absorbed += taken
            losses = {side: dict.fromkeys(classes, 0) for side in SIDES}
            for side, enemy in (("attacker", "defender"), ("defender", "attacker")):
                for target in classes:
                    if not damage[side][target]:
                        continue
                    pool = pending[enemy][target] + damage[side][target]
                    per_unit = stats[target]["hull"] * 10000
                    killed = min(before[enemy][target], pool // per_unit)
                    losses[enemy][target] = killed
                    # Partial damage carries over; an extinct class loses its surplus.
                    alive_after = before[enemy][target] - killed
                    pending[enemy][target] = pool - killed * per_unit if alive_after else 0
            for side in SIDES:
                for c in classes:
                    counts[side][c] -= losses[side][c]
            entry = {
                "round": len(rounds) + 1,
                "before": before,
                "targets": targets,
                "damage": damage,
                "losses": losses,
            }
            if version == "combat-v2":
                entry["shield_absorbed"] = absorbed // 10000
                entry["shield_left"] = shield // 10000
            rounds.append(entry)
        attacker_left = any(counts["attacker"].values())
        defender_left = any(counts["defender"].values())
        outcome = (
            "attacker_win"
            if attacker_left
            else ("defender_win" if defender_left else "mutual_destruction")
        )
    result = {
        "combat_version": version,
        "outcome": outcome,
        "initial": initial,
        "rounds": rounds,
        "losses": {s: {c: initial[s][c] - counts[s][c] for c in classes} for s in SIDES},
        "survivors": counts,
    }
    if version == "combat-v2":
        result["shield"] = {"initial": initial_shield // 10000, "left": shield // 10000}
    return result


def spec_from_rules(rules, attacker, defender, shield=0):
    """The exact resolver input from pinned CombatRules; stored whole in the engagement."""
    classes = rules.all_classes
    stats = {c: rules.stats[c].model_dump() for c in rules.classes}
    stats |= {c: s.model_dump() for c, s in (rules.modules or {}).items()}
    spec = {
        "combat_version": rules.combat_version,
        "classes": list(classes),
        "stats": stats,
        "matchups_bps": {c: dict(rules.matchups_bps[c]) for c in classes},
        "max_rounds": rules.max_rounds,
        "attacker": {c: attacker.get(c, 0) for c in classes},
        "defender": {c: defender.get(c, 0) for c in classes},
    }
    if rules.combat_version == "combat-v2":
        spec["defender_shield"] = shield
    return spec


def allocate_losses(fleets, losses):
    """Largest remainder per class over the pre-combat holdings; ties by stable fleet id.

    `fleets`: {fleet_id: {class: count}}, `losses`: {class: count}. Splitting or merging the
    same holdings never changes the global losses, only their distribution.
    """
    result = {f: {} for f in fleets}
    for c, lost in losses.items():
        holders = sorted((f, s.get(c, 0)) for f, s in fleets.items() if s.get(c, 0))
        total = sum(n for _, n in holders)
        if lost > total or lost < 0:
            raise CombatInputError("Losses exceed the engaged holdings")
        if not lost:
            continue
        shares = [(f, n, lost * n // total, lost * n % total) for f, n in holders]
        left = lost - sum(q for _, _, q, _ in shares)
        bonus = {f for f, _, _, _ in sorted(shares, key=lambda x: (-x[3], x[0]))[:left]}
        for f, _, q, _ in shares:
            taken = q + (1 if f in bonus else 0)
            if taken:
                result[f][c] = taken
    return result
