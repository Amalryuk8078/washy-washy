"""Domain model package.

Every module defining a SQLAlchemy model belongs here and must import
``Base`` from this package. Alembic's env.py does ``from core.models
import *`` so that all model modules register on ``Base.metadata`` before
autogeneration runs — add new model modules' public names to ``__all__``
as they're introduced.
"""

from core.models.address import Address, AddressLabel
from core.models.base import Base
from core.models.customer_profile import CustomerProfile
from core.models.material import Material
from core.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from core.models.partner_capability import PartnerCapability
from core.models.partner_profile import PartnerProfile, PartnerStatus
from core.models.permission import Permission, PermissionScope
from core.models.role import Role, RoleName
from core.models.role_permission import RolePermission
from core.models.service import Service
from core.models.service_area import ServiceArea
from core.models.service_area_postal_code import ServiceAreaPostalCode
from core.models.service_material import ServiceMaterial
from core.models.user import User
from core.models.user_role import UserRole

__all__ = [
    "Base",
    "CreatedAtMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "Role",
    "RoleName",
    "Permission",
    "PermissionScope",
    "UserRole",
    "RolePermission",
    "CustomerProfile",
    "PartnerProfile",
    "PartnerStatus",
    "Address",
    "AddressLabel",
    "ServiceArea",
    "ServiceAreaPostalCode",
    "Service",
    "Material",
    "ServiceMaterial",
    "PartnerCapability",
]
