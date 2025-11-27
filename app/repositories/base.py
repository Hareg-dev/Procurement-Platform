from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.core.db import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize repository with model class.
        
        Args:
            model: SQLAlchemy model class
        """
        self.model = model
    
    async def get(self, db: AsyncSession, record_id: int) -> Optional[ModelType]:
        """
        Get a single record by ID.
        
        Args:
            db: Database session
            record_id: Record ID
            
        Returns:
            Optional[ModelType]: Model instance if found, None otherwise
        """
        result = await db.execute(select(self.model).where(self.model.id == record_id))
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """
        Get multiple records with pagination and filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria
            
        Returns:
            List[ModelType]: List of model instances
        """
        query = select(self.model)
        
        # Apply filters with validation
        allowed_fields = {c.name for c in self.model.__table__.columns}
        for field, value in filters.items():
            if field in allowed_fields and value is not None:
                query = query.where(getattr(self.model, field) == value)
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def count(self, db: AsyncSession, **filters) -> int:
        """
        Count records with optional filtering.
        
        Args:
            db: Database session
            **filters: Filter criteria
            
        Returns:
            int: Number of records
        """
        query = select(func.count())
        
        # Apply filters with validation
        allowed_fields = {c.name for c in self.model.__table__.columns}
        for field, value in filters.items():
            if field in allowed_fields and value is not None:
                query = query.where(getattr(self.model, field) == value)
        
        result = await db.execute(query)
        return result.scalar()
    
    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record.
        
        Args:
            db: Database session
            obj_in: Create schema instance
            
        Returns:
            ModelType: Created model instance
        """
        try:
            obj_in_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
            db_obj = self.model(**obj_in_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError:
            await db.rollback()
            raise
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update an existing record.
        
        Args:
            db: Database session
            db_obj: Existing model instance
            obj_in: Update schema instance or dict
            
        Returns:
            ModelType: Updated model instance
        """
        try:
            if isinstance(obj_in, dict):
                update_data = obj_in
            else:
                update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in
            
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError:
            await db.rollback()
            raise
    
    async def delete(self, db: AsyncSession, *, record_id: int) -> Optional[ModelType]:
        """
        Delete a record by ID.
        
        Args:
            db: Database session
            record_id: Record ID
            
        Returns:
            Optional[ModelType]: Deleted model instance if found, None otherwise
        """
        try:
            result = await db.execute(
                delete(self.model).where(self.model.id == record_id).returning(self.model)
            )
            deleted_obj = result.scalar_one_or_none()
            if deleted_obj:
                await db.commit()
            return deleted_obj
        except SQLAlchemyError:
            await db.rollback()
            raise
    
    async def exists(self, db: AsyncSession, record_id: int) -> bool:
        """
        Check if a record exists by ID.
        
        Args:
            db: Database session
            record_id: Record ID
            
        Returns:
            bool: True if record exists, False otherwise
        """
        result = await db.execute(
            select(func.count()).where(self.model.id == record_id)
        )
        return result.scalar() > 0