from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v2.deps import require_org_roles
from app.core.db import get_db
from app.models.procurement import AuditEvent, OrgRole
from app.models.procurement_schemas import AuditEventResponse

router = APIRouter(prefix="/audit-events", tags=["v2-audit"])

can_read_audit = require_org_roles(OrgRole.ORG_ADMIN)


@router.get(
    "",
    response_model=list[AuditEventResponse],
    summary="Read the organization's append-only audit trail",
)
async def list_audit_events(
    entity_type: Optional[str] = Query(None, max_length=50),
    entity_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    member=Depends(can_read_audit),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventResponse]:
    stmt = select(AuditEvent).where(
        AuditEvent.organization_id == member.organization_id
    )
    if entity_type is not None:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    stmt = (
        stmt.order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
