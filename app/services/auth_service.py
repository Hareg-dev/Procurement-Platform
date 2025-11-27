from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_token_with_user_data,
    get_password_hash,
    verify_password,
)
from app.models.domain import LoginResponse, Token, UserCreate, UserResponse
from app.models.orm import User
from app.repositories.user_repo import user_repository


class AuthService:
    """Service class for authentication operations."""
    
    def __init__(self):
        self.user_repo = user_repository
    
    async def authenticate_user(
        self, db: AsyncSession, *, email: str, password: str
    ) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Args:
            db: Database session
            email: User email address
            password: Plain text password
            
        Returns:
            Optional[User]: User instance if authentication successful, None otherwise
        """
        user = await self.user_repo.get_by_email(db, email=email)
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    async def create_new_user(
        self, db: AsyncSession, *, user_in: UserCreate
    ) -> User:
        """
        Create a new user and their company.
        
        Args:
            db: Database session
            user_in: User creation data
            
        Returns:
            User: Created user instance
            
        Raises:
            HTTPException: If email already exists
        """
        # Check if email already exists
        if await self.user_repo.email_exists(db, email=user_in.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Prepare user data
        user_data = {
            "email": user_in.email,
            "hashed_password": get_password_hash(user_in.password),
            "first_name": user_in.first_name,
            "last_name": user_in.last_name,
            "role": user_in.role,
            "is_active": True,
            "is_verified": False,
        }
        
        # Prepare company data
        company_data = user_in.company.dict()
        
        # Create user with company
        user = await self.user_repo.create_with_company(
            db, user_data=user_data, company_data=company_data
        )
        
        return user
    
    async def login_user(
        self, db: AsyncSession, *, email: str, password: str
    ) -> LoginResponse:
        """
        Login a user and return user data with access token.
        
        Args:
            db: Database session
            email: User email address
            password: Plain text password
            
        Returns:
            LoginResponse: User data and access token
            
        Raises:
            HTTPException: If authentication fails
        """
        user = await self.authenticate_user(db, email=email, password=password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last login
        await self.user_repo.update_last_login(db, user_id=user.id)
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_token_with_user_data(
            user_id=user.id,
            email=user.email,
            expires_delta=access_token_expires
        )
        
        # Create token response
        token = Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60  # Convert to seconds
        )
        
        # Create user response
        user_response = UserResponse.model_validate(user)
        
        return LoginResponse(user=user_response, token=token)
    
    async def register_user(
        self, db: AsyncSession, *, user_in: UserCreate
    ) -> LoginResponse:
        """
        Register a new user and return user data with access token.
        
        Args:
            db: Database session
            user_in: User creation data
            
        Returns:
            LoginResponse: User data and access token
        """
        # Create new user
        user = await self.create_new_user(db, user_in=user_in)
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_token_with_user_data(
            user_id=user.id,
            email=user.email,
            expires_delta=access_token_expires
        )
        
        # Create token response
        token = Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60  # Convert to seconds
        )
        
        # Create user response
        user_response = UserResponse.model_validate(user)
        
        return LoginResponse(user=user_response, token=token)
    
    async def get_current_user_by_token(
        self, db: AsyncSession, *, token: str
    ) -> Optional[User]:
        """
        Get current user from JWT token.
        
        Args:
            db: Database session
            token: JWT access token
            
        Returns:
            Optional[User]: User instance if token is valid, None otherwise
        """
        from app.core.security import decode_token
        
        payload = decode_token(token)
        if payload is None:
            return None
        
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return None
        
        user = await self.user_repo.get_with_company(db, user_id)
        if user is None or not user.is_active:
            return None
        
        return user
    
    async def refresh_token(
        self, db: AsyncSession, *, current_user: User
    ) -> Token:
        """
        Refresh access token for current user.
        
        Args:
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Token: New access token
        """
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_token_with_user_data(
            user_id=current_user.id,
            email=current_user.email,
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60  # Convert to seconds
        )


# Create service instance
auth_service = AuthService()