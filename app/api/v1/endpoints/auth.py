from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user
from app.core.db import get_db
from app.models.domain import (
    LoginResponse,
    MessageResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.models.orm import User
from app.services.auth_service import auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user and their company. Returns user data and access token."
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """
    Register a new user and their company.
    
    - **email**: User email address (must be unique)
    - **password**: User password (minimum 8 characters)
    - **first_name**: User first name
    - **last_name**: User last name
    - **role**: User role (buyer, supplier, admin)
    - **company**: Company information
    
    Returns user data and JWT access token.
    """
    try:
        return await auth_service.register_user(db, user_in=user_in)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Registration error: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login user",
    description="Authenticate user with email and password. Returns user data and access token."
)
async def login(
    user_credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """
    Login user with email and password.
    
    - **email**: User email address
    - **password**: User password
    
    Returns user data and JWT access token.
    """
    try:
        return await auth_service.login_user(
            db,
            email=user_credentials.email,
            password=user_credentials.password
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Refresh the access token for the current authenticated user."
)
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Refresh access token for the current user.
    
    Requires valid authentication token in Authorization header.
    Returns a new JWT access token.
    """
    try:
        return await auth_service.refresh_token(db, current_user=current_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the current authenticated user's information."
)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Get current authenticated user information.
    
    Requires valid authentication token in Authorization header.
    Returns user data including company information.
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout user",
    description="Logout the current user (client-side token invalidation)."
)
async def logout(
    current_user: User = Depends(get_current_active_user)
) -> MessageResponse:
    """
    Logout user.
    
    Note: This endpoint is mainly for consistency. JWT tokens are stateless,
    so actual logout should be handled on the client side by removing the token.
    
    In a production environment, you might want to implement token blacklisting
    or use shorter token expiration times with refresh tokens.
    """
    return MessageResponse(message="Successfully logged out")


@router.post(
    "/verify-token",
    response_model=UserResponse,
    summary="Verify token",
    description="Verify if the provided token is valid and return user information."
)
async def verify_token(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """
    Verify if the authentication token is valid.
    
    This endpoint can be used by client applications to verify
    if their stored token is still valid.
    
    Requires valid authentication token in Authorization header.
    Returns user data if token is valid.
    """
    return UserResponse.model_validate(current_user)