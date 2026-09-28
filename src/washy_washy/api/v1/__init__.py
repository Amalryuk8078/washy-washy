from fastapi import APIRouter

from washy_washy.api.v1.routes import (
    addresses,
    auth,
    availability,
    catalog,
    customers,
    facilities,
    health,
    orders,
    partners,
    payments,
    pricing,
    roles,
    service_areas,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(addresses.router)
api_v1_router.include_router(service_areas.router)
api_v1_router.include_router(roles.router)
api_v1_router.include_router(catalog.router)
api_v1_router.include_router(pricing.router)
api_v1_router.include_router(availability.router)
api_v1_router.include_router(orders.router)
api_v1_router.include_router(facilities.router)
api_v1_router.include_router(partners.router)
api_v1_router.include_router(payments.router)

__all__ = ["api_v1_router"]
