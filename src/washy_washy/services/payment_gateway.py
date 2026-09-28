"""The payment-provider boundary: an abstract ``PaymentGateway`` plus a
deterministic ``ManualPaymentGateway`` implementation — never a
concrete Stripe/Razorpay/etc. integration wired directly into business
logic, per the Phase 10 spec's explicit "create a provider interface
rather than coupling the domain to one gateway."

``PaymentService`` (below) depends only on this interface. Swapping in
a real provider later means writing one more class here and changing
what gets constructed at the app's wiring point — never touching
``PaymentService`` itself. ``ManualPaymentGateway`` is not a stand-in
for a specific real provider; it's a deterministic, always-succeeds
implementation for this project's own dev/test use, in the same spirit
as ``AvailabilityService`` never talking to a real SMS/notification
provider. Tests that need to exercise a *failed* charge/refund inject
their own small fake implementing this same interface, rather than the
gateway needing built-in failure-simulation knobs.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class GatewayResult:
    """Every provider call returns this same shape, regardless of
    which concrete gateway handled it — the point of the abstraction.
    """

    success: bool
    provider_reference: str
    raw: dict


class PaymentGateway(ABC):
    @abstractmethod
    async def charge(self, amount: Decimal, currency: str) -> GatewayResult: ...

    @abstractmethod
    async def refund(self, provider_reference: str, amount: Decimal) -> GatewayResult: ...


class ManualPaymentGateway(PaymentGateway):
    """Deterministic, always-succeeds gateway. Generates a fake but
    realistic-looking ``provider_reference`` (a UUID) — this project
    has no real gateway account to charge against, and the point of
    Phase 10 is the domain's correctness around payments, not a real
    integration.
    """

    async def charge(self, amount: Decimal, currency: str) -> GatewayResult:
        return GatewayResult(
            success=True,
            provider_reference=f"manual_ch_{uuid.uuid4().hex}",
            raw={"amount": str(amount), "currency": currency},
        )

    async def refund(self, provider_reference: str, amount: Decimal) -> GatewayResult:
        return GatewayResult(
            success=True,
            provider_reference=f"manual_re_{uuid.uuid4().hex}",
            raw={"charge_reference": provider_reference, "amount": str(amount)},
        )
