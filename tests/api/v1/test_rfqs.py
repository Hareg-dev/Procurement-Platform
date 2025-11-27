"""
Comprehensive tests for RFQ (Request for Quotation) endpoints.

Tests cover:
- RFQ creation (buyers only)
- RFQ listing (my RFQs for buyers)
- Open RFQs listing (for suppliers)
- RFQ details retrieval with access control
- RFQ updates and modifications
- RFQ publishing (DRAFT -> OPEN)
- RFQ closing (OPEN -> CLOSED)
- Access control and permissions
- Validation and error handling
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, RFQ, RFQStatus


class TestRFQCreation:
    """Test RFQ creation endpoint."""
    
    async def test_create_rfq_as_buyer(self, test_client: AsyncClient, buyer_auth_headers: dict, test_data_factory):
        """Test successful RFQ creation by buyer."""
        rfq_data = test_data_factory.create_rfq_data(
            title="Office Furniture RFQ",
            description="Need ergonomic office furniture for 50 employees",
            budget_min=25000.00,
            budget_max=75000.00
        )
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=buyer_auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify RFQ data
        assert data["title"] == "Office Furniture RFQ"
        assert data["description"] == "Need ergonomic office furniture for 50 employees"
        assert data["budget_min"] == 25000.00
        assert data["budget_max"] == 75000.00
        assert data["status"] == "draft"  # New RFQs start as draft
        assert data["is_open"] is False  # Draft RFQs are not open
        assert data["bid_count"] == 0
        
        # Verify buyer company is set
        assert "buyer_company" in data
        assert data["buyer_company"]["name"] is not None
    
    async def test_create_rfq_as_supplier_forbidden(self, test_client: AsyncClient, supplier_auth_headers: dict, test_data_factory):
        """Test that suppliers cannot create RFQs."""
        rfq_data = test_data_factory.create_rfq_data()
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=supplier_auth_headers)
        
        assert response.status_code == 403
        assert "Only buyers can create RFQs" in response.json()["detail"]
    
    async def test_create_rfq_unauthorized(self, test_client: AsyncClient, test_data_factory):
        """Test RFQ creation without authentication fails."""
        rfq_data = test_data_factory.create_rfq_data()
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data)
        
        assert response.status_code == 401
    
    async def test_create_rfq_past_deadline(self, test_client: AsyncClient, buyer_auth_headers: dict, test_data_factory):
        """Test creating RFQ with past deadline fails."""
        rfq_data = test_data_factory.create_rfq_data(
            deadline=(datetime.utcnow() - timedelta(days=1)).isoformat()  # Past deadline
        )
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=buyer_auth_headers)
        
        assert response.status_code == 400
        assert "deadline must be in the future" in response.json()["detail"]
    
    async def test_create_rfq_invalid_budget_range(self, test_client: AsyncClient, buyer_auth_headers: dict, test_data_factory):
        """Test creating RFQ with invalid budget range fails."""
        rfq_data = test_data_factory.create_rfq_data(
            budget_min=50000.00,
            budget_max=25000.00  # Max less than min
        )
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=buyer_auth_headers)
        
        assert response.status_code == 400
        assert "Minimum budget cannot be greater than maximum budget" in response.json()["detail"]
    
    async def test_create_rfq_missing_required_fields(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test creating RFQ with missing required fields fails."""
        # Missing title
        rfq_data = {
            "description": "Test description",
            "deadline": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=buyer_auth_headers)
        
        assert response.status_code == 422  # Validation error


class TestRFQRetrieval:
    """Test RFQ retrieval endpoints."""
    
    async def test_get_my_rfqs_as_buyer(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ):
        """Test getting my RFQs as buyer."""
        response = await test_client.get("/api/v1/rfqs/", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify RFQ data structure
        rfq_data = data[0]
        assert "id" in rfq_data
        assert "title" in rfq_data
        assert "deadline" in rfq_data
        assert "status" in rfq_data
        assert "buyer_company" in rfq_data
        assert "bid_count" in rfq_data
        assert "is_open" in rfq_data
    
    async def test_get_my_rfqs_as_supplier_forbidden(self, test_client: AsyncClient, supplier_auth_headers: dict):
        """Test that suppliers cannot get buyer's RFQs."""
        response = await test_client.get("/api/v1/rfqs/", headers=supplier_auth_headers)
        
        assert response.status_code == 403
    
    async def test_get_open_rfqs_as_supplier(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test getting open RFQs as supplier."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        response = await test_client.get("/api/v1/rfqs/open", headers=supplier_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Should see the open RFQ (since it's from a different company)
        assert len(data) >= 1
        
        rfq_data = data[0]
        assert rfq_data["status"] == "open"
        assert rfq_data["is_open"] is True
    
    async def test_get_open_rfqs_excludes_own_company(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test that suppliers don't see RFQs from their own company."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        # Try to get open RFQs as buyer (same company as RFQ creator)
        response = await test_client.get("/api/v1/rfqs/open", headers=buyer_auth_headers)
        
        # Should return empty list or not include own RFQ
        assert response.status_code == 200
        data = response.json()
        
        # If there are RFQs, none should be from the same company
        for rfq in data:
            assert rfq["id"] != test_rfq.id
    
    async def test_get_rfq_by_id_as_owner(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ):
        """Test getting RFQ details by ID as owner."""
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_rfq.id
        assert data["title"] == test_rfq.title
        assert data["description"] == test_rfq.description
        assert "buyer_company" in data
        assert "bid_count" in data
    
    async def test_get_rfq_by_id_not_found(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test getting nonexistent RFQ returns 404."""
        response = await test_client.get("/api/v1/rfqs/99999", headers=buyer_auth_headers)
        
        assert response.status_code == 404
        assert "RFQ not found" in response.json()["detail"]
    
    async def test_get_rfq_access_control(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ):
        """Test RFQ access control for different user types."""
        # Supplier should not see draft RFQ
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}", headers=supplier_auth_headers)
        assert response.status_code == 403


class TestRFQUpdates:
    """Test RFQ update endpoints."""
    
    async def test_update_rfq_as_owner(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ):
        """Test updating RFQ as owner."""
        update_data = {
            "title": "Updated RFQ Title",
            "description": "Updated description with more details",
            "budget_max": 60000.00
        }
        
        response = await test_client.put(f"/api/v1/rfqs/{test_rfq.id}", json=update_data, headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["title"] == "Updated RFQ Title"
        assert data["description"] == "Updated description with more details"
        assert data["budget_max"] == 60000.00
    
    async def test_update_rfq_unauthorized(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ):
        """Test that non-owners cannot update RFQ."""
        update_data = {"title": "Hacked Title"}
        
        response = await test_client.put(f"/api/v1/rfqs/{test_rfq.id}", json=update_data, headers=supplier_auth_headers)
        
        assert response.status_code == 403
    
    async def test_update_rfq_with_bids_restricted(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_bid):
        """Test that RFQs with bids have update restrictions."""
        update_data = {"title": "Cannot Update This"}
        
        response = await test_client.put(f"/api/v1/rfqs/{test_rfq.id}", json=update_data, headers=buyer_auth_headers)
        
        assert response.status_code == 400
        assert "already has bids" in response.json()["detail"]


class TestRFQStatusManagement:
    """Test RFQ status management (publish, close)."""
    
    async def test_publish_rfq(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ):
        """Test publishing RFQ (DRAFT -> OPEN)."""
        response = await test_client.post(f"/api/v1/rfqs/{test_rfq.id}/publish", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "open"
        assert data["is_open"] is True
    
    async def test_publish_rfq_unauthorized(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ):
        """Test that non-owners cannot publish RFQ."""
        response = await test_client.post(f"/api/v1/rfqs/{test_rfq.id}/publish", headers=supplier_auth_headers)
        
        assert response.status_code == 403
    
    async def test_publish_already_open_rfq(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test publishing already open RFQ fails."""
        # Make RFQ open first
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        response = await test_client.post(f"/api/v1/rfqs/{test_rfq.id}/publish", headers=buyer_auth_headers)
        
        assert response.status_code == 400
        assert "Only draft RFQs can be published" in response.json()["detail"]
    
    async def test_close_rfq(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test closing RFQ (OPEN -> CLOSED)."""
        # Make RFQ open first
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        response = await test_client.post(f"/api/v1/rfqs/{test_rfq.id}/close", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "closed"
        assert data["is_open"] is False
    
    async def test_close_rfq_unauthorized(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ):
        """Test that non-owners cannot close RFQ."""
        response = await test_client.post(f"/api/v1/rfqs/{test_rfq.id}/close", headers=supplier_auth_headers)
        
        assert response.status_code == 403


class TestRFQPagination:
    """Test RFQ pagination and filtering."""
    
    async def test_rfq_pagination(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test RFQ listing with pagination."""
        response = await test_client.get("/api/v1/rfqs/?page=1&size=5", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5  # Respects size limit
    
    async def test_open_rfqs_pagination(self, test_client: AsyncClient, supplier_auth_headers: dict):
        """Test open RFQs listing with pagination."""
        response = await test_client.get("/api/v1/rfqs/open?page=1&size=10", headers=supplier_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 10


class TestRFQValidation:
    """Test RFQ validation and edge cases."""
    
    async def test_create_rfq_with_minimal_data(self, test_client: AsyncClient, buyer_auth_headers: dict):
        """Test creating RFQ with only required fields."""
        rfq_data = {
            "title": "Minimal RFQ",
            "description": "Basic description",
            "deadline": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=buyer_auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["title"] == "Minimal RFQ"
        assert data["budget_min"] is None
        assert data["budget_max"] is None
        assert data["requirements"] is None
    
    async def test_create_rfq_with_zero_budget(self, test_client: AsyncClient, buyer_auth_headers: dict, test_data_factory):
        """Test creating RFQ with zero budget values."""
        rfq_data = test_data_factory.create_rfq_data(
            budget_min=0.00,
            budget_max=0.00
        )
        
        response = await test_client.post("/api/v1/rfqs/", json=rfq_data, headers=buyer_auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["budget_min"] == 0.00
        assert data["budget_max"] == 0.00
    
    async def test_update_rfq_invalid_deadline(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ):
        """Test updating RFQ with invalid deadline fails."""
        update_data = {
            "deadline": (datetime.utcnow() - timedelta(days=1)).isoformat()  # Past deadline
        }
        
        response = await test_client.put(f"/api/v1/rfqs/{test_rfq.id}", json=update_data, headers=buyer_auth_headers)
        
        assert response.status_code == 400
        assert "deadline must be in the future" in response.json()["detail"]


class TestRFQBusinessLogic:
    """Test RFQ business logic and properties."""
    
    async def test_rfq_is_open_property(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test RFQ is_open property calculation."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_open"] is True
    
    async def test_rfq_is_expired_property(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test RFQ is_expired property calculation."""
        # Set deadline in the past
        test_rfq.deadline = datetime.utcnow() - timedelta(days=1)
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_expired"] is True
        assert data["is_open"] is False  # Expired RFQs are not open
    
    async def test_rfq_bid_count_property(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_bid):
        """Test RFQ bid_count property."""
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["bid_count"] >= 1  # Should have at least the test bid
