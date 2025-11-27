# Manual Testing Commands for Procurement Platform

## Prerequisites
1. Start the FastAPI server: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
2. Ensure the server is running at `http://localhost:8000`

## Step-by-Step Testing Commands

### 1. Register Buyer Company
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "buyer@techcorp.com",
    "password": "password123",
    "first_name": "Sarah",
    "last_name": "Johnson",
    "role": "buyer",
    "company": {
      "name": "TechCorp Industries",
      "description": "Leading technology solutions provider",
      "website": "https://techcorp.com",
      "address": "123 Tech Street, San Francisco, CA",
      "phone": "+1-555-0123"
    }
  }'
```

**Expected Response:** Registration success with access token
**Save the `access_token` from response as `BUYER_TOKEN`**

### 2. Register Supplier Company
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "supplier@supplypro.com",
    "password": "password123",
    "first_name": "Mike",
    "last_name": "Wilson",
    "role": "supplier",
    "company": {
      "name": "SupplyPro Solutions",
      "description": "Premium office equipment and furniture supplier",
      "website": "https://supplypro.com",
      "address": "456 Supply Ave, New York, NY",
      "phone": "+1-555-0456"
    }
  }'
```

**Expected Response:** Registration success with access token
**Save the `access_token` from response as `SUPPLIER_TOKEN`**

### 3. Buyer Creates RFQ
```bash
curl -X POST "http://localhost:8000/api/v1/rfqs/" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Office Equipment Procurement 2024",
    "description": "Need comprehensive office setup including ergonomic furniture, computers, and networking equipment for new 50-person office",
    "deadline": "2024-12-31T23:59:59",
    "budget_min": 25000.00,
    "budget_max": 75000.00,
    "requirements": "Ergonomic chairs and desks, energy-efficient computers, secure networking equipment, 2-year warranty minimum"
  }'
```

**Expected Response:** RFQ created with status "draft"
**Save the `id` from response as `RFQ_ID`**

### 4. Publish RFQ (Make it Available for Bidding)
```bash
curl -X POST "http://localhost:8000/api/v1/rfqs/RFQ_ID_HERE/publish" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

**Expected Response:** RFQ status changed to "open"

### 5. Supplier Views Open RFQs
```bash
curl -X GET "http://localhost:8000/api/v1/rfqs/open" \
  -H "Authorization: Bearer YOUR_SUPPLIER_TOKEN_HERE"
```

**Expected Response:** List of open RFQs including the one just created

### 6. Supplier Gets RFQ Details
```bash
curl -X GET "http://localhost:8000/api/v1/rfqs/RFQ_ID_HERE" \
  -H "Authorization: Bearer YOUR_SUPPLIER_TOKEN_HERE"
```

**Expected Response:** Detailed RFQ information

### 7. Supplier Submits Bid
```bash
curl -X POST "http://localhost:8000/api/v1/rfqs/RFQ_ID_HERE/bids" \
  -H "Authorization: Bearer YOUR_SUPPLIER_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "price": 45000.00,
    "message": "We can provide premium office equipment with excellent warranty coverage. Our solution includes ergonomic Herman Miller chairs, height-adjustable desks, latest Dell computers, and enterprise-grade Cisco networking equipment.",
    "delivery_time": 21,
    "terms": "Net 30 payment terms, 3-year comprehensive warranty, free installation and setup, 24/7 technical support"
  }'
```

**Expected Response:** Bid created successfully
**Save the `id` from response as `BID_ID`**

### 8. Buyer Views All Bids for RFQ
```bash
curl -X GET "http://localhost:8000/api/v1/rfqs/RFQ_ID_HERE/bids" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

**Expected Response:** List of all bids for the RFQ

### 9. Buyer Gets Detailed Bid Information
```bash
curl -X GET "http://localhost:8000/api/v1/bids/BID_ID_HERE" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

**Expected Response:** Detailed bid information

### 10. Buyer Selects Winning Bid
```bash
curl -X POST "http://localhost:8000/api/v1/bids/BID_ID_HERE/select" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

**Expected Response:** Bid marked as selected, RFQ status changes to "awarded"

### 11. Verify Final RFQ Status
```bash
curl -X GET "http://localhost:8000/api/v1/rfqs/RFQ_ID_HERE" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

**Expected Response:** RFQ with status "awarded" and bid_count > 0

### 12. Supplier Checks Their Bids
```bash
curl -X GET "http://localhost:8000/api/v1/bids/my" \
  -H "Authorization: Bearer YOUR_SUPPLIER_TOKEN_HERE"
```

**Expected Response:** List of supplier's bids with selected status

## Additional Feature Tests

### Test AI Chat (Optional - requires Ollama)
```bash
curl -X POST "http://localhost:8000/api/v1/chat/simple-chat" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the key factors to consider when evaluating office equipment bids?"
  }'
```

### Test Dashboard
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

### Test Public Company Listings (No Auth Required)
```bash
curl -X GET "http://localhost:8000/api/v1/public/companies"
```

### Test User Profile
```bash
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer YOUR_BUYER_TOKEN_HERE"
```

## Expected Workflow Results

1. ✅ **Registration**: Two companies registered (buyer and supplier)
2. ✅ **RFQ Creation**: RFQ created in draft status
3. ✅ **RFQ Publishing**: RFQ status changed to open
4. ✅ **Bid Submission**: Supplier successfully submits bid
5. ✅ **Bid Review**: Buyer can view and analyze bids
6. ✅ **Bid Selection**: Buyer selects winning bid
7. ✅ **Status Update**: RFQ status changes to awarded
8. ✅ **Verification**: All parties can verify final status

## Troubleshooting

### Common Issues:
1. **401 Unauthorized**: Check if token is correctly included in Authorization header
2. **403 Forbidden**: Verify user role permissions (buyers can't bid, suppliers can't create RFQs)
3. **404 Not Found**: Ensure IDs are correct and resources exist
4. **400 Bad Request**: Check request body format and business rules

### Token Format:
- Always use: `Authorization: Bearer YOUR_TOKEN_HERE`
- Replace `YOUR_TOKEN_HERE` with actual token from registration/login response

### ID Replacement:
- Replace `RFQ_ID_HERE` with actual RFQ ID from step 3
- Replace `BID_ID_HERE` with actual bid ID from step 7
- Replace `YOUR_BUYER_TOKEN_HERE` with buyer's access token
- Replace `YOUR_SUPPLIER_TOKEN_HERE` with supplier's access token

## Success Indicators

- **HTTP 200/201**: Successful operations
- **Proper JSON responses**: Well-formatted data returned
- **Status transitions**: RFQ goes from draft → open → awarded
- **Role-based access**: Buyers and suppliers see appropriate data
- **Business rules enforced**: No self-bidding, deadline checks, etc.

This completes the full procurement workflow from company registration to contract award!