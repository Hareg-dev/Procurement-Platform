from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import UserCreate, UserUpdate
from app.models.orm import User, Company
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """Repository for User model with specific user operations."""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """
        Get user by email address.
        
        Args:
            db: Database session
            email: User email address
            
        Returns:
            Optional[User]: User instance if found, None otherwise
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_with_company(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """
        Get user with company information.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Optional[User]: User instance with company if found, None otherwise
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create_with_company(
        self, 
        db: AsyncSession, 
        *, 
        user_data: dict, 
        company_data: dict
    ) -> User:
        """
        Create a new user with associated company.
        
        Args:
            db: Database session
            user_data: User creation data
            company_data: Company creation data
            
        Returns:
            User: Created user instance with company
        """
        # Create company first
        db_company = Company(**company_data)
        db.add(db_company)
        await db.flush()  # Flush to get company ID
        
        # Create user with company ID
        user_data["company_id"] = db_company.id
        db_user = User(**user_data)
        db.add(db_user)
        
        await db.commit()
        await db.refresh(db_user)
        await db.refresh(db_company)
        
        # Load the relationship
        result = await db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.id == db_user.id)
        )
        return result.scalar_one()
    
    async def update_last_login(self, db: AsyncSession, *, user_id: int) -> Optional[User]:
        """
        Update user's last login timestamp.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Optional[User]: Updated user instance if found, None otherwise
        """
        db_user = await self.get(db, user_id)
        if db_user:
            db_user.last_login = datetime.utcnow()
            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)
        return db_user
    
    async def get_active_users(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[User]:
        """
        Get all active users.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[User]: List of active users
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.is_active == True)
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
    ) -> list[User]:
        """
        Get users by company ID.
        
        Args:
            db: Database session
            company_id: Company ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            list[User]: List of users in the company
        """
        result = await db.execute(
            select(User)
            .options(selectinload(User.company))
            .where(User.company_id == company_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def email_exists(self, db: AsyncSession, *, email: str) -> bool:
        """
        Check if email already exists in the system.
        
        Args:
            db: Database session
            email: Email address to check
            
        Returns:
            bool: True if email exists, False otherwise
        """
        result = await db.execute(
            select(User.id).where(User.email == email)
        )
        return result.scalar_one_or_none() is not None


# Create repository instance
user_repository = UserRepository()