"""
Comprehensive tests for user management endpoints.

Tests cover:
- User profile retrieval
- User dashboard data
- User listing (admin only)
- User details by ID (admin only)
- Access control and permissions
- Error handling and validation
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, Company


class TestUserProfile:
    """Test user profile endpoints."""
    
    async def test_get_my_profile(self, test_client: AsyncClient, buyer_auth_headers: dict, test_buyer_user: User):
        """Test getting current user's profile."""
        response = await test_client.get("/api/v1/users/me", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify user data
        assert data["id"] == test_buyer_user.id
        assert data["email"] == test_buyer_user.email
        assert data["first_name"] == test_buyer_user.first_name
        assert data["last_name"] == test_buyer_user.last_name
        assert data["role"] == "buyer"
        assert data["is_active"] is True
        assert data["title"] == test_buyer_user.title
        assert data["bio"] == test_buyer_user.bio
        
        # Verify company data is included
        assert "company" in data
        company_data = data["company"]
        assert company_data["name"] == test_buyer_user.company.name
    
    async def test_get_my_profile_unauthorized(self, test_client: AsyncClient):
        """Test getting profile without authentication fails."""
        response = await test_client.get("/api/v1/users/me")
        
        assert response.status_code == 401
    
    async def test_get_user_dashboard(self, test_client: AsyncClient, buyer_auth_headers: dict, test_buyer_user: User):
        """Test getting user dashboard data."""
        response = await test_client.get("/api/v1/users/me/dashboard", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify dashboard data structure
        assert data["first_name"] == test_buyer_user.first_name
        assert data["last_name"] == test_buyer_user.last_name
        assert data["email"] == test_buyer_user.email
        assert data["role"] == "buyer"
        assert data["title"] == test_buyer_user.title
        assert data["bio"] == test_buyer_user.bio
        assert data["company_name"] == test_buyer_user.company.name
    
    async def test_get_user_dashboard_unauthorized(self, test_client: AsyncClient):
        """Test getting dashboard without authentication fails."""
        response = await test_client.get("/api/v1/users/me/dashboard")
        
        assert response.status_code == 401


class TestUserListing:
    """Test user listing endpoints (admin only)."""
    
    async def test_list_users_as_admin(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test listing users as admin."""
        response = await test_client.get("/api/v1/users/", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1  # At least the admin user exists
        
        # Verify user data structure
        user_data = data[0]
        assert "id" in user_data
        assert "email" in user_data
        assert "first_name" in user_data
        assert "last_name" in user_data
        assert "role" in user_data
        assert "company" in user_data
    
    async def test_list_users_with_pagination(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test listing users with pagination parameters."""
        response = await test_client.get(
            "/api/v1/users/?page=1&size=10", 
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 10  # Respects size limit
    
    async def test_list_users_as_buyer_forbidden(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test that buyers cannot list users."""
        response = await test_client.get("/api/v1/users/", headers=buyer_auth_headers)
        
        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]
    
    async def test_list_users_as_supplier_forbidden(self, test_client: AsyncClient, supplier_auth_headers: dict):
        """Test that suppliers cannot list users."""
        response = await test_client.get("/api/v1/users/", headers=supplier_auth_headers)
        
        assert response.status_code == 403
    
    async def test_list_users_unauthorized(self, test_client: AsyncClient):
        """Test listing users without authentication fails."""
        response = await test_client.get("/api/v1/users/")
        
        assert response.status_code == 401


class TestUserDetails:
    """Test user details by ID endpoints (admin only)."""
    
    async def test_get_user_by_id_as_admin(self, test_client: AsyncClient, admin_auth_headers: dict, test_buyer_user: User):
        """Test getting user details by ID as admin."""
        response = await test_client.get(
            f"/api/v1/users/{test_buyer_user.id}", 
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify user data
        assert data["id"] == test_buyer_user.id
        assert data["email"] == test_buyer_user.email
        assert data["first_name"] == test_buyer_user.first_name
        assert data["last_name"] == test_buyer_user.last_name
        assert data["role"] == "buyer"
        
        # Verify company data is included
        assert "company" in data
        company_data = data["company"]
        assert company_data["name"] == test_buyer_user.company.name
    
    async def test_get_user_by_id_not_found(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test getting nonexistent user returns 404."""
        response = await test_client.get("/api/v1/users/99999", headers=admin_auth_headers)
        
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
    
    async def test_get_user_by_id_as_buyer_forbidden(self, test_client: AsyncClient, buyer_auth_headers: dict, test_supplier_user: User):
        """Test that buyers cannot get user details by ID."""
        response = await test_client.get(
            f"/api/v1/users/{test_supplier_user.id}", 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 403
    
    async def test_get_user_by_id_unauthorized(self, test_client: AsyncClient, test_buyer_user: User):
        """Test getting user by ID without authentication fails."""
        response = await test_client.get(f"/api/v1/users/{test_buyer_user.id}")
        
        assert response.status_code == 401


class TestUserRolePermissions:
    """Test role-based access control for user endpoints."""
    
    async def test_buyer_can_access_own_profile(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test that buyers can access their own profile."""
        response = await test_client.get("/api/v1/users/me", headers=buyer_auth_headers)
        assert response.status_code == 200
    
    async def test_supplier_can_access_own_profile(self, test_client: AsyncClient, supplier_auth_headers: dict):
        """Test that suppliers can access their own profile."""
        response = await test_client.get("/api/v1/users/me", headers=supplier_auth_headers)
        assert response.status_code == 200
    
    async def test_admin_can_access_own_profile(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test that admins can access their own profile."""
        response = await test_client.get("/api/v1/users/me", headers=admin_auth_headers)
        assert response.status_code == 200
    
    async def test_admin_can_list_all_users(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test that admins can list all users."""
        response = await test_client.get("/api/v1/users/", headers=admin_auth_headers)
        assert response.status_code == 200
    
    async def test_admin_can_get_any_user_details(self, test_client: AsyncClient, admin_auth_headers: dict, test_buyer_user: User):
        """Test that admins can get any user's details."""
        response = await test_client.get(f"/api/v1/users/{test_buyer_user.id}", headers=admin_auth_headers)
        assert response.status_code == 200


class TestUserDataValidation:
    """Test data validation and edge cases."""
    
    async def test_get_user_invalid_id_format(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test getting user with invalid ID format."""
        response = await test_client.get("/api/v1/users/invalid-id", headers=admin_auth_headers)
        
        assert response.status_code == 422  # Validation error
    
    async def test_pagination_invalid_parameters(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test pagination with invalid parameters."""
        # Negative page
        response = await test_client.get("/api/v1/users/?page=-1", headers=admin_auth_headers)
        assert response.status_code == 422
        
        # Zero page
        response = await test_client.get("/api/v1/users/?page=0", headers=admin_auth_headers)
        assert response.status_code == 422
        
        # Negative size
        response = await test_client.get("/api/v1/users/?size=-1", headers=admin_auth_headers)
        assert response.status_code == 422
        
        # Zero size
        response = await test_client.get("/api/v1/users/?size=0", headers=admin_auth_headers)
        assert response.status_code == 422
    
    async def test_pagination_large_size(self, test_client: AsyncClient, admin_auth_headers: dict):
        """Test pagination with very large size parameter."""
        response = await test_client.get("/api/v1/users/?size=1000", headers=admin_auth_headers)
        
        # Should either limit to max size or return validation error
        assert response.status_code in [200, 422]


class TestUserProfileFields:
    """Test user profile field handling."""
    
    async def test_profile_includes_new_fields(self, test_client: AsyncClient, buyer_auth_headers: dict, test_buyer_user: User):
        """Test that profile includes title and bio fields."""
        response = await test_client.get("/api/v1/users/me", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify new fields are present
        assert "title" in data
        assert "bio" in data
        assert data["title"] == test_buyer_user.title
        assert data["bio"] == test_buyer_user.bio
    
    async def test_dashboard_includes_company_name(self, test_client: AsyncClient, buyer_auth_headers: dict, test_buyer_user: User):
        """Test that dashboard includes company name for personalization."""
        response = await test_client.get("/api/v1/users/me/dashboard", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "company_name" in data
        assert data["company_name"] == test_buyer_user.company.name
    
    async def test_profile_with_null_optional_fields(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test profile with null optional fields (title, bio)."""
        # Create user with null title and bio
        from app.core.security import get_password_hash
        from app.models.orm import UserRole
        
        # First create a company
        company = Company(
            name="Test Company for Null Fields",
            is_active=True
        )
        test_db_session.add(company)
        await test_db_session.commit()
        await test_db_session.refresh(company)
        
        user = User(
            email="nullfields@example.com",
            hashed_password=get_password_hash("password123"),
            first_name="Null",
            last_name="Fields",
            role=UserRole.BUYER,
            is_active=True,
            company_id=company.id,
            title=None,  # Null title
            bio=None     # Null bio
        )
        test_db_session.add(user)
        await test_db_session.commit()
        
        # Login and get profile
        login_data = {"email": "nullfields@example.com", "password": "password123"}
        login_response = await test_client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["token"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await test_client.get("/api/v1/users/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] is None
        assert data["bio"] is None
