# Procurement Platform API Documentation

## Overview

The Procurement Platform is a comprehensive FastAPI-based system that facilitates the procurement process between buyers and suppliers. The platform includes AI-powered features for enhanced decision-making and negotiation assistance.

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication
Most endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Table of Contents

1. [Authentication Endpoints](#authentication-endpoints)
2. [User Management Endpoints](#user-management-endpoints)
3. [RFQ (Request for Quotation) Endpoints](#rfq-endpoints)
4. [Bid Management Endpoints](#bid-endpoints)
5. [Public Marketplace Endpoints](#public-endpoints)
6. [AI-Powered Features](#ai-endpoints)
7. [WebSocket Chat](#websocket-chat)
8. [Error Handling](#error-handling)
9. [Data Models](#data-models)

---

## Authentication Endpoints

### Register New User
**POST** `/auth/register`

Register a new user and create their company.

**Request Body:**
```json
{
  "email": "user@company.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "role": "buyer",
  "company": {
    "name": "Acme Corporation",
    "description": "Leading technology company",
    "website": "https://acme.com",
    "address": "123 Business St, City, State",
    "phone": "+1234567890"
  }
}
```

**Response (201):**
```json
{
  "user": {
    "id": 1,
    "email": "user@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "buyer",
    "is_active": true,
    "is_verified": false,
    "company": {
      "id": 1,
      "name": "Acme Corporation",
      "description": "Leading technology company"
    }
  },
  "token": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### Login
**POST** `/auth/login`

Authenticate user and receive access token.

**Request Body:**
```json
{
  "email": "user@company.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "user": {
    "id": 1,
    "email": "user@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "buyer"
  },
  "token": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### Refresh Token
**POST** `/auth/refresh`

Refresh the access token.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Get Current User
**GET** `/auth/me`

Get current authenticated user information.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": 1,
  "email": "user@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "buyer",
  "company": {
    "id": 1,
    "name": "Acme Corporation"
  }
}
```

### Logout
**POST** `/auth/logout`

Logout user (invalidate token).

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "message": "Successfully logged out"
}
```

---

## User Management Endpoints

### Get My Profile
**GET** `/users/me`

Get detailed profile information for the current user.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": 1,
  "email": "user@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "buyer",
  "is_active": true,
  "is_verified": false,
  "title": "Procurement Manager",
  "bio": "Experienced in strategic sourcing",
  "company": {
    "id": 1,
    "name": "Acme Corporation",
    "description": "Leading technology company"
  }
}
```

### Get Dashboard Data
**GET** `/users/me/dashboard`

Get personalized dashboard data for welcome screens.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "user@company.com",
  "role": "buyer",
  "title": "Procurement Manager",
  "bio": "Experienced in strategic sourcing",
  "company_name": "Acme Corporation"
}
```

### List Users (Admin Only)
**GET** `/users/`

List all users in the system.

**Headers:** `Authorization: Bearer <admin_token>`

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20, max: 100)

**Response (200):**
```json
[
  {
    "id": 1,
    "email": "user@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "buyer",
    "company": {
      "id": 1,
      "name": "Acme Corporation"
    }
  }
]
```

### Get User by ID (Admin Only)
**GET** `/users/{user_id}`

Get specific user details by ID.

**Headers:** `Authorization: Bearer <admin_token>`

**Response (200):**
```json
{
  "id": 1,
  "email": "user@company.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "buyer",
  "company": {
    "id": 1,
    "name": "Acme Corporation"
  }
}
```

---

## RFQ Endpoints

### Create RFQ
**POST** `/rfqs/`

Create a new Request for Quotation (buyers only).

**Headers:** `Authorization: Bearer <buyer_token>`

**Request Body:**
```json
{
  "title": "Office Equipment Procurement",
  "description": "Need office furniture and equipment for new branch",
  "deadline": "2024-12-31T23:59:59",
  "budget_min": 10000.00,
  "budget_max": 50000.00,
  "requirements": "Ergonomic furniture, energy-efficient equipment"
}
```

**Response (201):**
```json
{
  "id": 1,
  "title": "Office Equipment Procurement",
  "description": "Need office furniture and equipment for new branch",
  "deadline": "2024-12-31T23:59:59",
  "status": "draft",
  "budget_min": 10000.00,
  "budget_max": 50000.00,
  "requirements": "Ergonomic furniture, energy-efficient equipment",
  "buyer_company": {
    "id": 1,
    "name": "Acme Corporation"
  },
  "bid_count": 0,
  "is_open": false,
  "is_expired": false,
  "ai_summary": "RFQ for office equipment with sustainability focus"
}
```

### Get My RFQs
**GET** `/rfqs/`

Get RFQs created by current user's company (buyers only).

**Headers:** `Authorization: Bearer <buyer_token>`

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20)

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "Office Equipment Procurement",
    "deadline": "2024-12-31T23:59:59",
    "status": "open",
    "created_at": "2024-01-15T10:00:00",
    "buyer_company": {
      "id": 1,
      "name": "Acme Corporation"
    },
    "bid_count": 3,
    "is_open": true
  }
]
```

### Get Open RFQs
**GET** `/rfqs/open`

Get open RFQs available for bidding (suppliers only).

**Headers:** `Authorization: Bearer <supplier_token>`

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20)

**Response (200):**
```json
[
  {
    "id": 2,
    "title": "IT Infrastructure Upgrade",
    "deadline": "2024-11-30T23:59:59",
    "status": "open",
    "created_at": "2024-01-10T14:30:00",
    "buyer_company": {
      "id": 2,
      "name": "Tech Solutions Inc"
    },
    "bid_count": 1,
    "is_open": true
  }
]
```

### Get RFQ Details
**GET** `/rfqs/{rfq_id}`

Get detailed information about a specific RFQ.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": 1,
  "title": "Office Equipment Procurement",
  "description": "Need office furniture and equipment for new branch",
  "deadline": "2024-12-31T23:59:59",
  "status": "open",
  "budget_min": 10000.00,
  "budget_max": 50000.00,
  "requirements": "Ergonomic furniture, energy-efficient equipment",
  "buyer_company": {
    "id": 1,
    "name": "Acme Corporation",
    "description": "Leading technology company"
  },
  "bid_count": 3,
  "is_open": true,
  "is_expired": false,
  "ai_summary": "Comprehensive RFQ for office setup with focus on ergonomics"
}
```

### Update RFQ
**PUT** `/rfqs/{rfq_id}`

Update an existing RFQ (buyers only, restrictions apply).

**Headers:** `Authorization: Bearer <buyer_token>`

**Request Body:**
```json
{
  "title": "Updated Office Equipment Procurement",
  "description": "Updated requirements for office setup",
  "budget_max": 60000.00
}
```

**Response (200):**
```json
{
  "id": 1,
  "title": "Updated Office Equipment Procurement",
  "description": "Updated requirements for office setup",
  "budget_max": 60000.00
}
```

### Publish RFQ
**POST** `/rfqs/{rfq_id}/publish`

Publish RFQ to make it available for bidding (DRAFT → OPEN).

**Headers:** `Authorization: Bearer <buyer_token>`

**Response (200):**
```json
{
  "id": 1,
  "status": "open",
  "is_open": true
}
```

### Close RFQ
**POST** `/rfqs/{rfq_id}/close`

Close RFQ to stop accepting new bids (OPEN → CLOSED).

**Headers:** `Authorization: Bearer <buyer_token>`

**Response (200):**
```json
{
  "id": 1,
  "status": "closed",
  "is_open": false
}
```

---

## Bid Endpoints

### Submit Bid
**POST** `/rfqs/{rfq_id}/bids`

Submit a bid on an RFQ (suppliers only).

**Headers:** `Authorization: Bearer <supplier_token>`

**Request Body:**
```json
{
  "price": 35000.00,
  "message": "We can provide high-quality equipment within your timeline",
  "delivery_time": 21,
  "terms": "Net 30 payment, 2-year warranty included"
}
```

**Response (201):**
```json
{
  "id": 1,
  "price": 35000.00,
  "message": "We can provide high-quality equipment within your timeline",
  "delivery_time": 21,
  "terms": "Net 30 payment, 2-year warranty included",
  "is_selected": false,
  "rfq_id": 1,
  "supplier_company": {
    "id": 2,
    "name": "Office Solutions Ltd"
  },
  "ai_summary": "Competitive bid with good warranty terms"
}
```

### Get RFQ Bids
**GET** `/rfqs/{rfq_id}/bids`

Get all bids for an RFQ (RFQ owner only).

**Headers:** `Authorization: Bearer <buyer_token>`

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20)

**Response (200):**
```json
[
  {
    "id": 1,
    "price": 35000.00,
    "delivery_time": 21,
    "is_selected": false,
    "created_at": "2024-01-16T09:30:00",
    "supplier_company": {
      "id": 2,
      "name": "Office Solutions Ltd"
    }
  }
]
```

### Get My Bids
**GET** `/bids/my`

Get bids submitted by current user's company.

**Headers:** `Authorization: Bearer <supplier_token>`

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20)

**Response (200):**
```json
[
  {
    "id": 1,
    "price": 35000.00,
    "rfq_id": 1,
    "is_selected": false,
    "supplier_company": {
      "id": 2,
      "name": "Office Solutions Ltd"
    }
  }
]
```

### Get Bid Details
**GET** `/bids/{bid_id}`

Get detailed information about a specific bid.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": 1,
  "price": 35000.00,
  "message": "We can provide high-quality equipment within your timeline",
  "delivery_time": 21,
  "terms": "Net 30 payment, 2-year warranty included",
  "is_selected": false,
  "rfq_id": 1,
  "supplier_company": {
    "id": 2,
    "name": "Office Solutions Ltd"
  },
  "ai_summary": "Competitive bid with excellent warranty coverage"
}
```

### Update Bid
**PUT** `/bids/{bid_id}`

Update an existing bid (before RFQ deadline).

**Headers:** `Authorization: Bearer <supplier_token>`

**Request Body:**
```json
{
  "price": 32000.00,
  "message": "Updated proposal with better pricing",
  "delivery_time": 18
}
```

**Response (200):**
```json
{
  "id": 1,
  "price": 32000.00,
  "message": "Updated proposal with better pricing",
  "delivery_time": 18
}
```

### Select Winning Bid
**POST** `/bids/{bid_id}/select`

Select a bid as the winning bid (RFQ owner only).

**Headers:** `Authorization: Bearer <buyer_token>`

**Response (200):**
```json
{
  "id": 1,
  "is_selected": true,
  "rfq_id": 1
}
```

### Withdraw Bid
**DELETE** `/bids/{bid_id}`

Withdraw a bid (before RFQ deadline).

**Headers:** `Authorization: Bearer <supplier_token>`

**Response (200):**
```json
{
  "message": "Bid withdrawn successfully"
}
```

---

## Public Endpoints

### Get Public Company Profile
**GET** `/public/companies/{company_id}`

Get public information about a company (no authentication required).

**Response (200):**
```json
{
  "id": 1,
  "name": "Office Solutions Ltd",
  "public_description": "Leading provider of office equipment and furniture",
  "logo_url": "https://company.com/logo.png",
  "website": "https://officesolutions.com",
  "location": "New York, NY",
  "created_at": "2024-01-01T00:00:00"
}
```

### List Public Suppliers
**GET** `/public/suppliers`

List all public supplier companies (no authentication required).

**Query Parameters:**
- `location` (string): Filter by location
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20)

**Response (200):**
```json
[
  {
    "id": 2,
    "name": "Office Solutions Ltd",
    "public_description": "Leading provider of office equipment",
    "logo_url": "https://company.com/logo.png",
    "website": "https://officesolutions.com",
    "location": "New York, NY",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

### List Public Companies
**GET** `/public/companies`

List all public companies (buyers and suppliers, no authentication required).

**Query Parameters:**
- `location` (string): Filter by location
- `page` (int): Page number (default: 1)
- `size` (int): Items per page (default: 20)

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "Acme Corporation",
    "public_description": "Leading technology company",
    "logo_url": "https://acme.com/logo.png",
    "website": "https://acme.com",
    "location": "San Francisco, CA",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

---

## AI Endpoints

### Generate Negotiation Message
**POST** `/bids/{bid_id}/negotiate`

Generate AI-powered negotiation message based on bid context.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "goal": "Negotiate a 10% price reduction while maintaining quality and delivery timeline"
}
```

**Response (200):**
```json
{
  "message": "Dear [Supplier Name], Thank you for your competitive proposal of $35,000. After reviewing your bid, we are impressed with your warranty terms and delivery timeline. However, to align with our budget constraints, we would like to discuss the possibility of a 10% price adjustment to $31,500 while maintaining the same quality standards and 21-day delivery commitment. We believe this adjustment would create a mutually beneficial partnership. Would you be open to discussing this proposal?",
  "context_used": "Bid #1 for RFQ 'Office Equipment Procurement'"
}
```

---

## WebSocket Chat

### AI Co-pilot Chat
**WebSocket** `/ws/chat/{rfq_id}?token=<jwt_token>`

Real-time AI assistance for procurement decisions.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/chat/1?token=your_jwt_token');
```

**Send Message:**
```json
{
  "message": "What are the key risks in this RFQ?"
}
```

**Receive Messages:**
```json
{
  "type": "ai_response",
  "message": "Based on your RFQ for office equipment, here are the key risks to consider: 1. Delivery timeline constraints - 21 days may be tight for custom furniture. 2. Budget range - The $40,000 spread between min/max budget could lead to significant quality variations. 3. Specification clarity - Consider adding more detailed ergonomic requirements..."
}
```

**Message Types:**
- `system`: Connection status and system messages
- `ai_response`: AI assistant responses
- `error`: Error messages

---

## Error Handling

### Standard Error Response Format
```json
{
  "detail": "Error description",
  "type": "error_type"
}
```

### Common HTTP Status Codes

- **200 OK**: Successful request
- **201 Created**: Resource created successfully
- **400 Bad Request**: Invalid request data or business rule violation
- **401 Unauthorized**: Authentication required or invalid token
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server error

### Error Examples

**Authentication Error (401):**
```json
{
  "detail": "Could not validate credentials"
}
```

**Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "price"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt",
      "ctx": {"limit_value": 0}
    }
  ]
}
```

**Business Rule Violation (400):**
```json
{
  "detail": "Cannot bid on your own RFQ"
}
```

---

## Data Models

### User Roles
- `buyer`: Can create RFQs and evaluate bids
- `supplier`: Can submit bids on open RFQs
- `admin`: Full system access

### RFQ Status
- `draft`: RFQ created but not published
- `open`: RFQ published and accepting bids
- `closed`: RFQ closed, no more bids accepted
- `awarded`: Winning bid selected
- `cancelled`: RFQ cancelled

### Pagination Parameters
- `page`: Page number (minimum: 1)
- `size`: Items per page (minimum: 1, maximum: 100)

### Date Format
All dates use ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`

---

## Rate Limiting

API endpoints are rate-limited to prevent abuse:
- Authentication endpoints: 5 requests per minute
- General endpoints: 100 requests per minute
- AI endpoints: 10 requests per minute
- WebSocket connections: 1 connection per user per RFQ

---

## Changelog

### Version 1.0.0
- Initial API implementation
- Authentication and user management
- RFQ and bid management
- Public marketplace endpoints
- AI-powered negotiation assistance
- WebSocket AI co-pilot chat

---

For additional support or questions, please contact the development team.
