from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user, require_admin
from app.core.db import get_db
from app.models.domain import UserResponse, UserDashboardResponse, PaginationParams
from app.models.orm import User
from app.repositories.user_repo import user_repository

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Get the current authenticated user's detailed profile information."
)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current user's profile information.
    
    Requires valid authentication token in Authorization header.
    Returns detailed user data including company information.
    """
    return UserResponse.from_orm(current_user)


@router.get(
    "/me/dashboard",
    response_model=UserDashboardResponse,
    summary="Get user dashboard data",
    description="Get personalized dashboard data for the current user including company name."
)
async def get_user_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> UserDashboardResponse:
    """
    Get user dashboard data for personalized welcome message.
    
    Returns user information including:
    - first_name, last_name, email, role
    - title, bio (new profile fields)
    - company_name for personalized experience
    
    This endpoint is designed for frontend dashboard/welcome screens.
    """
    # Ensure user has company relationship loaded
    user_with_company = await user_repository.get_with_company(db, current_user.id)
    if not user_with_company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create dashboard response with company name
    dashboard_data = {
        "first_name": user_with_company.first_name,
        "last_name": user_with_company.last_name,
        "email": user_with_company.email,
        "role": user_with_company.role,
        "title": user_with_company.title,
        "bio": user_with_company.bio,
        "company_name": user_with_company.company.name
    }
    
    return UserDashboardResponse(**dashboard_data)


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List users",
    description="Get a list of all users (admin only)."
)
async def list_users(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> list[UserResponse]:
    """
    List all users (admin only).
    
    Requires admin role and valid authentication token.
    Returns paginated list of users.
    """
    skip = (pagination.page - 1) * pagination.size
    users = await user_repository.get_active_users(
        db, skip=skip, limit=pagination.size
    )
    return [UserResponse.from_orm(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Get a specific user by their ID (admin only)."
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> UserResponse:
    """
    Get user by ID (admin only).
    
    Requires admin role and valid authentication token.
    Returns user data if found.
    """
    user = await user_repository.get_with_company(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.from_orm(user)