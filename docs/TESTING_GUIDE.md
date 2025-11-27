# Testing Guide for Procurement Platform

## Overview

This document provides comprehensive information about testing the procurement platform, including setup, running tests, and understanding the test structure.

## Test Structure

```
tests/
├── conftest.py                 # Test configuration and fixtures
├── api/
│   └── v1/
│       ├── test_auth.py        # Authentication endpoint tests
│       ├── test_users.py       # User management tests
│       ├── test_rfqs.py        # RFQ endpoint tests
│       ├── test_bids.py        # Bid endpoint tests
│       ├── test_public.py      # Public endpoint tests
│       └── test_ai_chat.py     # AI and WebSocket tests
├── run_tests.py                # Test runner script
└── pytest.ini                 # Pytest configuration
```

## Prerequisites

### Required Dependencies
```bash
pip install pytest pytest-asyncio httpx
```

### Optional Dependencies (for enhanced testing)
```bash
pip install pytest-cov pytest-xdist pytest-mock
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py --verbose

# Run specific test module
python run_tests.py --module auth
python run_tests.py --module rfqs
```

### Coverage Testing

```bash
# Run tests with coverage report
python run_tests.py --coverage

# Generate HTML coverage report
python run_tests.py --coverage --html-report
```

### Parallel Testing

```bash
# Run tests in parallel (faster execution)
python run_tests.py --parallel
```

### Test Filtering

```bash
# Run only fast tests (skip slow ones)
python run_tests.py --fast

# Run only integration tests
python run_tests.py --integration

# Run only unit tests
python run_tests.py --unit
```

### Direct Pytest Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/api/v1/test_auth.py

# Run specific test class
pytest tests/api/v1/test_auth.py::TestAuthRegistration

# Run specific test method
pytest tests/api/v1/test_auth.py::TestAuthRegistration::test_register_new_user_success

# Run with markers
pytest -m "auth"
pytest -m "not slow"
pytest -m "integration"
```

## Test Categories

### 1. Authentication Tests (`test_auth.py`)

**Coverage:**
- User registration with company creation
- User login and token generation
- Token refresh functionality
- Current user retrieval
- Token verification
- Logout functionality
- Error handling and validation

**Key Test Classes:**
- `TestAuthRegistration`: Registration endpoint tests
- `TestAuthLogin`: Login endpoint tests
- `TestAuthTokenOperations`: Token-related operations
- `TestAuthUserInfo`: Current user information
- `TestAuthLogout`: Logout functionality
- `TestAuthValidation`: Validation and edge cases

### 2. User Management Tests (`test_users.py`)

**Coverage:**
- User profile retrieval
- User dashboard data
- User listing (admin only)
- User details by ID (admin only)
- Access control and permissions
- Error handling and validation

**Key Test Classes:**
- `TestUserProfile`: Profile endpoint tests
- `TestUserListing`: User listing tests (admin)
- `TestUserDetails`: User details tests (admin)
- `TestUserRolePermissions`: Role-based access control
- `TestUserDataValidation`: Data validation tests
- `TestUserProfileFields`: New profile field tests

### 3. RFQ Tests (`test_rfqs.py`)

**Coverage:**
- RFQ creation (buyers only)
- RFQ listing (my RFQs for buyers)
- Open RFQs listing (for suppliers)
- RFQ details retrieval with access control
- RFQ updates and modifications
- RFQ publishing (DRAFT → OPEN)
- RFQ closing (OPEN → CLOSED)
- Access control and permissions
- Validation and error handling

**Key Test Classes:**
- `TestRFQCreation`: RFQ creation tests
- `TestRFQRetrieval`: RFQ retrieval tests
- `TestRFQUpdates`: RFQ update tests
- `TestRFQStatusManagement`: Status management tests
- `TestRFQPagination`: Pagination tests
- `TestRFQValidation`: Validation tests
- `TestRFQBusinessLogic`: Business logic tests

### 4. Bid Tests (`test_bids.py`)

**Coverage:**
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

**Key Test Classes:**
- `TestBidSubmission`: Bid submission tests
- `TestBidRetrieval`: Bid retrieval tests
- `TestBidUpdates`: Bid update tests
- `TestBidSelection`: Bid selection tests
- `TestBidWithdrawal`: Bid withdrawal tests
- `TestBidAINegotiation`: AI negotiation tests
- `TestBidValidation`: Validation tests
- `TestBidBusinessLogic`: Business logic tests

### 5. Public Endpoint Tests (`test_public.py`)

**Coverage:**
- Public company profile retrieval
- Public supplier listing with filtering
- Public company listing
- Privacy controls (is_public flag)
- Location-based filtering
- Unauthenticated access
- Error handling and validation

**Key Test Classes:**
- `TestPublicCompanyProfile`: Company profile tests
- `TestPublicSupplierListing`: Supplier listing tests
- `TestPublicCompanyListing`: Company listing tests
- `TestPublicEndpointsPagination`: Pagination tests
- `TestPublicEndpointsValidation`: Validation tests
- `TestPublicEndpointsUnauthenticated`: Unauthenticated access tests
- `TestPublicEndpointsDataIntegrity`: Data integrity tests

### 6. AI and WebSocket Tests (`test_ai_chat.py`)

**Coverage:**
- AI negotiation assistance endpoint
- WebSocket AI chat functionality
- Authentication and access control
- Error handling for AI services
- Message validation and formatting
- Chat history management

**Key Test Classes:**
- `TestAINegotiation`: AI negotiation tests
- `TestWebSocketAIChat`: WebSocket chat tests
- `TestAIServiceMocking`: AI service mocking tests
- `TestAIEndpointsAccessControl`: Access control tests
- `TestAIEndpointsValidation`: Validation tests

## Test Fixtures

### Database Fixtures
- `test_db_engine`: Test database engine (SQLite in-memory)
- `test_db_session`: Test database session
- `test_client`: HTTP test client with database override

### Data Fixtures
- `test_company`: Test buyer company
- `test_supplier_company`: Test supplier company
- `test_buyer_user`: Test buyer user
- `test_supplier_user`: Test supplier user
- `test_admin_user`: Test admin user
- `test_rfq`: Test RFQ
- `test_bid`: Test bid

### Authentication Fixtures
- `buyer_auth_headers`: Authentication headers for buyer
- `supplier_auth_headers`: Authentication headers for supplier
- `admin_auth_headers`: Authentication headers for admin

### Data Factory
- `test_data_factory`: Factory for creating test data

## Test Configuration

### Pytest Markers

```python
# Mark slow tests
@pytest.mark.slow
def test_complex_operation():
    pass

# Mark integration tests
@pytest.mark.integration
def test_full_workflow():
    pass

# Mark AI tests
@pytest.mark.ai
def test_ai_feature():
    pass
```

### Environment Variables

```bash
# Test database (automatically configured)
TEST_DATABASE_URL=sqlite+aiosqlite:///:memory:

# Test settings
ENVIRONMENT=testing
SECRET_KEY=test-secret-key
OPENAI_API_KEY=test-openai-key
```

## Mocking AI Services

Since AI services require external API keys and may be expensive to test, we use mocking:

```python
from unittest.mock import patch

@patch('app.services.llm_service.llm_service.generate_negotiation_message')
async def test_negotiation(mock_llm, test_client, auth_headers):
    mock_llm.return_value = "Mocked AI response"
    # Test continues with mocked response
```

## Coverage Reports

### Terminal Coverage
```bash
python run_tests.py --coverage
```

### HTML Coverage Report
```bash
python run_tests.py --coverage --html-report
# Open htmlcov/index.html in browser
```

### Coverage Targets
- **Overall Coverage**: > 90%
- **Critical Paths**: > 95%
- **API Endpoints**: 100%
- **Business Logic**: > 95%

## Performance Testing

### Load Testing
```bash
# Run performance-sensitive tests
pytest -m "not slow" --benchmark-only
```

### Memory Usage
```bash
# Monitor memory usage during tests
pytest --memray
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx pytest-cov
      - name: Run tests
        run: python run_tests.py --coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## Debugging Tests

### Running Single Test with Debug
```bash
pytest tests/api/v1/test_auth.py::TestAuthRegistration::test_register_new_user_success -v -s --pdb
```

### Print Debug Information
```python
def test_something(test_client):
    response = test_client.get("/api/v1/test")
    print(f"Response: {response.status_code}")
    print(f"Data: {response.json()}")
    assert response.status_code == 200
```

### Async Debugging
```python
import asyncio

async def test_async_function():
    # Use asyncio.create_task for debugging async operations
    result = await some_async_function()
    print(f"Async result: {result}")
```

## Common Issues and Solutions

### 1. Database Connection Issues
```python
# Ensure proper async session handling
async def test_with_db(test_db_session):
    # Always use the provided session
    user = User(email="test@example.com")
    test_db_session.add(user)
    await test_db_session.commit()
```

### 2. Authentication Issues
```python
# Use provided auth fixtures
async def test_protected_endpoint(test_client, buyer_auth_headers):
    response = await test_client.get("/api/v1/protected", headers=buyer_auth_headers)
    assert response.status_code == 200
```

### 3. Async Test Issues
```python
# Ensure proper async/await usage
@pytest.mark.asyncio
async def test_async_endpoint():
    # Always use async client methods
    response = await test_client.get("/api/v1/endpoint")
```

## Best Practices

### 1. Test Naming
```python
# Good: Descriptive test names
def test_create_rfq_as_buyer_returns_201():
    pass

def test_submit_bid_on_expired_rfq_returns_400():
    pass

# Bad: Generic test names
def test_rfq():
    pass
```

### 2. Test Structure
```python
# Use AAA pattern: Arrange, Act, Assert
async def test_user_registration():
    # Arrange
    user_data = {"email": "test@example.com", "password": "password123"}
    
    # Act
    response = await test_client.post("/api/v1/auth/register", json=user_data)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
```

### 3. Test Independence
```python
# Each test should be independent
async def test_independent_operation(test_db_session):
    # Create fresh test data for each test
    user = User(email="unique@example.com")
    test_db_session.add(user)
    await test_db_session.commit()
```

### 4. Error Testing
```python
# Test both success and failure cases
async def test_login_success():
    # Test successful login
    pass

async def test_login_wrong_password():
    # Test login with wrong password
    pass

async def test_login_nonexistent_user():
    # Test login with nonexistent user
    pass
```

## Reporting Issues

When tests fail:

1. **Check the error message** for specific details
2. **Run the specific failing test** in isolation
3. **Check test data setup** and fixtures
4. **Verify database state** if applicable
5. **Check for async/await issues**
6. **Review recent code changes**

## Contributing to Tests

### Adding New Tests
1. Follow existing test structure and naming conventions
2. Use appropriate fixtures and markers
3. Include both positive and negative test cases
4. Add proper documentation and comments
5. Ensure tests are independent and repeatable

### Updating Existing Tests
1. Maintain backward compatibility when possible
2. Update related tests when changing business logic
3. Keep test data realistic and representative
4. Update documentation when changing test behavior

---

For questions about testing, please refer to the development team or create an issue in the project repository.
