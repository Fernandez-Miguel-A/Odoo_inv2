from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Location:
    id: int
    name: str
    complete_name: str
    parent_id: int | None
    usage: str


@dataclass(slots=True)
class Replenishment:
    id: int
    product_id: int
    sku: str
    product_name: str
    location_id: int
    location_name: str
    on_hand: float
    reserved: float
    incoming: float
    route: str
    minimum: float
    maximum: float
    trigger: str
    snoozed_until: str | None

    @property
    def forecast(self) -> float:
        return round(self.on_hand + self.incoming - self.reserved, 2)

    @property
    def target(self) -> float:
        return self.maximum if self.maximum > self.minimum else self.minimum

    @property
    def to_order(self) -> float:
        if self.snoozed_until:
            return 0.0
        return max(0.0, round(self.target - self.forecast, 2))


@dataclass(slots=True)
class ReplenishmentOrder:
    id: int
    reference: str
    product_name: str
    location_name: str
    quantity: float
    route: str
    status: str
    created_at: str
