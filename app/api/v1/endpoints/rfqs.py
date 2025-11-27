from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user, require_buyer
from app.core.db import get_db
from app.models.domain import (
    MessageResponse,
    PaginationParams,
    RFQCreate,
    RFQListResponse,
    RFQResponse,
    RFQUpdate,
)
from app.models.orm import User
from app.services.rfq_service import rfq_service

router = APIRouter()


@router.post(
    "/",
    response_model=RFQResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new RFQ",
    description="Create a new Request for Quotation (buyers only)."
)
async def create_rfq(
    rfq_in: RFQCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_buyer)
) -> RFQResponse:
    """
    Create a new RFQ.
    
    - **title**: RFQ title
    - **description**: Detailed description of requirements
    - **deadline**: Deadline for bid submissions
    - **budget_min**: Optional minimum budget
    - **budget_max**: Optional maximum budget
    - **requirements**: Additional requirements or specifications
    
    Returns the created RFQ with buyer company information.
    """
    return await rfq_service.create_rfq(db, rfq_in=rfq_in, current_user=current_user)


@router.get(
    "/",
    response_model=list[RFQListResponse],
    summary="Get my RFQs",
    description="Get RFQs created by the current user's company (buyers only)."
)
async def get_my_rfqs(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_buyer)
) -> list[RFQListResponse]:
    """
    Get RFQs created by current user's company.
    
    Returns paginated list of RFQs with basic information.
    """
    skip = (pagination.page - 1) * pagination.size
    return await rfq_service.get_my_rfqs(
        db, current_user=current_user, skip=skip, limit=pagination.size
    )


@router.get(
    "/open",
    response_model=list[RFQListResponse],
    summary="Get open RFQs",
    description="Get all open RFQs available for bidding (suppliers only)."
)
async def get_open_rfqs(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[RFQListResponse]:
    """
    Get open RFQs that suppliers can bid on.
    
    Excludes RFQs from the supplier's own company.
    Returns paginated list of open RFQs.
    """
    skip = (pagination.page - 1) * pagination.size
    return await rfq_service.get_open_rfqs(
        db, current_user=current_user, skip=skip, limit=pagination.size
    )


@router.get(
    "/{rfq_id}",
    response_model=RFQResponse,
    summary="Get RFQ by ID",
    description="Get detailed information about a specific RFQ."
)
async def get_rfq(
    rfq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> RFQResponse:
    """
    Get RFQ by ID.
    
    Access control:
    - Buyers can view their own RFQs
    - Suppliers can view open RFQs
    - Admins can view all RFQs
    
    Returns detailed RFQ information including buyer company details.
    """
    return await rfq_service.get_rfq(db, rfq_id=rfq_id, current_user=current_user)


@router.put(
    "/{rfq_id}",
    response_model=RFQResponse,
    summary="Update RFQ",
    description="Update an existing RFQ (buyers only, before bids are submitted)."
)
async def update_rfq(
    rfq_id: int,
    rfq_update: RFQUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_buyer)
) -> RFQResponse:
    """
    Update an RFQ.
    
    Restrictions:
    - Only the RFQ owner can update it
    - Cannot modify RFQ with existing bids (except status changes)
    - Deadline must be in the future
    
    Returns updated RFQ information.
    """
    return await rfq_service.update_rfq(
        db, rfq_id=rfq_id, rfq_update=rfq_update, current_user=current_user
    )


@router.post(
    "/{rfq_id}/publish",
    response_model=RFQResponse,
    summary="Publish RFQ",
    description="Publish an RFQ to make it available for bidding (change status from DRAFT to OPEN)."
)
async def publish_rfq(
    rfq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_buyer)
) -> RFQResponse:
    """
    Publish an RFQ.
    
    Changes RFQ status from DRAFT to OPEN, making it visible to suppliers
    and available for bidding.
    
    Requirements:
    - RFQ must be in DRAFT status
    - Deadline must be in the future
    - Only RFQ owner can publish
    
    Returns updated RFQ information.
    """
    return await rfq_service.publish_rfq(db, rfq_id=rfq_id, current_user=current_user)


@router.post(
    "/{rfq_id}/close",
    response_model=RFQResponse,
    summary="Close RFQ",
    description="Close an RFQ to stop accepting new bids (change status to CLOSED)."
)
async def close_rfq(
    rfq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_buyer)
) -> RFQResponse:
    """
    Close an RFQ.
    
    Changes RFQ status to CLOSED, preventing new bids from being submitted.
    Existing bids remain accessible for evaluation.
    
    Requirements:
    - RFQ must be in OPEN or DRAFT status
    - Only RFQ owner can close
    
    Returns updated RFQ information.
    """
    return await rfq_service.close_rfq(db, rfq_id=rfq_id, current_user=current_user)