"""
Test configuration and fixtures for the procurement platform.

This module provides pytest fixtures for database setup, test client,
authentication, and test data creation.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Any
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.config import Settings
from app.core.db import get_db, Base
from app.core.security import get_password_hash
from app.models.orm import User, Company, RFQ, Bid, UserRole, RFQStatus


# Test database URL (in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestSettings(Settings):
    """Test-specific settings."""
    database_url: str = TEST_DATABASE_URL
    secret_key: str = "test-secret-key"
    openai_api_key: str = "test-openai-key"
    redis_url: str = "redis://localhost:6379/15"  # Use different DB for tests


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def test_client(test_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database dependency override."""
    
    async def override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_company(test_db_session: AsyncSession) -> Company:
    """Create a test company."""
    company = Company(
        name="Test Company Inc.",
        description="A test company for procurement",
        website="https://testcompany.com",
        address="123 Test Street, Test City",
        phone="+1234567890",
        is_active=True,
        is_public=True,
        public_description="We are a leading test company",
        logo_url="https://testcompany.com/logo.png",
        location="Test City, TC"
    )
    test_db_session.add(company)
    await test_db_session.commit()
    await test_db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def test_supplier_company(test_db_session: AsyncSession) -> Company:
    """Create a test supplier company."""
    company = Company(
        name="Test Supplier Ltd.",
        description="A test supplier company",
        website="https://testsupplier.com",
        address="456 Supplier Ave, Supplier City",
        phone="+0987654321",
        is_active=True,
        is_public=True,
        public_description="We supply quality test products",
        logo_url="https://testsupplier.com/logo.png",
        location="Supplier City, SC"
    )
    test_db_session.add(company)
    await test_db_session.commit()
    await test_db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def test_buyer_user(test_db_session: AsyncSession, test_company: Company) -> User:
    """Create a test buyer user."""
    user = User(
        email="buyer@testcompany.com",
        hashed_password=get_password_hash("testpassword123"),
        first_name="John",
        last_name="Buyer",
        role=UserRole.BUYER,
        is_active=True,
        is_verified=True,
        company_id=test_company.id,
        title="Procurement Manager",
        bio="Experienced procurement professional"
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_supplier_user(test_db_session: AsyncSession, test_supplier_company: Company) -> User:
    """Create a test supplier user."""
    user = User(
        email="supplier@testsupplier.com",
        hashed_password=get_password_hash("testpassword123"),
        first_name="Jane",
        last_name="Supplier",
        role=UserRole.SUPPLIER,
        is_active=True,
        is_verified=True,
        company_id=test_supplier_company.id,
        title="Sales Manager",
        bio="Dedicated to providing quality products"
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin_user(test_db_session: AsyncSession, test_company: Company) -> User:
    """Create a test admin user."""
    user = User(
        email="admin@testcompany.com",
        hashed_password=get_password_hash("adminpassword123"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        company_id=test_company.id,
        title="System Administrator",
        bio="Platform administrator"
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_rfq(test_db_session: AsyncSession, test_buyer_user: User) -> RFQ:
    """Create a test RFQ."""
    rfq = RFQ(
        title="Test Office Equipment RFQ",
        description="We need office equipment including desks, chairs, and computers for our new office space.",
        deadline=datetime.utcnow() + timedelta(days=30),
        status=RFQStatus.OPEN,
        budget_min=10000.00,
        budget_max=50000.00,
        requirements="All equipment must be ergonomic and environmentally friendly.",
        buyer_company_id=test_buyer_user.company_id,
        created_by_user_id=test_buyer_user.id,
        ai_summary="RFQ for office equipment with sustainability requirements"
    )
    test_db_session.add(rfq)
    await test_db_session.commit()
    await test_db_session.refresh(rfq)
    return rfq


@pytest_asyncio.fixture
async def test_bid(test_db_session: AsyncSession, test_rfq: RFQ, test_supplier_user: User) -> Bid:
    """Create a test bid."""
    bid = Bid(
        price=35000.00,
        message="We can provide high-quality office equipment that meets all your requirements.",
        delivery_time=14,
        terms="Payment within 30 days, 2-year warranty included",
        rfq_id=test_rfq.id,
        supplier_company_id=test_supplier_user.company_id,
        submitted_by_user_id=test_supplier_user.id,
        ai_summary="Competitive bid with good warranty terms"
    )
    test_db_session.add(bid)
    await test_db_session.commit()
    await test_db_session.refresh(bid)
    return bid


@pytest_asyncio.fixture
async def buyer_auth_headers(test_client: AsyncClient, test_buyer_user: User) -> Dict[str, str]:
    """Get authentication headers for buyer user."""
    login_data = {
        "email": test_buyer_user.email,
        "password": "testpassword123"
    }
    response = await test_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    token = response.json()["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def supplier_auth_headers(test_client: AsyncClient, test_supplier_user: User) -> Dict[str, str]:
    """Get authentication headers for supplier user."""
    login_data = {
        "email": test_supplier_user.email,
        "password": "testpassword123"
    }
    response = await test_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    token = response.json()["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_auth_headers(test_client: AsyncClient, test_admin_user: User) -> Dict[str, str]:
    """Get authentication headers for admin user."""
    login_data = {
        "email": test_admin_user.email,
        "password": "adminpassword123"
    }
    response = await test_client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    token = response.json()["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# Test data factories
class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_company_data(**kwargs) -> Dict[str, Any]:
        """Create company test data."""
        default_data = {
            "name": "New Test Company",
            "description": "A new test company",
            "website": "https://newtestcompany.com",
            "address": "789 New Street, New City",
            "phone": "+1122334455"
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_user_data(**kwargs) -> Dict[str, Any]:
        """Create user test data."""
        default_data = {
            "email": "newuser@example.com",
            "password": "newpassword123",
            "first_name": "New",
            "last_name": "User",
            "role": "buyer",
            "company": TestDataFactory.create_company_data()
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_rfq_data(**kwargs) -> Dict[str, Any]:
        """Create RFQ test data."""
        default_data = {
            "title": "New Test RFQ",
            "description": "A new test RFQ for testing purposes",
            "deadline": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "budget_min": 5000.00,
            "budget_max": 25000.00,
            "requirements": "Test requirements"
        }
        default_data.update(kwargs)
        return default_data
    
    @staticmethod
    def create_bid_data(**kwargs) -> Dict[str, Any]:
        """Create bid test data."""
        default_data = {
            "price": 15000.00,
            "message": "Test bid message",
            "delivery_time": 21,
            "terms": "Test terms and conditions"
        }
        default_data.update(kwargs)
        return default_data


@pytest.fixture
def test_data_factory():
    """Provide test data factory."""
    return TestDataFactory
