"""Partner-onboarding endpoints. Updating a partner's onboarding/vetting
status (Phase 4's own `PartnerStatus` field, first driven here) is
`ADMIN`-only.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.models.role import RoleName
from washy_washy.api.v1.controllers import partners as partners_controller
from washy_washy.dependencies.auth import get_current_user
from washy_washy.dependencies.rbac import require_role
from washy_washy.schemas.common import SuccessResponse
from washy_washy.schemas.facilities import UpdatePartnerStatusRequest

router = APIRouter(tags=["partners"], dependencies=[Depends(get_current_user)])
_admin_only = Depends(require_role(RoleName.ADMIN.value))


@router.patch(
    "/partners/{partner_profile_id}/status",
    response_model=SuccessResponse,
    dependencies=[_admin_only],
)
async def update_partner_status(
    partner_profile_id: uuid.UUID,
    request: UpdatePartnerStatusRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> SuccessResponse:
    profile = await partners_controller.update_partner_status(
        partner_profile_id, request, db_session
    )
    return SuccessResponse(message="Partner status updated", data=profile)
