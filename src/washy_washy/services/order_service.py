"""Order creation, item management, and ownership-scoped queries.

Deliberately separate from ``order_state_service.py``: this module
owns *what an order/item contains*, the state machine owns *what
status it's in* — the same split the Phase 8 spec draws between
"order state" and "order item state." ``OrderService`` composes
``OrderStateService`` for the two operations that both change order
data *and* move its status in one transaction (``schedule_pickup``,
``finalize_pricing``, ``cancel_order``), rather than duplicating
transition logic here.

Reuses ``PricingService`` (Phase 6) and ``AvailabilityService``
(Phase 7) exactly as they already exist — this is the same kind of
composition a controller does across services, just one layer down,
so the quantity/weight pricing-model dispatch and the atomic slot
capacity reservation are never reimplemented here.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessRuleException, NotFoundException
from core.models.order import Order, OrderStatus
from core.models.order_item import OrderItem
from core.models.order_status_history import OrderStatusHistory
from washy_washy.constants import error_codes, error_messages
from washy_washy.repositories.address_repo import AddressRepository
from washy_washy.repositories.material_repo import MaterialRepository
from washy_washy.repositories.order_item_repo import OrderItemRepository
from washy_washy.repositories.order_repo import OrderRepository
from washy_washy.repositories.order_status_history_repo import OrderStatusHistoryRepository
from washy_washy.repositories.service_area_repo import ServiceAreaRepository
from washy_washy.repositories.service_repo import ServiceRepository
from washy_washy.services.availability_service import AvailabilityService
from washy_washy.services.order_state_service import OrderStateService
from washy_washy.services.pricing_service import PricingService

ZERO = Decimal("0")


@dataclass(frozen=True)
class OrderItemInput:
    service_id: uuid.UUID
    declared_material_id: uuid.UUID
    declared_quantity: int | None = None
    declared_weight_kg: Decimal | None = None


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._orders = OrderRepository(session)
        self._order_items = OrderItemRepository(session)
        self._order_status_history = OrderStatusHistoryRepository(session)
        self._addresses = AddressRepository(session)
        self._service_areas = ServiceAreaRepository(session)
        self._services = ServiceRepository(session)
        self._materials = MaterialRepository(session)
        self._pricing = PricingService(session)
        self._availability = AvailabilityService(session)
        self._order_state = OrderStateService(session)

    # -- Creation ------------------------------------------------------------

    async def create_order(
        self,
        customer_id: uuid.UUID,
        *,
        pickup_address_id: uuid.UUID,
        delivery_address_id: uuid.UUID,
        items: list[OrderItemInput],
        rush_charge: Decimal = ZERO,
        delivery_charge: Decimal = ZERO,
        tax: Decimal = ZERO,
        discount: Decimal = ZERO,
    ) -> Order:
        """Customer -> address -> service area -> service -> estimated
        pricing -> order draft, exactly the Phase 8 spec's own creation
        workflow. Never finalizes a price here -- ``estimated_total``
        only, from each item's ``PriceBreakdown.subtotal`` (base +
        material + care + quantity/weight, no rush/delivery/tax/discount)
        plus the order-level rush/delivery/tax/discount supplied here.
        """
        if not items:
            raise BusinessRuleException(
                error_messages.ORDER_ITEMS_REQUIRED, error_codes.ORDER_ITEMS_REQUIRED
            )

        pickup_address = await self._addresses.get_by_id(pickup_address_id)
        if pickup_address is None or pickup_address.user_id != customer_id:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        delivery_address = await self._addresses.get_by_id(delivery_address_id)
        if delivery_address is None or delivery_address.user_id != customer_id:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

        # The service area is derived from the pickup address rather than
        # caller-supplied, so it can never be inconsistent with where the
        # order is actually being picked up from.
        service_area = await self._service_areas.get_by_postal_code(pickup_address.postal_code)
        if service_area is None:
            raise BusinessRuleException(
                error_messages.ADDRESS_NOT_SERVICEABLE, error_codes.ADDRESS_NOT_SERVICEABLE
            )

        order = await self._orders.create(
            Order(
                customer_id=customer_id,
                service_area_id=service_area.id,
                pickup_address_id=pickup_address_id,
                delivery_address_id=delivery_address_id,
                status=OrderStatus.DRAFT.value,
                estimated_total=ZERO,
            )
        )

        items_subtotal = ZERO
        for item_input in items:
            if await self._services.get_by_id(item_input.service_id) is None:
                raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
            if await self._materials.get_by_id(item_input.declared_material_id) is None:
                raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)

            breakdown = await self._pricing.calculate_price(
                service_id=item_input.service_id,
                material_id=item_input.declared_material_id,
                quantity=item_input.declared_quantity,
                weight_kg=item_input.declared_weight_kg,
            )
            await self._order_items.create(
                OrderItem(
                    order_id=order.id,
                    service_id=item_input.service_id,
                    declared_material_id=item_input.declared_material_id,
                    declared_quantity=item_input.declared_quantity,
                    declared_weight_kg=item_input.declared_weight_kg,
                    estimated_pricing_rule_id=breakdown.pricing_rule_id,
                    estimated_material_pricing_rule_id=breakdown.material_pricing_rule_id,
                    estimated_line_total=breakdown.subtotal,
                )
            )
            items_subtotal += breakdown.subtotal

        order.estimated_total = items_subtotal + rush_charge + delivery_charge + tax - discount
        await self._orders.update(order)

        await self._order_status_history.create(
            OrderStatusHistory(
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.DRAFT.value,
                changed_by_user_id=customer_id,
                reason="Order created",
            )
        )
        return order

    # -- Queries ---------------------------------------------------------

    async def list_own_orders(self, customer_id: uuid.UUID) -> list[Order]:
        return await self._orders.list_for_customer(customer_id)

    async def list_items(self, order_id: uuid.UUID) -> list[OrderItem]:
        return await self._order_items.list_for_order(order_id)

    async def get_history(self, order_id: uuid.UUID) -> list[OrderStatusHistory]:
        return await self._order_state.get_history(order_id)

    async def transition(
        self,
        order_id: uuid.UUID,
        to_status: OrderStatus,
        *,
        requester_user_id: uuid.UUID,
        requester_is_staff: bool,
        changed_by_role: str | None = None,
        reason: str | None = None,
    ) -> Order:
        """Thin pass-through to ``OrderStateService.transition`` -- kept
        here too so callers only ever depend on ``OrderService``, not
        both services at once, for the generic (non-scheduling,
        non-finalizing) transition endpoint.
        """
        return await self._order_state.transition(
            order_id,
            to_status,
            requester_user_id=requester_user_id,
            requester_is_staff=requester_is_staff,
            changed_by_role=changed_by_role,
            reason=reason,
        )

    async def get_order_for_viewer(
        self, order_id: uuid.UUID, viewer_user_id: uuid.UUID, *, is_staff: bool
    ) -> Order:
        """Ownership posture matches ``AddressService.get_own_address``:
        an order that exists but belongs to a different customer (and
        the viewer isn't staff) is a plain 404, never a 403.
        """
        order = await self._orders.get_by_id(order_id)
        if order is None or (not is_staff and order.customer_id != viewer_user_id):
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        return order

    # -- Scheduling --------------------------------------------------------

    async def schedule_pickup(
        self,
        order_id: uuid.UUID,
        requester_user_id: uuid.UUID,
        *,
        requester_is_staff: bool,
        pickup_slot_id: uuid.UUID,
        capacity_used: Decimal,
        changed_by_role: str | None = None,
    ) -> Order:
        """Books the slot's capacity (Phase 7) and moves the order to
        ``PICKUP_SCHEDULED`` in one call. Booking happens *before* the
        status transition: if the slot has no room,
        ``AvailabilityService.book_pickup_slot`` raises and the order's
        status is left untouched.
        """
        order = await self.get_order_for_viewer(
            order_id, requester_user_id, is_staff=requester_is_staff
        )
        reservation = await self._availability.book_pickup_slot(
            pickup_slot_id, order.customer_id, capacity_used
        )
        order.pickup_slot_id = pickup_slot_id
        order.pickup_reservation_id = reservation.id
        await self._orders.update(order)

        return await self._order_state.transition(
            order_id,
            OrderStatus.PICKUP_SCHEDULED,
            requester_user_id=requester_user_id,
            requester_is_staff=requester_is_staff,
            changed_by_role=changed_by_role,
            reason="Pickup slot scheduled",
        )

    # -- Inspection / itemization -----------------------------------------

    async def itemize_order_item(
        self,
        order_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        verified_material_id: uuid.UUID | None = None,
        verified_quantity: int | None = None,
        verified_weight_kg: Decimal | None = None,
    ) -> OrderItem:
        """Records the facility's verified material/quantity/weight for
        one item. Deliberately does not touch the order's own
        ``status`` -- moving to ``ITEMIZED`` once every item has been
        verified is a separate, explicit ``OrderStateService.transition``
        call, per the spec's "do not mix order item state with order
        state."
        """
        item = await self._order_items.get_by_id(item_id)
        if item is None or item.order_id != order_id:
            raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
        if verified_material_id is not None:
            if await self._materials.get_by_id(verified_material_id) is None:
                raise NotFoundException(error_messages.NOT_FOUND, error_codes.NOT_FOUND)
            item.verified_material_id = verified_material_id
        if verified_quantity is not None:
            item.verified_quantity = verified_quantity
        if verified_weight_kg is not None:
            item.verified_weight_kg = verified_weight_kg
        return await self._order_items.update(item)

    async def finalize_pricing(
        self,
        order_id: uuid.UUID,
        requester_user_id: uuid.UUID,
        *,
        requester_is_staff: bool,
        rush_charge: Decimal = ZERO,
        delivery_charge: Decimal = ZERO,
        tax: Decimal = ZERO,
        discount: Decimal = ZERO,
        changed_by_role: str | None = None,
    ) -> Order:
        """Recomputes each item's price using its *verified* material/
        quantity/weight (falling back to the declared value for any
        item never itemized) and moves the order to ``PRICE_FINALIZED``
        in one call. Rush/delivery/tax/discount are supplied here, not
        stored on the order -- the same "caller-supplied input, not
        stored policy" design as Phase 6's ``calculate_price``, since
        they may legitimately differ from what was estimated.
        """
        order = await self.get_order_for_viewer(
            order_id, requester_user_id, is_staff=requester_is_staff
        )
        items = await self._order_items.list_for_order(order_id)

        items_subtotal = ZERO
        for item in items:
            material_id = item.verified_material_id or item.declared_material_id
            quantity = (
                item.verified_quantity
                if item.verified_quantity is not None
                else item.declared_quantity
            )
            weight_kg = (
                item.verified_weight_kg
                if item.verified_weight_kg is not None
                else item.declared_weight_kg
            )
            breakdown = await self._pricing.calculate_price(
                service_id=item.service_id,
                material_id=material_id,
                quantity=quantity,
                weight_kg=weight_kg,
            )
            item.final_pricing_rule_id = breakdown.pricing_rule_id
            item.final_material_pricing_rule_id = breakdown.material_pricing_rule_id
            item.final_line_total = breakdown.subtotal
            await self._order_items.update(item)
            items_subtotal += breakdown.subtotal

        order.final_total = items_subtotal + rush_charge + delivery_charge + tax - discount
        await self._orders.update(order)

        return await self._order_state.transition(
            order_id,
            OrderStatus.PRICE_FINALIZED,
            requester_user_id=requester_user_id,
            requester_is_staff=requester_is_staff,
            changed_by_role=changed_by_role,
            reason="Price finalized",
        )

    # -- Cancellation ------------------------------------------------------

    async def cancel_order(
        self,
        order_id: uuid.UUID,
        requester_user_id: uuid.UUID,
        *,
        requester_is_staff: bool,
        changed_by_role: str | None = None,
        reason: str | None = None,
    ) -> Order:
        return await self._order_state.transition(
            order_id,
            OrderStatus.CANCELLED,
            requester_user_id=requester_user_id,
            requester_is_staff=requester_is_staff,
            changed_by_role=changed_by_role,
            reason=reason or "Order cancelled",
        )
