"""CapacityUnit — the unit a slot's capacity is measured in.

Shared by ``PickupSlot`` and ``DeliverySlot``. A single slot's
``capacity_total``/``capacity_reserved`` are always in *one* unit —
never mixed (e.g. never comparing an "orders" count against a "kg"
total) — per the Phase 7 spec's explicit "choose explicit capacity
semantics, do not mix units."
"""

import enum


class CapacityUnit(enum.StrEnum):
    ORDERS = "ORDERS"
    WEIGHT_KG = "WEIGHT_KG"
    ITEMS = "ITEMS"
    BAGS = "BAGS"
