from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.models.domain import CompanyPublicResponse, PaginationParams
from app.models.orm import Company, UserRole

router = APIRouter()


@router.get(
    "/companies/{company_id}",
    response_model=CompanyPublicResponse,
    summary="Get public company profile",
    description="Get public information about a specific company by ID."
)
async def get_public_company(
    company_id: int,
    db: AsyncSession = Depends(get_db)
) -> CompanyPublicResponse:
    """
    Get public company information by ID.
    
    Returns public company profile if the company has is_public=True.
    Returns 404 if company not found or not public.
    """
    # Query for public company
    result = await db.execute(
        select(Company)
        .where(
            and_(
                Company.id == company_id,
                Company.is_public == True,
                Company.is_active == True
            )
        )
    )
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found or not publicly available"
        )
    
    return CompanyPublicResponse.from_orm(company)


@router.get(
    "/suppliers",
    response_model=list[CompanyPublicResponse],
    summary="List public suppliers",
    description="Get a list of all public supplier companies with optional filtering."
)
async def list_public_suppliers(
    pagination: PaginationParams = Depends(),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: AsyncSession = Depends(get_db)
) -> list[CompanyPublicResponse]:
    """
    List all public supplier companies.
    
    Filters:
    - Only companies with is_public=True
    - Only companies with supplier users (role='supplier')
    - Only active companies
    - Optional location filter
    
    Returns paginated list of public supplier companies.
    """
    # Build the query
    query = (
        select(Company)
        .options(selectinload(Company.users))
        .where(
            and_(
                Company.is_public == True,
                Company.is_active == True
            )
        )
    )
    
    # Add location filter if provided
    if location:
        query = query.where(Company.location.ilike(f"%{location}%"))
    
    # Filter companies that have supplier users
    # We need to join with users table to check for supplier role
    from app.models.orm import User
    query = query.join(User).where(User.role == UserRole.SUPPLIER)
    
    # Add pagination
    skip = (pagination.page - 1) * pagination.size
    query = query.distinct().offset(skip).limit(pagination.size)
    
    # Execute query
    result = await db.execute(query)
    companies = result.scalars().all()
    
    return [CompanyPublicResponse.from_orm(company) for company in companies]


@router.get(
    "/companies",
    response_model=list[CompanyPublicResponse],
    summary="List all public companies",
    description="Get a list of all public companies (buyers and suppliers) with optional filtering."
)
async def list_public_companies(
    pagination: PaginationParams = Depends(),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: AsyncSession = Depends(get_db)
) -> list[CompanyPublicResponse]:
    """
    List all public companies (both buyers and suppliers).
    
    Filters:
    - Only companies with is_public=True
    - Only active companies
    - Optional location filter
    
    Returns paginated list of public companies.
    """
    # Build the query
    query = (
        select(Company)
        .where(
            and_(
                Company.is_public == True,
                Company.is_active == True
            )
        )
    )
    
    # Add location filter if provided
    if location:
        query = query.where(Company.location.ilike(f"%{location}%"))
    
    # Add pagination and ordering
    skip = (pagination.page - 1) * pagination.size
    query = query.order_by(Company.created_at.desc()).offset(skip).limit(pagination.size)
    
    # Execute query
    result = await db.execute(query)
    companies = result.scalars().all()
    
    return [CompanyPublicResponse.from_orm(company) for company in companies]
