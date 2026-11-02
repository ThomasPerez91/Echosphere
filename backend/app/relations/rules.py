"""Pinned relations data and pure logical-date rules. No database, clock or worker order here.

Q18 (step 13): two relation states only, NO_AGREEMENT and PACT. Hostility is a dated fact per
side, never a state. Every decision compares server logical dates: a pact covers an instant t
when it was accepted at or before t and its notice has not ended at t (`ends_at` exclusive).
"""

from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Seconds = Annotated[int, Field(strict=True, gt=0, le=30 * 24 * 3600)]

NO_AGREEMENT, PACT = "NO_AGREEMENT", "PACT"


class RelationsRules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: str
    relations_version: Literal["relations-v1"]
    proposal_ttl_seconds: Seconds
    refusal_cooldown_seconds: Seconds
    notice_seconds: Seconds

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
