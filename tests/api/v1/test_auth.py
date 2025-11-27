"""
Comprehensive tests for authentication endpoints.

Tests cover:
- User registration with company creation
- User login and token generation
- Token refresh functionality
- Current user retrieval
- Token verification
- Logout functionality
- Error handling and validation
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, Company


class TestAuthRegistration:
    """Test user registration endpoint."""
    
    async def test_register_new_user_success(self, test_client: AsyncClient, test_data_factory):
        """Test successful user registration with company creation."""
        registration_data = test_data_factory.create_user_data(
            email="newbuyer@example.com",
            role="buyer"
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "user" in data
        assert "token" in data
        
        # Verify user data
        user_data = data["user"]
        assert user_data["email"] == "newbuyer@example.com"
        assert user_data["first_name"] == "New"
        assert user_data["last_name"] == "User"
        assert user_data["role"] == "buyer"
        assert user_data["is_active"] is True
        assert user_data["is_verified"] is False
        assert "company" in user_data
        
        # Verify company data
        company_data = user_data["company"]
        assert company_data["name"] == "New Test Company"
        
        # Verify token
        token_data = data["token"]
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert "expires_in" in token_data
    
    async def test_register_supplier_user(self, test_client: AsyncClient, test_data_factory):
        """Test supplier user registration."""
        registration_data = test_data_factory.create_user_data(
            email="newsupplier@example.com",
            role="supplier",
            company=test_data_factory.create_company_data(name="Supplier Company")
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["role"] == "supplier"
        assert data["user"]["company"]["name"] == "Supplier Company"
    
    async def test_register_duplicate_email(self, test_client: AsyncClient, test_buyer_user: User, test_data_factory):
        """Test registration with duplicate email fails."""
        registration_data = test_data_factory.create_user_data(
            email=test_buyer_user.email  # Use existing email
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    async def test_register_invalid_email(self, test_client: AsyncClient, test_data_factory):
        """Test registration with invalid email format."""
        registration_data = test_data_factory.create_user_data(
            email="invalid-email-format"
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 422  # Validation error
    
    async def test_register_short_password(self, test_client: AsyncClient, test_data_factory):
        """Test registration with short password fails."""
        registration_data = test_data_factory.create_user_data(
            password="123"  # Too short
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 422  # Validation error
    
    async def test_register_missing_company_data(self, test_client: AsyncClient):
        """Test registration without company data fails."""
        registration_data = {
            "email": "test@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "role": "buyer"
            # Missing company data
        }
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 422  # Validation error


class TestAuthLogin:
    """Test user login endpoint."""
    
    async def test_login_success(self, test_client: AsyncClient, test_buyer_user: User):
        """Test successful user login."""
        login_data = {
            "email": test_buyer_user.email,
            "password": "testpassword123"
        }
        
        response = await test_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "user" in data
        assert "token" in data
        
        # Verify user data
        user_data = data["user"]
        assert user_data["email"] == test_buyer_user.email
        assert user_data["role"] == "buyer"
        
        # Verify token
        token_data = data["token"]
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
    
    async def test_login_wrong_password(self, test_client: AsyncClient, test_buyer_user: User):
        """Test login with wrong password fails."""
        login_data = {
            "email": test_buyer_user.email,
            "password": "wrongpassword"
        }
        
        response = await test_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    async def test_login_nonexistent_user(self, test_client: AsyncClient):
        """Test login with nonexistent user fails."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
        
        response = await test_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    async def test_login_inactive_user(self, test_client: AsyncClient, test_db_session: AsyncSession, test_buyer_user: User):
        """Test login with inactive user fails."""
        # Deactivate user
        test_buyer_user.is_active = False
        test_db_session.add(test_buyer_user)
        await test_db_session.commit()
        
        login_data = {
            "email": test_buyer_user.email,
            "password": "testpassword123"
        }
        
        response = await test_client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401


class TestAuthTokenOperations:
    """Test token-related operations."""
    
    async def test_refresh_token(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test token refresh functionality."""
        response = await test_client.post("/api/v1/auth/refresh", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    async def test_refresh_token_unauthorized(self, test_client: AsyncClient):
        """Test token refresh without authentication fails."""
        response = await test_client.post("/api/v1/auth/refresh")
        
        assert response.status_code == 401
    
    async def test_verify_token(self, test_client: AsyncClient, buyer_auth_headers: dict, test_buyer_user: User):
        """Test token verification."""
        response = await test_client.post("/api/v1/auth/verify-token", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == test_buyer_user.email
        assert data["role"] == "buyer"
    
    async def test_verify_invalid_token(self, test_client: AsyncClient):
        """Test verification with invalid token fails."""
        headers = {"Authorization": "Bearer invalid-token"}
        response = await test_client.post("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 401


class TestAuthUserInfo:
    """Test current user information endpoints."""
    
    async def test_get_current_user(self, test_client: AsyncClient, buyer_auth_headers: dict, test_buyer_user: User):
        """Test getting current user information."""
        response = await test_client.get("/api/v1/auth/me", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == test_buyer_user.email
        assert data["first_name"] == test_buyer_user.first_name
        assert data["last_name"] == test_buyer_user.last_name
        assert data["role"] == "buyer"
        assert "company" in data
    
    async def test_get_current_user_unauthorized(self, test_client: AsyncClient):
        """Test getting current user without authentication fails."""
        response = await test_client.get("/api/v1/auth/me")
        
        assert response.status_code == 401


class TestAuthLogout:
    """Test logout functionality."""
    
    async def test_logout_success(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test successful logout."""
        response = await test_client.post("/api/v1/auth/logout", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "logged out" in data["message"].lower()
    
    async def test_logout_unauthorized(self, test_client: AsyncClient):
        """Test logout without authentication fails."""
        response = await test_client.post("/api/v1/auth/logout")
        
        assert response.status_code == 401


class TestAuthValidation:
    """Test authentication validation and edge cases."""
    
    async def test_register_invalid_role(self, test_client: AsyncClient, test_data_factory):
        """Test registration with invalid role fails."""
        registration_data = test_data_factory.create_user_data(
            role="invalid_role"
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 422
    
    async def test_login_missing_fields(self, test_client: AsyncClient):
        """Test login with missing fields fails."""
        # Missing password
        response = await test_client.post("/api/v1/auth/login", json={"email": "test@example.com"})
        assert response.status_code == 422
        
        # Missing email
        response = await test_client.post("/api/v1/auth/login", json={"password": "password123"})
        assert response.status_code == 422
    
    async def test_register_empty_strings(self, test_client: AsyncClient, test_data_factory):
        """Test registration with empty string fields fails."""
        registration_data = test_data_factory.create_user_data(
            first_name="",  # Empty string
            last_name=""
        )
        
        response = await test_client.post("/api/v1/auth/register", json=registration_data)
        
        assert response.status_code == 422
