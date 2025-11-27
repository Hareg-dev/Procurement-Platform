from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user, require_supplier
from app.core.db import get_db
from app.models.domain import (
    BidCreate,
    BidListResponse,
    BidResponse,
    BidUpdate,
    MessageResponse,
    NegotiationRequest,
    NegotiationResponse,
    PaginationParams,
)
from app.models.orm import User
from app.services.bid_service import bid_service

router = APIRouter()


@router.post(
    "/rfqs/{rfq_id}/bids",
    response_model=BidResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a bid on an RFQ",
    description="Submit a bid on a specific RFQ (suppliers only)."
)
async def create_bid(
    rfq_id: int,
    bid_in: BidCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier)
) -> BidResponse:
    """
    Submit a bid on an RFQ.
    
    - **price**: Bid price (must be positive)
    - **message**: Optional message or proposal details
    - **delivery_time**: Optional delivery time in days
    - **terms**: Optional terms and conditions
    
    Restrictions:
    - Only suppliers can submit bids
    - Cannot bid on own company's RFQs
    - RFQ must be open and not expired
    - One bid per company per RFQ
    
    Returns the created bid with supplier company information.
    """
    return await bid_service.create_bid(
        db, rfq_id=rfq_id, bid_in=bid_in, current_user=current_user
    )


@router.get(
    "/rfqs/{rfq_id}/bids",
    response_model=list[BidListResponse],
    summary="Get bids for an RFQ",
    description="Get all bids submitted for a specific RFQ (RFQ owner only)."
)
async def get_rfq_bids(
    rfq_id: int,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[BidListResponse]:
    """
    Get all bids for an RFQ.
    
    Access control:
    - Only the RFQ owner (buyer) can view all bids
    - Admins can view all bids
    
    Returns paginated list of bids with supplier information.
    """
    skip = (pagination.page - 1) * pagination.size
    return await bid_service.get_rfq_bids(
        db, rfq_id=rfq_id, current_user=current_user, skip=skip, limit=pagination.size
    )


@router.get(
    "/bids/my",
    response_model=list[BidResponse],
    summary="Get my bids",
    description="Get bids submitted by the current user's company."
)
async def get_my_bids(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[BidResponse]:
    """
    Get bids submitted by current user's company.
    
    Returns paginated list of bids with RFQ and supplier information.
    """
    skip = (pagination.page - 1) * pagination.size
    return await bid_service.get_my_bids(
        db, current_user=current_user, skip=skip, limit=pagination.size
    )


@router.get(
    "/bids/{bid_id}",
    response_model=BidResponse,
    summary="Get bid by ID",
    description="Get detailed information about a specific bid."
)
async def get_bid(
    bid_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> BidResponse:
    """
    Get bid by ID.
    
    Access control:
    - Bid submitter can view their own bid
    - RFQ owner can view bids on their RFQ
    - Admins can view all bids
    
    Returns detailed bid information.
    """
    return await bid_service.get_bid(db, bid_id=bid_id, current_user=current_user)


@router.put(
    "/bids/{bid_id}",
    response_model=BidResponse,
    summary="Update bid",
    description="Update an existing bid (before RFQ deadline)."
)
async def update_bid(
    bid_id: int,
    bid_update: BidUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> BidResponse:
    """
    Update a bid.
    
    Restrictions:
    - Only the bid submitter can update it
    - RFQ must still be open
    - RFQ deadline must not have passed
    - Price must be within budget limits if specified
    
    Returns updated bid information.
    """
    return await bid_service.update_bid(
        db, bid_id=bid_id, bid_update=bid_update, current_user=current_user
    )


@router.post(
    "/bids/{bid_id}/select",
    response_model=BidResponse,
    summary="Select winning bid",
    description="Select a bid as the winning bid for an RFQ (RFQ owner only)."
)
async def select_bid(
    bid_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> BidResponse:
    """
    Select a bid as the winning bid.
    
    Actions performed:
    - Marks the selected bid as winner
    - Unselects any previously selected bids for the same RFQ
    - Updates RFQ status to AWARDED
    
    Access control:
    - Only the RFQ owner can select bids
    - Admins can select bids
    
    Returns the selected bid information.
    """
    return await bid_service.select_winning_bid(
        db, bid_id=bid_id, current_user=current_user
    )


@router.delete(
    "/bids/{bid_id}",
    response_model=MessageResponse,
    summary="Withdraw bid",
    description="Withdraw (delete) a bid before RFQ deadline."
)
async def withdraw_bid(
    bid_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> MessageResponse:
    """
    Withdraw a bid.
    
    Restrictions:
    - Only the bid submitter can withdraw it
    - Cannot withdraw selected bids
    - RFQ must still be open
    - RFQ deadline must not have passed
    
    Returns success message.
    """
    result = await bid_service.withdraw_bid(
        db, bid_id=bid_id, current_user=current_user
    )
    return MessageResponse(message=result["message"])


@router.post(
    "/bids/{bid_id}/negotiate",
    response_model=NegotiationResponse,
    summary="Generate AI negotiation message",
    description="Generate an AI-powered negotiation message based on bid context and user goals."
)
async def generate_negotiation_message(
    bid_id: int,
    request: NegotiationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> NegotiationResponse:
    """
    Generate an AI-powered negotiation message for a specific bid.
    
    This endpoint uses AI to craft professional negotiation messages based on:
    - Bid details (price, terms, delivery time)
    - RFQ context and requirements
    - User's negotiation goals
    
    Access control:
    - Bid submitter can negotiate their own bids
    - RFQ owner can negotiate with bid submitters
    - Admins can negotiate any bids
    
    Returns a professional negotiation message with context information.
    """
    from app.services.llm_service import llm_service
    
    # Get bid with full details
    bid = await bid_service.get_bid(db, bid_id=bid_id, current_user=current_user)
    
    # Build context from bid and RFQ information
    context = f"""
    BID DETAILS:
    - Bid Amount: ${bid.price}
    - Delivery Time: {bid.delivery_time or 'Not specified'} days
    - Supplier: {bid.supplier_company.name}
    - Bid Message: {bid.message or 'No message provided'}
    - Terms: {bid.terms or 'No specific terms'}
    
    RFQ CONTEXT:
    - RFQ Title: {bid.rfq.title}
    - Budget Range: ${bid.rfq.budget_min or 'Not specified'} - ${bid.rfq.budget_max or 'Not specified'}
    - Deadline: {bid.rfq.deadline}
    - Requirements: {bid.rfq.requirements or 'No specific requirements'}
    
    CURRENT STATUS:
    - Bid Status: {'Selected' if bid.is_selected else 'Under Review'}
    - RFQ Status: {bid.rfq.status.value}
    """
    
    try:
        # Generate negotiation message using AI
        negotiation_message = await llm_service.generate_negotiation_message(
            context=context.strip(),
            goal=request.goal
        )
        
        return NegotiationResponse(
            message=negotiation_message,
            context_used=f"Bid #{bid_id} for RFQ '{bid.rfq.title}'"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate negotiation message: {str(e)}"
        )