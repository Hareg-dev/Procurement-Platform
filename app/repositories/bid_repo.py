from typing import Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import BidCreate, BidUpdate
from app.models.orm import Bid, RFQ, Company, User
from app.repositories.base import BaseRepository


class BidRepository(BaseRepository[Bid, BidCreate, BidUpdate]):
    """Repository for Bid model with specific bid operations."""
    
    def __init__(self):
        super().__init__(Bid)
    
    async def get_with_details(self, db: AsyncSession, bid_id: int) -> Optional[Bid]:
        """
        Get bid with supplier company and RFQ information.
        
        Args:
            db: Database session
            bid_id: Bid ID
            
        Returns:
            Optional[Bid]: Bid instance with details if found, None otherwise
        """
        result = await db.execute(
            select(Bid)
            .options(
                selectinload(Bid.supplier_company),
                selectinload(Bid.submitted_by),
                selectinload(Bid.rfq).selectinload(RFQ.buyer_company)
            )
            .where(Bid.id == bid_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_rfq(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Bid]:
        """
        Get all bids for a specific RFQ.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[Bid]: List of bids for the RFQ
        """
        result = await db.execute(
            select(Bid)
            .options(
                selectinload(Bid.supplier_company),
                selectinload(Bid.submitted_by)
            )
            .where(Bid.rfq_id == rfq_id)
            .order_by(Bid.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_company(
        self, 
        db: AsyncSession, 
        *, 
        company_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Bid]:
        """
        Get bids by supplier company ID.
        
        Args:
            db: Database session
            company_id: Supplier company ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[Bid]: List of bids from the company
        """
        result = await db.execute(
            select(Bid)
            .options(
                selectinload(Bid.rfq).selectinload(RFQ.buyer_company),
                selectinload(Bid.supplier_company)
            )
            .where(Bid.supplier_company_id == company_id)
            .order_by(Bid.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_bid(
        self, 
        db: AsyncSession, 
        *, 
        bid_data: dict, 
        rfq_id: int,
        company_id: int, 
        user_id: int
    ) -> Bid:
        """
        Create a new bid with RFQ, company, and user information.
        
        Args:
            db: Database session
            bid_data: Bid creation data
            rfq_id: RFQ ID
            company_id: Supplier company ID
            user_id: Submitting user ID
            
        Returns:
            Bid: Created bid instance
        """
        bid_data.update({
            "rfq_id": rfq_id,
            "supplier_company_id": company_id,
            "submitted_by_user_id": user_id,
            "is_selected": False
        })
        
        db_bid = Bid(**bid_data)
        db.add(db_bid)
        await db.commit()
        await db.refresh(db_bid)
        
        # Load relationships
        result = await db.execute(
            select(Bid)
            .options(
                selectinload(Bid.supplier_company),
                selectinload(Bid.submitted_by),
                selectinload(Bid.rfq)
            )
            .where(Bid.id == db_bid.id)
        )
        return result.scalar_one()
    
    async def check_existing_bid(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int, 
        company_id: int
    ) -> Optional[Bid]:
        """
        Check if a company has already submitted a bid for an RFQ.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            company_id: Supplier company ID
            
        Returns:
            Optional[Bid]: Existing bid if found, None otherwise
        """
        result = await db.execute(
            select(Bid)
            .where(
                and_(
                    Bid.rfq_id == rfq_id,
                    Bid.supplier_company_id == company_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def select_bid(
        self, 
        db: AsyncSession, 
        *, 
        bid_id: int
    ) -> Optional[Bid]:
        """
        Select a bid as the winning bid and unselect others for the same RFQ.
        
        Args:
            db: Database session
            bid_id: Bid ID to select
            
        Returns:
            Optional[Bid]: Selected bid if found, None otherwise
        """
        # Get the bid to select
        selected_bid = await self.get(db, bid_id)
        if not selected_bid:
            return None
        
        # Unselect all other bids for the same RFQ
        await db.execute(
            update(Bid)
            .where(
                and_(
                    Bid.rfq_id == selected_bid.rfq_id,
                    Bid.id != bid_id
                )
            )
            .values(is_selected=False)
        )
        
        # Select the chosen bid
        selected_bid.is_selected = True
        db.add(selected_bid)
        await db.commit()
        await db.refresh(selected_bid)
        
        return selected_bid
    
    async def get_selected_bid(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int
    ) -> Optional[Bid]:
        """
        Get the selected (winning) bid for an RFQ.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            
        Returns:
            Optional[Bid]: Selected bid if found, None otherwise
        """
        result = await db.execute(
            select(Bid)
            .options(
                selectinload(Bid.supplier_company),
                selectinload(Bid.submitted_by)
            )
            .where(
                and_(
                    Bid.rfq_id == rfq_id,
                    Bid.is_selected == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_lowest_bids(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int, 
        limit: int = 5
    ) -> list[Bid]:
        """
        Get the lowest priced bids for an RFQ.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            limit: Maximum number of bids to return
            
        Returns:
            list[Bid]: List of lowest priced bids
        """
        result = await db.execute(
            select(Bid)
            .options(selectinload(Bid.supplier_company))
            .where(Bid.rfq_id == rfq_id)
            .order_by(Bid.price.asc())
            .limit(limit)
        )
        return result.scalars().all()


# Create repository instance
bid_repository = BidRepository()
