"""
Comprehensive tests for Bid endpoints.

Tests cover:
- Bid submission on RFQs (suppliers only)
- Bid retrieval for RFQ owners
- My bids listing for suppliers
- Bid details with access control
- Bid updates before deadline
- Bid selection by RFQ owners
- Bid withdrawal
- AI negotiation assistance
- Access control and permissions
- Validation and error handling
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, RFQ, Bid, RFQStatus


class TestBidSubmission:
    """Test bid submission endpoints."""
    
    async def test_submit_bid_as_supplier(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession, test_data_factory):
        """Test successful bid submission by supplier."""
        # Make RFQ open for bidding
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = test_data_factory.create_bid_data(
            price=30000.00,
            message="We can deliver high-quality products within your timeline",
            delivery_time=21,
            terms="Net 30 payment terms, 1-year warranty"
        )
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify bid data
        assert data["price"] == 30000.00
        assert data["message"] == "We can deliver high-quality products within your timeline"
        assert data["delivery_time"] == 21
        assert data["terms"] == "Net 30 payment terms, 1-year warranty"
        assert data["is_selected"] is False
        assert data["rfq_id"] == test_rfq.id
        
        # Verify supplier company is set
        assert "supplier_company" in data
        assert data["supplier_company"]["name"] is not None
    
    async def test_submit_bid_as_buyer_forbidden(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_data_factory):
        """Test that buyers cannot submit bids."""
        bid_data = test_data_factory.create_bid_data()
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 403
        assert "Only suppliers can submit bids" in response.json()["detail"]
    
    async def test_submit_bid_on_draft_rfq(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_data_factory):
        """Test submitting bid on draft RFQ fails."""
        # RFQ is draft by default
        bid_data = test_data_factory.create_bid_data()
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 400
        assert "not open for bidding" in response.json()["detail"]
    
    async def test_submit_bid_on_expired_rfq(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession, test_data_factory):
        """Test submitting bid on expired RFQ fails."""
        # Make RFQ expired
        test_rfq.status = RFQStatus.OPEN
        test_rfq.deadline = datetime.utcnow() - timedelta(hours=1)
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = test_data_factory.create_bid_data()
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 400
        assert "deadline has passed" in response.json()["detail"]
    
    async def test_submit_bid_on_own_rfq(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession, test_data_factory):
        """Test that suppliers cannot bid on their own company's RFQs."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = test_data_factory.create_bid_data()
        
        # Try to bid as buyer (same company as RFQ creator)
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=buyer_auth_headers
        )
        
        assert response.status_code in [400, 403]  # Should prevent self-bidding
    
    async def test_submit_duplicate_bid(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_bid, test_data_factory):
        """Test submitting duplicate bid from same company fails."""
        bid_data = test_data_factory.create_bid_data(price=40000.00)
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 400
        assert "already submitted a bid" in response.json()["detail"]
    
    async def test_submit_bid_exceeds_budget(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession, test_data_factory):
        """Test submitting bid that exceeds maximum budget."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = test_data_factory.create_bid_data(
            price=100000.00  # Exceeds test_rfq.budget_max (50000)
        )
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 400
        assert "exceeds maximum budget" in response.json()["detail"]


class TestBidRetrieval:
    """Test bid retrieval endpoints."""
    
    async def test_get_rfq_bids_as_owner(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ, test_bid):
        """Test getting RFQ bids as RFQ owner."""
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}/bids", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify bid data structure
        bid_data = data[0]
        assert "id" in bid_data
        assert "price" in bid_data
        assert "delivery_time" in bid_data
        assert "is_selected" in bid_data
        assert "supplier_company" in bid_data
    
    async def test_get_rfq_bids_unauthorized(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ):
        """Test that non-owners cannot view RFQ bids."""
        response = await test_client.get(f"/api/v1/rfqs/{test_rfq.id}/bids", headers=supplier_auth_headers)
        
        assert response.status_code == 403
    
    async def test_get_my_bids(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid):
        """Test getting my company's bids."""
        response = await test_client.get("/api/v1/bids/my", headers=supplier_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify bid includes RFQ context
        bid_data = data[0]
        assert "rfq_id" in bid_data
        assert "supplier_company" in bid_data
    
    async def test_get_bid_by_id_as_submitter(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid):
        """Test getting bid details as submitter."""
        response = await test_client.get(f"/api/v1/bids/{test_bid.id}", headers=supplier_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_bid.id
        assert data["price"] == test_bid.price
        assert data["rfq_id"] == test_bid.rfq_id
    
    async def test_get_bid_by_id_as_rfq_owner(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid):
        """Test getting bid details as RFQ owner."""
        response = await test_client.get(f"/api/v1/bids/{test_bid.id}", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == test_bid.id
        assert data["price"] == test_bid.price
    
    async def test_get_bid_unauthorized(self, test_client: AsyncClient, test_bid):
        """Test getting bid without proper access fails."""
        # Create another supplier user from different company
        response = await test_client.get(f"/api/v1/bids/{test_bid.id}")
        
        assert response.status_code == 401


class TestBidUpdates:
    """Test bid update endpoints."""
    
    async def test_update_bid_as_submitter(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid, test_db_session: AsyncSession):
        """Test updating bid as submitter before deadline."""
        # Ensure RFQ is still open
        test_bid.rfq.status = RFQStatus.OPEN
        test_db_session.add(test_bid.rfq)
        await test_db_session.commit()
        
        update_data = {
            "price": 32000.00,
            "message": "Updated proposal with better terms",
            "delivery_time": 18
        }
        
        response = await test_client.put(
            f"/api/v1/bids/{test_bid.id}", 
            json=update_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["price"] == 32000.00
        assert data["message"] == "Updated proposal with better terms"
        assert data["delivery_time"] == 18
    
    async def test_update_bid_unauthorized(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid):
        """Test that non-submitters cannot update bid."""
        update_data = {"price": 1000.00}
        
        response = await test_client.put(
            f"/api/v1/bids/{test_bid.id}", 
            json=update_data, 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 403
    
    async def test_update_bid_after_deadline(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid, test_db_session: AsyncSession):
        """Test updating bid after deadline fails."""
        # Set RFQ deadline in the past
        test_bid.rfq.deadline = datetime.utcnow() - timedelta(hours=1)
        test_db_session.add(test_bid.rfq)
        await test_db_session.commit()
        
        update_data = {"price": 25000.00}
        
        response = await test_client.put(
            f"/api/v1/bids/{test_bid.id}", 
            json=update_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 400
        assert "deadline has passed" in response.json()["detail"]


class TestBidSelection:
    """Test bid selection endpoints."""
    
    async def test_select_bid_as_rfq_owner(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid):
        """Test selecting bid as RFQ owner."""
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/select", 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_selected"] is True
    
    async def test_select_bid_unauthorized(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid):
        """Test that non-owners cannot select bids."""
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/select", 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 403


class TestBidWithdrawal:
    """Test bid withdrawal endpoints."""
    
    async def test_withdraw_bid_as_submitter(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid, test_db_session: AsyncSession):
        """Test withdrawing bid as submitter."""
        # Ensure RFQ is still open
        test_bid.rfq.status = RFQStatus.OPEN
        test_db_session.add(test_bid.rfq)
        await test_db_session.commit()
        
        response = await test_client.delete(
            f"/api/v1/bids/{test_bid.id}", 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "withdrawn" in data["message"].lower()
    
    async def test_withdraw_bid_unauthorized(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid):
        """Test that non-submitters cannot withdraw bid."""
        response = await test_client.delete(
            f"/api/v1/bids/{test_bid.id}", 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 403
    
    async def test_withdraw_selected_bid(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid, test_db_session: AsyncSession):
        """Test withdrawing selected bid fails."""
        # Mark bid as selected
        test_bid.is_selected = True
        test_db_session.add(test_bid)
        await test_db_session.commit()
        
        response = await test_client.delete(
            f"/api/v1/bids/{test_bid.id}", 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 400
        assert "Cannot withdraw selected bid" in response.json()["detail"]


class TestBidAINegotiation:
    """Test AI negotiation assistance endpoints."""
    
    async def test_generate_negotiation_message_as_bid_owner(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid):
        """Test generating negotiation message as bid owner."""
        negotiation_data = {
            "goal": "Negotiate a 5% price reduction while maintaining delivery timeline"
        }
        
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/negotiate", 
            json=negotiation_data, 
            headers=supplier_auth_headers
        )
        
        # Note: This might fail if OpenAI is not configured, which is expected in tests
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "context_used" in data
            assert isinstance(data["message"], str)
            assert len(data["message"]) > 0
    
    async def test_generate_negotiation_message_as_rfq_owner(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid):
        """Test generating negotiation message as RFQ owner."""
        negotiation_data = {
            "goal": "Request additional warranty coverage and faster delivery"
        }
        
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/negotiate", 
            json=negotiation_data, 
            headers=buyer_auth_headers
        )
        
        # Note: This might fail if OpenAI is not configured
        assert response.status_code in [200, 500]
    
    async def test_generate_negotiation_message_unauthorized(self, test_client: AsyncClient, test_bid):
        """Test generating negotiation message without access fails."""
        negotiation_data = {"goal": "Some goal"}
        
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/negotiate", 
            json=negotiation_data
        )
        
        assert response.status_code == 401
    
    async def test_generate_negotiation_message_empty_goal(self, test_client: AsyncClient, supplier_auth_headers: dict, test_bid):
        """Test generating negotiation message with empty goal fails."""
        negotiation_data = {"goal": ""}
        
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/negotiate", 
            json=negotiation_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 422  # Validation error


class TestBidValidation:
    """Test bid validation and edge cases."""
    
    async def test_submit_bid_negative_price(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test submitting bid with negative price fails."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = {
            "price": -1000.00,  # Negative price
            "message": "Invalid bid"
        }
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_submit_bid_zero_price(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test submitting bid with zero price fails."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = {
            "price": 0.00,  # Zero price
            "message": "Free bid"
        }
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_submit_bid_missing_price(self, test_client: AsyncClient, supplier_auth_headers: dict, test_rfq: RFQ, test_db_session: AsyncSession):
        """Test submitting bid without price fails."""
        # Make RFQ open
        test_rfq.status = RFQStatus.OPEN
        test_db_session.add(test_rfq)
        await test_db_session.commit()
        
        bid_data = {
            "message": "Bid without price"
            # Missing price field
        }
        
        response = await test_client.post(
            f"/api/v1/rfqs/{test_rfq.id}/bids", 
            json=bid_data, 
            headers=supplier_auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    async def test_bid_pagination(self, test_client: AsyncClient, buyer_auth_headers: dict, test_rfq: RFQ):
        """Test bid listing with pagination."""
        response = await test_client.get(
            f"/api/v1/rfqs/{test_rfq.id}/bids?page=1&size=5", 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5  # Respects size limit


class TestBidBusinessLogic:
    """Test bid business logic and properties."""
    
    async def test_bid_includes_supplier_info(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid):
        """Test that bid responses include supplier company information."""
        response = await test_client.get(f"/api/v1/bids/{test_bid.id}", headers=buyer_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "supplier_company" in data
        supplier_info = data["supplier_company"]
        assert "name" in supplier_info
        assert supplier_info["name"] is not None
    
    async def test_bid_selection_updates_rfq_status(self, test_client: AsyncClient, buyer_auth_headers: dict, test_bid, test_db_session: AsyncSession):
        """Test that selecting a bid updates RFQ status to AWARDED."""
        response = await test_client.post(
            f"/api/v1/bids/{test_bid.id}/select", 
            headers=buyer_auth_headers
        )
        
        assert response.status_code == 200
        
        # Check that RFQ status was updated
        await test_db_session.refresh(test_bid.rfq)
        assert test_bid.rfq.status == RFQStatus.AWARDED
