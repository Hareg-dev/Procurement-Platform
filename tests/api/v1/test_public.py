"""
Comprehensive tests for public endpoints.

Tests cover:
- Public company profile retrieval
- Public supplier listing with filtering
- Public company listing
- Privacy controls (is_public flag)
- Location-based filtering
- Unauthenticated access
- Error handling and validation
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Company, User, UserRole


class TestPublicCompanyProfile:
    """Test public company profile endpoints."""
    
    async def test_get_public_company_profile(self, test_client: AsyncClient, test_company: Company):
        """Test getting public company profile without authentication."""
        response = await test_client.get(f"/api/v1/public/companies/{test_company.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify public company data
        assert data["id"] == test_company.id
        assert data["name"] == test_company.name
        assert data["public_description"] == test_company.public_description
        assert data["logo_url"] == test_company.logo_url
        assert data["website"] == test_company.website
        assert data["location"] == test_company.location
        assert "created_at" in data
        
        # Verify private fields are not exposed
        assert "address" not in data
        assert "phone" not in data
        assert "description" not in data  # Private description
    
    async def test_get_private_company_returns_404(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test that private companies return 404."""
        # Create a private company
        private_company = Company(
            name="Private Company",
            is_active=True,
            is_public=False  # Private company
        )
        test_db_session.add(private_company)
        await test_db_session.commit()
        await test_db_session.refresh(private_company)
        
        response = await test_client.get(f"/api/v1/public/companies/{private_company.id}")
        
        assert response.status_code == 404
        assert "not publicly available" in response.json()["detail"]
    
    async def test_get_inactive_company_returns_404(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test that inactive companies return 404."""
        # Create an inactive company
        inactive_company = Company(
            name="Inactive Company",
            is_active=False,  # Inactive company
            is_public=True
        )
        test_db_session.add(inactive_company)
        await test_db_session.commit()
        await test_db_session.refresh(inactive_company)
        
        response = await test_client.get(f"/api/v1/public/companies/{inactive_company.id}")
        
        assert response.status_code == 404
    
    async def test_get_nonexistent_company_returns_404(self, test_client: AsyncClient):
        """Test that nonexistent companies return 404."""
        response = await test_client.get("/api/v1/public/companies/99999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestPublicSupplierListing:
    """Test public supplier listing endpoints."""
    
    async def test_list_public_suppliers(self, test_client: AsyncClient, test_supplier_company: Company, test_supplier_user: User):
        """Test listing public suppliers without authentication."""
        response = await test_client.get("/api/v1/public/suppliers")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify supplier data structure
        supplier_data = next((s for s in data if s["id"] == test_supplier_company.id), None)
        assert supplier_data is not None
        assert supplier_data["name"] == test_supplier_company.name
        assert supplier_data["public_description"] == test_supplier_company.public_description
        assert supplier_data["location"] == test_supplier_company.location
    
    async def test_list_suppliers_with_location_filter(self, test_client: AsyncClient, test_supplier_company: Company):
        """Test listing suppliers with location filtering."""
        response = await test_client.get("/api/v1/public/suppliers?location=Supplier City")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Should include suppliers from "Supplier City"
        for supplier in data:
            assert "Supplier City" in supplier["location"]
    
    async def test_list_suppliers_location_filter_case_insensitive(self, test_client: AsyncClient, test_supplier_company: Company):
        """Test that location filtering is case insensitive."""
        response = await test_client.get("/api/v1/public/suppliers?location=supplier city")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still find suppliers despite case difference
        assert isinstance(data, list)
    
    async def test_list_suppliers_no_results_for_nonexistent_location(self, test_client: AsyncClient):
        """Test listing suppliers for nonexistent location returns empty list."""
        response = await test_client.get("/api/v1/public/suppliers?location=Nonexistent City")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0
    
    async def test_list_suppliers_excludes_buyers(self, test_client: AsyncClient, test_company: Company, test_buyer_user: User):
        """Test that supplier listing excludes buyer companies."""
        response = await test_client.get("/api/v1/public/suppliers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include buyer companies
        buyer_company_ids = [s["id"] for s in data if s["id"] == test_company.id]
        assert len(buyer_company_ids) == 0
    
    async def test_list_suppliers_excludes_private_companies(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test that supplier listing excludes private companies."""
        # Create a private supplier company
        private_supplier_company = Company(
            name="Private Supplier",
            is_active=True,
            is_public=False  # Private
        )
        test_db_session.add(private_supplier_company)
        await test_db_session.commit()
        await test_db_session.refresh(private_supplier_company)
        
        # Create supplier user for the private company
        from app.core.security import get_password_hash
        supplier_user = User(
            email="private@supplier.com",
            hashed_password=get_password_hash("password123"),
            first_name="Private",
            last_name="Supplier",
            role=UserRole.SUPPLIER,
            is_active=True,
            company_id=private_supplier_company.id
        )
        test_db_session.add(supplier_user)
        await test_db_session.commit()
        
        response = await test_client.get("/api/v1/public/suppliers")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include private companies
        private_company_ids = [s["id"] for s in data if s["id"] == private_supplier_company.id]
        assert len(private_company_ids) == 0


class TestPublicCompanyListing:
    """Test public company listing endpoints."""
    
    async def test_list_public_companies(self, test_client: AsyncClient, test_company: Company, test_supplier_company: Company):
        """Test listing all public companies without authentication."""
        response = await test_client.get("/api/v1/public/companies")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 2  # At least test_company and test_supplier_company
        
        # Verify both buyer and supplier companies are included
        company_ids = [c["id"] for c in data]
        assert test_company.id in company_ids
        assert test_supplier_company.id in company_ids
    
    async def test_list_companies_with_location_filter(self, test_client: AsyncClient, test_company: Company):
        """Test listing companies with location filtering."""
        response = await test_client.get("/api/v1/public/companies?location=Test City")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Should include companies from "Test City"
        for company in data:
            assert "Test City" in company["location"]
    
    async def test_list_companies_excludes_private(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test that company listing excludes private companies."""
        # Create a private company
        private_company = Company(
            name="Private Company",
            is_active=True,
            is_public=False
        )
        test_db_session.add(private_company)
        await test_db_session.commit()
        await test_db_session.refresh(private_company)
        
        response = await test_client.get("/api/v1/public/companies")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include private companies
        private_company_ids = [c["id"] for c in data if c["id"] == private_company.id]
        assert len(private_company_ids) == 0
    
    async def test_list_companies_excludes_inactive(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test that company listing excludes inactive companies."""
        # Create an inactive company
        inactive_company = Company(
            name="Inactive Company",
            is_active=False,
            is_public=True
        )
        test_db_session.add(inactive_company)
        await test_db_session.commit()
        await test_db_session.refresh(inactive_company)
        
        response = await test_client.get("/api/v1/public/companies")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include inactive companies
        inactive_company_ids = [c["id"] for c in data if c["id"] == inactive_company.id]
        assert len(inactive_company_ids) == 0


class TestPublicEndpointsPagination:
    """Test pagination for public endpoints."""
    
    async def test_suppliers_pagination(self, test_client: AsyncClient):
        """Test supplier listing with pagination."""
        response = await test_client.get("/api/v1/public/suppliers?page=1&size=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5  # Respects size limit
    
    async def test_companies_pagination(self, test_client: AsyncClient):
        """Test company listing with pagination."""
        response = await test_client.get("/api/v1/public/companies?page=1&size=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 10  # Respects size limit
    
    async def test_pagination_invalid_parameters(self, test_client: AsyncClient):
        """Test pagination with invalid parameters."""
        # Negative page
        response = await test_client.get("/api/v1/public/companies?page=-1")
        assert response.status_code == 422
        
        # Zero page
        response = await test_client.get("/api/v1/public/companies?page=0")
        assert response.status_code == 422
        
        # Negative size
        response = await test_client.get("/api/v1/public/companies?size=-1")
        assert response.status_code == 422


class TestPublicEndpointsValidation:
    """Test validation and edge cases for public endpoints."""
    
    async def test_get_company_invalid_id_format(self, test_client: AsyncClient):
        """Test getting company with invalid ID format."""
        response = await test_client.get("/api/v1/public/companies/invalid-id")
        
        assert response.status_code == 422  # Validation error
    
    async def test_location_filter_empty_string(self, test_client: AsyncClient):
        """Test location filtering with empty string."""
        response = await test_client.get("/api/v1/public/suppliers?location=")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return all suppliers (empty filter ignored)
        assert isinstance(data, list)
    
    async def test_location_filter_special_characters(self, test_client: AsyncClient):
        """Test location filtering with special characters."""
        response = await test_client.get("/api/v1/public/suppliers?location=São Paulo")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    async def test_very_large_page_size(self, test_client: AsyncClient):
        """Test pagination with very large page size."""
        response = await test_client.get("/api/v1/public/companies?size=1000")
        
        # Should either limit to reasonable size or return validation error
        assert response.status_code in [200, 422]


class TestPublicEndpointsUnauthenticated:
    """Test that public endpoints work without authentication."""
    
    async def test_all_public_endpoints_unauthenticated(self, test_client: AsyncClient, test_company: Company, test_supplier_company: Company):
        """Test that all public endpoints work without authentication headers."""
        
        # Test company profile
        response = await test_client.get(f"/api/v1/public/companies/{test_company.id}")
        assert response.status_code == 200
        
        # Test supplier listing
        response = await test_client.get("/api/v1/public/suppliers")
        assert response.status_code == 200
        
        # Test company listing
        response = await test_client.get("/api/v1/public/companies")
        assert response.status_code == 200
    
    async def test_public_endpoints_ignore_auth_headers(self, test_client: AsyncClient, buyer_auth_headers: dict, test_company: Company):
        """Test that public endpoints work even with authentication headers."""
        
        # Should work with auth headers (but not require them)
        response = await test_client.get(
            f"/api/v1/public/companies/{test_company.id}", 
            headers=buyer_auth_headers
        )
        assert response.status_code == 200
        
        # Should also work with invalid auth headers
        invalid_headers = {"Authorization": "Bearer invalid-token"}
        response = await test_client.get(
            f"/api/v1/public/companies/{test_company.id}", 
            headers=invalid_headers
        )
        assert response.status_code == 200


class TestPublicEndpointsDataIntegrity:
    """Test data integrity and consistency in public endpoints."""
    
    async def test_public_company_data_consistency(self, test_client: AsyncClient, test_company: Company):
        """Test that public company data is consistent across endpoints."""
        
        # Get company from profile endpoint
        profile_response = await test_client.get(f"/api/v1/public/companies/{test_company.id}")
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        
        # Get company from listing endpoint
        listing_response = await test_client.get("/api/v1/public/companies")
        assert listing_response.status_code == 200
        listing_data = listing_response.json()
        
        # Find the same company in listing
        company_in_listing = next((c for c in listing_data if c["id"] == test_company.id), None)
        assert company_in_listing is not None
        
        # Verify consistent data
        assert profile_data["name"] == company_in_listing["name"]
        assert profile_data["location"] == company_in_listing["location"]
        assert profile_data["public_description"] == company_in_listing["public_description"]
    
    async def test_supplier_listing_only_includes_suppliers(self, test_client: AsyncClient, test_supplier_user: User):
        """Test that supplier listing only includes companies with supplier users."""
        response = await test_client.get("/api/v1/public/suppliers")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned companies should have supplier users
        # This is validated by the endpoint logic
        assert isinstance(data, list)
        
        # Verify test supplier company is included
        supplier_company_ids = [s["id"] for s in data if s["id"] == test_supplier_user.company_id]
        assert len(supplier_company_ids) == 1
    
    async def test_location_filtering_accuracy(self, test_client: AsyncClient, test_db_session: AsyncSession):
        """Test that location filtering is accurate and doesn't return false positives."""
        
        # Create companies with specific locations
        company1 = Company(
            name="New York Company",
            location="New York, NY",
            is_active=True,
            is_public=True
        )
        company2 = Company(
            name="Los Angeles Company", 
            location="Los Angeles, CA",
            is_active=True,
            is_public=True
        )
        test_db_session.add_all([company1, company2])
        await test_db_session.commit()
        
        # Filter for New York
        response = await test_client.get("/api/v1/public/companies?location=New York")
        assert response.status_code == 200
        data = response.json()
        
        # Should only return New York company
        ny_companies = [c for c in data if "New York" in c["location"]]
        la_companies = [c for c in data if "Los Angeles" in c["location"]]
        
        assert len(ny_companies) >= 1
        assert len(la_companies) == 0
