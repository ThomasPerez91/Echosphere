"""Pinned relations data and pure logical-date rules. No database, clock or worker order here.

Q18 (step 13): two relation states only, NO_AGREEMENT and PACT. Hostility is a dated fact per
side, never a state. Every decision compares server logical dates: a pact covers an instant t
when it was accepted at or before t and its notice has not ended at t (`ends_at` exclusive).
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.rules_dump import omit_unset_extensions

Seconds = Annotated[int, Field(strict=True, gt=0, le=30 * 24 * 3600)]

NO_AGREEMENT, PACT = "NO_AGREEMENT", "PACT"
Points = Annotated[int, Field(strict=True, ge=-100, le=100)]
Days = Annotated[int, Field(strict=True, gt=0, le=365)]
STANDING_LABELS = ("hostile", "wary", "neutral", "cordial", "allied")


class Standing(BaseModel):
    """v0.12 (recette 10/11/2026): relation score -100..100 read from dated server facts only
    (pact, notice, proposals, hostile acts); never stored, never a cause of any rule."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    pact: Points
    pact_per_day: Points
    pact_max_bonus: Points
    notice: Points
    proposal_received: Points
    hostile_received_recent: Points
    hostile_received_old: Points
    hostile_given_recent: Points
    recent_days: Days
    old_days: Days
    # Upper bounds of hostile, wary, neutral, cordial (allied above the last one).
    thresholds: list[Points] = Field(min_length=4, max_length=4)


def standing(terms: Standing, view: dict, at: datetime) -> dict:
    """Score and its factors from one side view of `project` (ISO dates, server time `at`)."""

    def date(value):
        return datetime.fromisoformat(value) if value else None

    factors = []
    pact = view.get("pact")
    if pact:
        days = max(0, (at - date(pact["accepted_at"])).days)
        factors.append(("pact", terms.pact))
        if days and terms.pact_per_day:
            factors.append(("pact_age", min(terms.pact_max_bonus, days * terms.pact_per_day)))
        if pact.get("notice"):
            factors.append(("notice", terms.notice))
    proposal = view.get("proposal")
    if proposal and proposal["direction"] == "received":
        factors.append(("proposal_received", terms.proposal_received))
    hostility = view.get("hostility") or {}
    recent, old = timedelta(days=terms.recent_days), timedelta(days=terms.old_days)
    received = date(hostility.get("by_counterpart_at"))
    if received and received > at - recent:
        factors.append(("hostile_received", terms.hostile_received_recent))
    elif received and received > at - old:
        factors.append(("hostile_received", terms.hostile_received_old))
    given = date(hostility.get("by_self_at"))
    if given and given > at - recent:
        factors.append(("hostile_given", terms.hostile_given_recent))
    score = max(-100, min(100, sum(v for _, v in factors)))
    label = next(
        (STANDING_LABELS[i] for i, bound in enumerate(terms.thresholds) if score <= bound),
        STANDING_LABELS[-1],
    )
    return {
        "score": score,
        "label": label,
        "factors": [{"kind": k, "points": v} for k, v in factors],
    }


class RelationsRules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: str
    relations_version: Literal["relations-v1"]
    proposal_ttl_seconds: Seconds
    refusal_cooldown_seconds: Seconds
    notice_seconds: Seconds
    standing: Standing | None = None
    serialize_extensions = omit_unset_extensions("standing")

    @property
    def proposal_ttl(self) -> timedelta:
        return timedelta(seconds=self.proposal_ttl_seconds)

    @property
    def refusal_cooldown(self) -> timedelta:
        return timedelta(seconds=self.refusal_cooldown_seconds)

    @property
    def notice(self) -> timedelta:
        return timedelta(seconds=self.notice_seconds)


def pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    """Canonical unordered pair, ordered like PostgreSQL orders UUIDs (byte order)."""
    if a == b:
        raise ValueError("A relation needs two distinct Empires")
    return (a, b) if a.bytes < b.bytes else (b, a)


def covers(accepted_at: datetime, ends_at: datetime | None, at: datetime) -> bool:
    """A pact protects `at` iff accepted_at <= at < ends_at (no end: still open)."""
    return accepted_at <= at and (ends_at is None or at < ends_at)


def proposal_open(expires_at: datetime | None, at: datetime) -> bool:
    return expires_at is not None and at < expires_at


def cooled_down(until: datetime | None, at: datetime) -> bool:
    return until is None or until <= at


def recent(fact_at: datetime | None, at: datetime, window: timedelta) -> bool:
    """A hostile fact is a grievance while it is younger than `window` at `at`."""
    return fact_at is not None and fact_at > at - window
