from fastapi import APIRouter

from washy_washy.api.v1.routes import (
    addresses,
    auth,
    customers,
    health,
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

__all__ = ["api_v1_router"]
