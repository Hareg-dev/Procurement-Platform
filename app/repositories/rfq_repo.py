from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import RFQCreate, RFQUpdate
from app.models.orm import RFQ, RFQStatus, Company, User
from app.repositories.base import BaseRepository


class RFQRepository(BaseRepository[RFQ, RFQCreate, RFQUpdate]):
    """Repository for RFQ model with specific RFQ operations."""
    
    def __init__(self):
        super().__init__(RFQ)
    
    async def get_with_details(self, db: AsyncSession, rfq_id: int) -> Optional[RFQ]:
        """
        Get RFQ with buyer company and bids information.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            
        Returns:
            Optional[RFQ]: RFQ instance with details if found, None otherwise
        """
        result = await db.execute(
            select(RFQ)
            .options(
                selectinload(RFQ.buyer_company),
                selectinload(RFQ.created_by),
                selectinload(RFQ.bids).selectinload(RFQ.bids.property.mapper.class_.supplier_company)
            )
            .where(RFQ.id == rfq_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_company(
        self, 
        db: AsyncSession, 
        *, 
        company_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[RFQ]:
        """
        Get RFQs by buyer company ID.
        
        Args:
            db: Database session
            company_id: Buyer company ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[RFQ]: List of RFQs for the company
        """
        result = await db.execute(
            select(RFQ)
            .options(
                selectinload(RFQ.buyer_company),
                selectinload(RFQ.bids)
            )
            .where(RFQ.buyer_company_id == company_id)
            .order_by(RFQ.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_open_rfqs(
        self, 
        db: AsyncSession, 
        *, 
        exclude_company_id: Optional[int] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> list[RFQ]:
        """
        Get all open RFQs that suppliers can bid on.
        
        Args:
            db: Database session
            exclude_company_id: Company ID to exclude (supplier's own company)
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[RFQ]: List of open RFQs
        """
        query = (
            select(RFQ)
            .options(selectinload(RFQ.buyer_company))
            .where(
                and_(
                    RFQ.status == RFQStatus.OPEN,
                    RFQ.deadline > datetime.utcnow()
                )
            )
        )
        
        if exclude_company_id:
            query = query.where(RFQ.buyer_company_id != exclude_company_id)
        
        query = query.order_by(RFQ.deadline.asc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def create_rfq(
        self, 
        db: AsyncSession, 
        *, 
        rfq_data: dict, 
        company_id: int, 
        user_id: int
    ) -> RFQ:
        """
        Create a new RFQ with buyer company and user information.
        
        Args:
            db: Database session
            rfq_data: RFQ creation data
            company_id: Buyer company ID
            user_id: Creating user ID
            
        Returns:
            RFQ: Created RFQ instance
        """
        rfq_data.update({
            "buyer_company_id": company_id,
            "created_by_user_id": user_id,
            "status": RFQStatus.DRAFT
        })
        
        db_rfq = RFQ(**rfq_data)
        db.add(db_rfq)
        await db.commit()
        await db.refresh(db_rfq)
        
        # Load relationships
        result = await db.execute(
            select(RFQ)
            .options(
                selectinload(RFQ.buyer_company),
                selectinload(RFQ.created_by)
            )
            .where(RFQ.id == db_rfq.id)
        )
        return result.scalar_one()
    
    async def update_status(
        self, 
        db: AsyncSession, 
        *, 
        rfq_id: int, 
        status: RFQStatus
    ) -> Optional[RFQ]:
        """
        Update RFQ status.
        
        Args:
            db: Database session
            rfq_id: RFQ ID
            status: New status
            
        Returns:
            Optional[RFQ]: Updated RFQ if found, None otherwise
        """
        db_rfq = await self.get(db, rfq_id)
        if db_rfq:
            db_rfq.status = status
            db.add(db_rfq)
            await db.commit()
            await db.refresh(db_rfq)
        return db_rfq
    
    async def get_expired_rfqs(self, db: AsyncSession) -> list[RFQ]:
        """
        Get all RFQs that have passed their deadline but are still open.
        
        Args:
            db: Database session
            
        Returns:
            list[RFQ]: List of expired RFQs
        """
        result = await db.execute(
            select(RFQ)
            .where(
                and_(
                    RFQ.status == RFQStatus.OPEN,
                    RFQ.deadline <= datetime.utcnow()
                )
            )
        )
        return result.scalars().all()
    
    async def search_rfqs(
        self, 
        db: AsyncSession, 
        *, 
        query: str,
        company_id: Optional[int] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> list[RFQ]:
        """
        Search RFQs by title or description.
        
        Args:
            db: Database session
            query: Search query
            company_id: Optional company ID filter
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[RFQ]: List of matching RFQs
        """
        search_filter = or_(
            RFQ.title.ilike(f"%{query}%"),
            RFQ.description.ilike(f"%{query}%")
        )
        
        db_query = (
            select(RFQ)
            .options(selectinload(RFQ.buyer_company))
            .where(search_filter)
        )
        
        if company_id:
            db_query = db_query.where(RFQ.buyer_company_id == company_id)
        
        db_query = db_query.order_by(RFQ.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(db_query)
        return result.scalars().all()


# Create repository instance
rfq_repository = RFQRepository()