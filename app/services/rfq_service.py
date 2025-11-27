from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import RFQCreate, RFQResponse, RFQUpdate, RFQListResponse
from app.models.orm import RFQ, RFQStatus, User, UserRole
from app.repositories.rfq_repo import rfq_repository


class RFQService:
    """Service class for RFQ operations."""
    
    def __init__(self):
        self.rfq_repo = rfq_repository
    
    async def create_rfq(
        self, db: AsyncSession, *, rfq_in: RFQCreate, current_user: User
    ) -> RFQResponse:
        """
        Create a new RFQ.
        
        Args:
            db: Database session
            rfq_in: RFQ creation data
            current_user: Current authenticated user
            
        Returns:
            RFQResponse: Created RFQ data
            
        Raises:
            HTTPException: If user is not a buyer or admin
        """
        # Check if user can create RFQs (buyers and admins only)
        if current_user.role not in [UserRole.BUYER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only buyers can create RFQs"
            )
        
        # Validate deadline is in the future
        now = datetime.utcnow()
        if rfq_in.deadline <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFQ deadline must be in the future"
            )
        
        # Validate budget range if provided
        if (rfq_in.budget_min is not None and 
            rfq_in.budget_max is not None and 
            rfq_in.budget_min > rfq_in.budget_max):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum budget cannot be greater than maximum budget"
            )
        
        # Create RFQ
        rfq_data = rfq_in.dict()
        rfq = await self.rfq_repo.create_rfq(
            db, 
            rfq_data=rfq_data, 
            company_id=current_user.company_id, 
            user_id=current_user.id
        )
        
        # Trigger AI summarization task asynchronously
        try:
            from app.tasks.ai_tasks import summarize_rfq_and_bids
            summarize_rfq_and_bids.delay(rfq.id)
        except Exception as e:
            # Log error but don't fail the RFQ creation
            import logging
            logging.getLogger(__name__).warning(f"Failed to trigger AI summarization for RFQ {rfq.id}: {str(e)}")
        
        # Create response dict manually to avoid async property issues
        rfq_dict = {
            "id": rfq.id,
            "title": rfq.title,
            "description": rfq.description,
            "deadline": rfq.deadline,
            "status": rfq.status,
            "budget_min": rfq.budget_min,
            "budget_max": rfq.budget_max,
            "requirements": rfq.requirements,
            "created_at": rfq.created_at,
            "updated_at": rfq.updated_at,
            "buyer_company_id": rfq.buyer_company_id,
            "created_by_user_id": rfq.created_by_user_id,
            "buyer_company": rfq.buyer_company,
            "bid_count": 0,  # New RFQ has no bids
            "is_open": rfq.status == RFQStatus.OPEN and rfq.deadline > datetime.utcnow(),
            "is_expired": rfq.deadline <= datetime.utcnow()
        }
        return RFQResponse.model_validate(rfq_dict)
    
    async def get_rfq(
        self, db: AsyncSession, *, rfq_id: int, current_user: User
    ) -> RFQResponse:
        """
        Get RFQ by ID with access control.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            current_user: Current authenticated user
            
        Returns:
            RFQResponse: RFQ data
            
        Raises:
            HTTPException: If RFQ not found or access denied
        """
        rfq = await self.rfq_repo.get_with_details(db, rfq_id)
        if not rfq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFQ not found"
            )
        
        # Check access permissions
        can_access = (
            current_user.role == UserRole.ADMIN or
            rfq.buyer_company_id == current_user.company_id or
            (rfq.status == RFQStatus.OPEN and current_user.role == UserRole.SUPPLIER)
        )
        
        if not can_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this RFQ"
            )
        
        return RFQResponse.model_validate(rfq)
    
    async def get_my_rfqs(
        self, 
        db: AsyncSession, 
        *, 
        current_user: User, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[RFQListResponse]:
        """
        Get RFQs created by current user's company.
        
        Args:
            db: Database session
            current_user: Current authenticated user
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[RFQListResponse]: List of user's RFQs
        """
        rfqs = await self.rfq_repo.get_by_company(
            db, company_id=current_user.company_id, skip=skip, limit=limit
        )
        return [RFQListResponse.model_validate(rfq) for rfq in rfqs]
    
    async def get_open_rfqs(
        self, 
        db: AsyncSession, 
        *, 
        current_user: User, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[RFQListResponse]:
        """
        Get open RFQs that suppliers can bid on.
        
        Args:
            db: Database session
            current_user: Current authenticated user
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[RFQListResponse]: List of open RFQs
            
        Raises:
            HTTPException: If user is not a supplier or admin
        """
        if current_user.role not in [UserRole.SUPPLIER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only suppliers can view open RFQs"
            )
        
        # Exclude RFQs from the supplier's own company
        exclude_company_id = (
            current_user.company_id if current_user.role == UserRole.SUPPLIER else None
        )
        
        rfqs = await self.rfq_repo.get_open_rfqs(
            db, 
            exclude_company_id=exclude_company_id, 
            skip=skip, 
            limit=limit
        )
        return [RFQListResponse.model_validate(rfq) for rfq in rfqs]
    
    async def update_rfq(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int, 
        rfq_update: RFQUpdate, 
        current_user: User
    ) -> RFQResponse:
        """
        Update an RFQ.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            rfq_update: RFQ update data
            current_user: Current authenticated user
            
        Returns:
            RFQResponse: Updated RFQ data
            
        Raises:
            HTTPException: If RFQ not found, access denied, or invalid update
        """
        rfq = await self.rfq_repo.get(db, rfq_id)
        if not rfq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFQ not found"
            )
        
        # Check if user can update this RFQ
        if (current_user.role != UserRole.ADMIN and 
            rfq.buyer_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this RFQ"
            )
        
        # Prevent updates if RFQ has bids (unless admin)
        if (rfq.bid_count > 0 and 
            current_user.role != UserRole.ADMIN and 
            rfq_update.status not in [RFQStatus.CLOSED, RFQStatus.CANCELLED]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify RFQ that already has bids"
            )
        
        # Validate deadline if being updated
        if rfq_update.deadline:
            if rfq_update.deadline <= datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="RFQ deadline must be in the future"
                )
        
        # Update RFQ
        updated_rfq = await self.rfq_repo.update(
            db, db_obj=rfq, obj_in=rfq_update
        )
        
        # Load relationships for response
        updated_rfq = await self.rfq_repo.get_with_details(db, updated_rfq.id)
        return RFQResponse.model_validate(updated_rfq)
    
    async def publish_rfq(
        self, db: AsyncSession, *, rfq_id: int, current_user: User
    ) -> RFQResponse:
        """
        Publish an RFQ (change status from DRAFT to OPEN).
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            current_user: Current authenticated user
            
        Returns:
            RFQResponse: Updated RFQ data
            
        Raises:
            HTTPException: If RFQ not found, access denied, or invalid state
        """
        rfq = await self.rfq_repo.get(db, rfq_id)
        if not rfq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFQ not found"
            )
        
        # Check permissions
        if (current_user.role != UserRole.ADMIN and 
            rfq.buyer_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to publish this RFQ"
            )
        
        # Check if RFQ can be published
        if rfq.status != RFQStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft RFQs can be published"
            )
        
        if rfq.deadline <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot publish RFQ with past deadline"
            )
        
        # Update status to OPEN
        updated_rfq = await self.rfq_repo.update_status(
            db, rfq_id=rfq_id, status=RFQStatus.OPEN
        )
        
        # Load relationships for response
        updated_rfq = await self.rfq_repo.get_with_details(db, updated_rfq.id)
        return RFQResponse.model_validate(updated_rfq)
    
    async def close_rfq(
        self, db: AsyncSession, *, rfq_id: int, current_user: User
    ) -> RFQResponse:
        """
        Close an RFQ (change status to CLOSED).
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            current_user: Current authenticated user
            
        Returns:
            RFQResponse: Updated RFQ data
            
        Raises:
            HTTPException: If RFQ not found, access denied, or invalid state
        """
        rfq = await self.rfq_repo.get(db, rfq_id)
        if not rfq:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFQ not found"
            )
        
        # Check permissions
        if (current_user.role != UserRole.ADMIN and 
            rfq.buyer_company_id != current_user.company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to close this RFQ"
            )
        
        # Check if RFQ can be closed
        if rfq.status not in [RFQStatus.OPEN, RFQStatus.DRAFT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RFQ cannot be closed in current state"
            )
        
        # Update status to CLOSED
        updated_rfq = await self.rfq_repo.update_status(
            db, rfq_id=rfq_id, status=RFQStatus.CLOSED
        )
        
        # Load relationships for response
        updated_rfq = await self.rfq_repo.get_with_details(db, updated_rfq.id)
        return RFQResponse.model_validate(updated_rfq)


# Create service instance
rfq_service = RFQService()