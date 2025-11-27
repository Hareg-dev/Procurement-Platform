from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import BidCreate, BidResponse, BidUpdate, BidListResponse
from app.models.orm import Bid, RFQ, RFQStatus, User, UserRole
from app.repositories.bid_repo import bid_repository
from app.repositories.rfq_repo import rfq_repository


class BidService:
    """Service class for Bid operations."""
    
    def __init__(self):
        self.bid_repo = bid_repository
        self.rfq_repo = rfq_repository
    
    async def create_bid(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int,
        bid_in: BidCreate, 
        current_user: User
    ) -> BidResponse:
        """
        Create a new bid on an RFQ.
        
        Args:
            db: Database session
            rfq_id: RFQ ID to bid on
            bid_in: Bid creation data
            current_user: Current authenticated user
            
        Returns:
            BidResponse: Created bid data
            
        Raises:
            HTTPException: If user is not a supplier, RFQ not found, or invalid bid
        """
        # Check if user can create bids (suppliers only)
        if current_user.role not in [UserRole.SUPPLIER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only suppliers can submit bids"
            )
        
        # Get and validate RFQ
        rfq = await self.rfq_repo.get(db, rfq_id)
        if not rfq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFQ not found"
            )
        
        # Check if RFQ is open for bidding
        if rfq.status != RFQStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFQ is not open for bidding"
            )
        
        # Check if deadline has passed
        if rfq.deadline <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFQ deadline has passed"
            )
        
        # Prevent suppliers from bidding on their own RFQs
        if rfq.buyer_company_id == current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot bid on your own RFQ"
            )
        
        # Check if company has already submitted a bid
        existing_bid = await self.bid_repo.check_existing_bid(
            db, rfq_id=rfq_id, company_id=current_user.company_id
        )
        if existing_bid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your company has already submitted a bid for this RFQ"
            )
        
        # Validate bid price against budget if specified
        if rfq.budget_max and bid_in.price > rfq.budget_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bid price exceeds maximum budget of {rfq.budget_max}"
            )
        
        # Create bid
        bid_data = bid_in.dict()
        bid = await self.bid_repo.create_bid(
            db,
            bid_data=bid_data,
            rfq_id=rfq_id,
            company_id=current_user.company_id,
            user_id=current_user.id
        )
        
        # Trigger AI summarization task asynchronously
        try:
            from app.tasks.ai_tasks import summarize_single_bid
            summarize_single_bid.delay(bid.id)
        except Exception as e:
            # Log error but don't fail the bid creation
            import logging
            logging.getLogger(__name__).warning(f"Failed to trigger AI summarization for bid {bid.id}: {str(e)}")
        
        return BidResponse.from_orm(bid)
    
    async def get_bid(
        self, db: AsyncSession, *, bid_id: int, current_user: User
    ) -> BidResponse:
        """
        Get bid by ID with access control.
        
        Args:
            db: Database session
            bid_id: Bid ID
            current_user: Current authenticated user
            
        Returns:
            BidResponse: Bid data
            
        Raises:
            HTTPException: If bid not found or access denied
        """
        bid = await self.bid_repo.get_with_details(db, bid_id)
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found"
            )
        
        # Check access permissions
        can_access = (
            current_user.role == UserRole.ADMIN or
            bid.supplier_company_id == current_user.company_id or
            bid.rfq.buyer_company_id == current_user.company_id
        )
        
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this bid"
            )
        
        return BidResponse.from_orm(bid)
    
    async def get_rfq_bids(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int, 
        current_user: User,
        skip: int = 0,
        limit: int = 100
    ) -> list[BidListResponse]:
        """
        Get all bids for an RFQ (buyer access only).
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            current_user: Current authenticated user
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[BidListResponse]: List of bids for the RFQ
            
        Raises:
            HTTPException: If RFQ not found or access denied
        """
        # Get and validate RFQ
        rfq = await self.rfq_repo.get(db, rfq_id)
        if not rfq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFQ not found"
            )
        
        # Check if user can view bids (RFQ owner or admin only)
        if (current_user.role != UserRole.ADMIN and 
            rfq.buyer_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view bids for this RFQ"
            )
        
        # Get bids
        bids = await self.bid_repo.get_by_rfq(
            db, rfq_id=rfq_id, skip=skip, limit=limit
        )
        return [BidListResponse.from_orm(bid) for bid in bids]
    
    async def get_my_bids(
        self, 
        db: AsyncSession, 
        *, 
        current_user: User,
        skip: int = 0,
        limit: int = 100
    ) -> list[BidResponse]:
        """
        Get bids submitted by current user's company.
        
        Args:
            db: Database session
            current_user: Current authenticated user
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[BidResponse]: List of user's company bids
        """
        bids = await self.bid_repo.get_by_company(
            db, company_id=current_user.company_id, skip=skip, limit=limit
        )
        return [BidResponse.from_orm(bid) for bid in bids]
    
    async def update_bid(
        self, 
        db: AsyncSession, 
        *, 
        bid_id: int, 
        bid_update: BidUpdate, 
        current_user: User
    ) -> BidResponse:
        """
        Update a bid (before RFQ deadline).
        
        Args:
            db: Database session
            bid_id: Bid ID
            bid_update: Bid update data
            current_user: Current authenticated user
            
        Returns:
            BidResponse: Updated bid data
            
        Raises:
            HTTPException: If bid not found, access denied, or invalid update
        """
        bid = await self.bid_repo.get_with_details(db, bid_id)
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found"
            )
        
        # Check if user can update this bid
        if (current_user.role != UserRole.ADMIN and 
            bid.supplier_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this bid"
            )
        
        # Check if RFQ is still open and not past deadline
        if bid.rfq.status != RFQStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update bid - RFQ is not open"
            )
        
        if bid.rfq.deadline <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update bid - RFQ deadline has passed"
            )
        
        # Validate updated price against budget if specified
        if (bid_update.price and 
            bid.rfq.budget_max and 
            bid_update.price > bid.rfq.budget_max):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bid price exceeds maximum budget of {bid.rfq.budget_max}"
            )
        
        # Update bid
        updated_bid = await self.bid_repo.update(
            db, db_obj=bid, obj_in=bid_update
        )
        
        # Load relationships for response
        updated_bid = await self.bid_repo.get_with_details(db, updated_bid.id)
        return BidResponse.from_orm(updated_bid)
    
    async def select_winning_bid(
        self, 
        db: AsyncSession, 
        *, 
        bid_id: int, 
        current_user: User
    ) -> BidResponse:
        """
        Select a bid as the winning bid for an RFQ.
        
        Args:
            db: Database session
            bid_id: Bid ID to select
            current_user: Current authenticated user
            
        Returns:
            BidResponse: Selected bid data
            
        Raises:
            HTTPException: If bid not found, access denied, or invalid selection
        """
        bid = await self.bid_repo.get_with_details(db, bid_id)
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found"
            )
        
        # Check if user can select bids (RFQ owner or admin only)
        if (current_user.role != UserRole.ADMIN and 
            bid.rfq.buyer_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to select bids for this RFQ"
            )
        
        # Check if RFQ allows bid selection
        if bid.rfq.status not in [RFQStatus.OPEN, RFQStatus.CLOSED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot select bid - RFQ is in invalid state"
            )
        
        # Select the bid
        selected_bid = await self.bid_repo.select_bid(db, bid_id=bid_id)
        
        # Update RFQ status to AWARDED
        await self.rfq_repo.update_status(
            db, rfq_id=bid.rfq_id, status=RFQStatus.AWARDED
        )
        
        # Load relationships for response
        selected_bid = await self.bid_repo.get_with_details(db, selected_bid.id)
        return BidResponse.from_orm(selected_bid)
    
    async def withdraw_bid(
        self, 
        db: AsyncSession, 
        *, 
        bid_id: int, 
        current_user: User
    ) -> dict:
        """
        Withdraw a bid (delete it).
        
        Args:
            db: Database session
            bid_id: Bid ID to withdraw
            current_user: Current authenticated user
            
        Returns:
            dict: Success message
            
        Raises:
            HTTPException: If bid not found, access denied, or cannot withdraw
        """
        bid = await self.bid_repo.get_with_details(db, bid_id)
        if not bid:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bid not found"
            )
        
        # Check if user can withdraw this bid
        if (current_user.role != UserRole.ADMIN and 
            bid.supplier_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to withdraw this bid"
            )
        
        # Check if bid can be withdrawn
        if bid.is_selected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot withdraw selected bid"
            )
        
        if bid.rfq.status != RFQStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot withdraw bid - RFQ is not open"
            )
        
        if bid.rfq.deadline <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot withdraw bid - RFQ deadline has passed"
            )
        
        # Delete the bid
        await self.bid_repo.delete(db, id=bid_id)
        
        return {"message": "Bid withdrawn successfully"}


# Create service instance
bid_service = BidService()
