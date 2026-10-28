"""Exact fixed-point arithmetic, independent of HTTP, database and wall clock."""

from dataclasses import dataclass
from datetime import datetime

from app.simulation.clock import utc

MICRO_UNITS = 1_000_000
MICROSECONDS_PER_HOUR = 3_600_000_000
MAX_AMOUNT = 2**63 - 1
RESOURCES = frozenset({"alloys", "flux", "data"})


def amount(value: int) -> int:
    if type(value) is not int or not 0 <= value <= MAX_AMOUNT:
        raise ValueError("Amount must be a nonnegative signed 64-bit integer in micro-units")
    return value


@dataclass(frozen=True)
class ProductionState:
    stock: int
    rate_per_hour: int
    at: datetime
    remainder: int = 0
    capacity: int | None = None

    def __post_init__(self) -> None:
        amount(self.stock)
        amount(self.rate_per_hour)
        utc(self.at)
        if type(self.remainder) is not int or not 0 <= self.remainder < MICROSECONDS_PER_HOUR:
            raise ValueError("Invalid production remainder")
        if self.capacity is not None:
            amount(self.capacity)
            if self.stock > self.capacity:
                raise ValueError("Stock exceeds explicit capacity")


def produce(state: ProductionState, until: datetime) -> ProductionState:
    target = utc(until)
    delta = target - utc(state.at)
    if delta.days < 0:
        raise ValueError("Cannot settle production backwards")
    elapsed = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    if elapsed == 0:
        return state
    whole, remainder = divmod(
        state.rate_per_hour * elapsed + state.remainder,
        MICROSECONDS_PER_HOUR,
    )
    stock = state.stock + whole
    if state.capacity is not None and stock >= state.capacity:
        stock, remainder = state.capacity, 0
    amount(stock)  # Overflow is an explicit failure, never wrap or silent clipping.
    return ProductionState(stock, state.rate_per_hour, target, remainder, state.capacity)
