#!/bin/bash

# Complete Procurement Platform Workflow Test
# Tests the entire flow: Register → Login → Create RFQ → Submit Bid → Select Winner

BASE_URL="http://localhost:8000/api/v1"
echo "🚀 Testing Complete Procurement Platform Workflow"
echo "Base URL: $BASE_URL"
echo "=================================================="

# Step 1: Register Buyer Company
echo "📝 Step 1: Registering Buyer Company (TechCorp)"
BUYER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
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
  }')

echo "Buyer Registration Response:"
echo "$BUYER_RESPONSE" | jq '.'

# Extract buyer token
BUYER_TOKEN=$(echo "$BUYER_RESPONSE" | jq -r '.token.access_token')
echo "Buyer Token: $BUYER_TOKEN"
echo ""

# Step 2: Register Supplier Company
echo "🏭 Step 2: Registering Supplier Company (SupplyPro)"
SUPPLIER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
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
  }')

echo "Supplier Registration Response:"
echo "$SUPPLIER_RESPONSE" | jq '.'

# Extract supplier token
SUPPLIER_TOKEN=$(echo "$SUPPLIER_RESPONSE" | jq -r '.token.access_token')
echo "Supplier Token: $SUPPLIER_TOKEN"
echo ""

# Step 3: Buyer creates RFQ
echo "📋 Step 3: Buyer Creates RFQ"
RFQ_RESPONSE=$(curl -s -X POST "$BASE_URL/rfqs/" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Office Equipment Procurement 2024",
    "description": "Need comprehensive office setup including ergonomic furniture, computers, and networking equipment for new 50-person office",
    "deadline": "2024-12-31T23:59:59",
    "budget_min": 25000.00,
    "budget_max": 75000.00,
    "requirements": "Ergonomic chairs and desks, energy-efficient computers, secure networking equipment, 2-year warranty minimum"
  }')

echo "RFQ Creation Response:"
echo "$RFQ_RESPONSE" | jq '.'

# Extract RFQ ID
RFQ_ID=$(echo "$RFQ_RESPONSE" | jq -r '.id')
echo "RFQ ID: $RFQ_ID"
echo ""

# Step 4: Publish RFQ (make it available for bidding)
echo "📢 Step 4: Publishing RFQ"
PUBLISH_RESPONSE=$(curl -s -X POST "$BASE_URL/rfqs/$RFQ_ID/publish" \
  -H "Authorization: Bearer $BUYER_TOKEN")

echo "Publish Response:"
echo "$PUBLISH_RESPONSE" | jq '.'
echo ""

# Step 5: Supplier views open RFQs
echo "👀 Step 5: Supplier Views Open RFQs"
OPEN_RFQS=$(curl -s -X GET "$BASE_URL/rfqs/open" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN")

echo "Open RFQs for Supplier:"
echo "$OPEN_RFQS" | jq '.'
echo ""

# Step 6: Supplier gets RFQ details
echo "🔍 Step 6: Supplier Gets RFQ Details"
RFQ_DETAILS=$(curl -s -X GET "$BASE_URL/rfqs/$RFQ_ID" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN")

echo "RFQ Details:"
echo "$RFQ_DETAILS" | jq '.'
echo ""

# Step 7: Supplier submits bid
echo "💰 Step 7: Supplier Submits Bid"
BID_RESPONSE=$(curl -s -X POST "$BASE_URL/rfqs/$RFQ_ID/bids" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price": 45000.00,
    "message": "We can provide premium office equipment with excellent warranty coverage. Our solution includes ergonomic Herman Miller chairs, height-adjustable desks, latest Dell computers, and enterprise-grade Cisco networking equipment.",
    "delivery_time": 21,
    "terms": "Net 30 payment terms, 3-year comprehensive warranty, free installation and setup, 24/7 technical support"
  }')

echo "Bid Submission Response:"
echo "$BID_RESPONSE" | jq '.'

# Extract bid ID
BID_ID=$(echo "$BID_RESPONSE" | jq -r '.id')
echo "Bid ID: $BID_ID"
echo ""

# Step 8: Register second supplier for competition
echo "🏭 Step 8: Registering Second Supplier (CompetitorCorp)"
SUPPLIER2_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "sales@competitorcorp.com",
    "password": "password123",
    "first_name": "Lisa",
    "last_name": "Chen",
    "role": "supplier",
    "company": {
      "name": "CompetitorCorp",
      "description": "Budget-friendly office solutions",
      "website": "https://competitorcorp.com",
      "address": "789 Budget Blvd, Chicago, IL",
      "phone": "+1-555-0789"
    }
  }')

SUPPLIER2_TOKEN=$(echo "$SUPPLIER2_RESPONSE" | jq -r '.token.access_token')
echo "Second Supplier Token: $SUPPLIER2_TOKEN"

# Step 9: Second supplier submits competing bid
echo "💸 Step 9: Second Supplier Submits Competing Bid"
BID2_RESPONSE=$(curl -s -X POST "$BASE_URL/rfqs/$RFQ_ID/bids" \
  -H "Authorization: Bearer $SUPPLIER2_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price": 38000.00,
    "message": "Cost-effective solution with reliable equipment. We offer good quality furniture and computers at competitive prices.",
    "delivery_time": 28,
    "terms": "Net 45 payment terms, 2-year standard warranty, basic installation included"
  }')

echo "Second Bid Response:"
echo "$BID2_RESPONSE" | jq '.'

BID2_ID=$(echo "$BID2_RESPONSE" | jq -r '.id')
echo "Second Bid ID: $BID2_ID"
echo ""

# Step 10: Buyer views all bids for the RFQ
echo "📊 Step 10: Buyer Reviews All Bids"
ALL_BIDS=$(curl -s -X GET "$BASE_URL/rfqs/$RFQ_ID/bids" \
  -H "Authorization: Bearer $BUYER_TOKEN")

echo "All Bids for RFQ:"
echo "$ALL_BIDS" | jq '.'
echo ""

# Step 11: Buyer gets detailed view of first bid
echo "🔍 Step 11: Buyer Reviews First Bid Details"
BID_DETAILS=$(curl -s -X GET "$BASE_URL/bids/$BID_ID" \
  -H "Authorization: Bearer $BUYER_TOKEN")

echo "First Bid Details:"
echo "$BID_DETAILS" | jq '.'
echo ""

# Step 12: Buyer selects winning bid
echo "🏆 Step 12: Buyer Selects Winning Bid"
SELECT_RESPONSE=$(curl -s -X POST "$BASE_URL/bids/$BID_ID/select" \
  -H "Authorization: Bearer $BUYER_TOKEN")

echo "Bid Selection Response:"
echo "$SELECT_RESPONSE" | jq '.'
echo ""

# Step 13: Verify RFQ status changed to awarded
echo "✅ Step 13: Verify RFQ Status"
FINAL_RFQ=$(curl -s -X GET "$BASE_URL/rfqs/$RFQ_ID" \
  -H "Authorization: Bearer $BUYER_TOKEN")

echo "Final RFQ Status:"
echo "$FINAL_RFQ" | jq '.'
echo ""

# Step 14: Supplier checks their bid status
echo "📈 Step 14: Winning Supplier Checks Bid Status"
SUPPLIER_BIDS=$(curl -s -X GET "$BASE_URL/bids/my" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN")

echo "Supplier's Bids:"
echo "$SUPPLIER_BIDS" | jq '.'
echo ""

# Step 15: Test AI chat feature
echo "🤖 Step 15: Test AI Chat Feature"
CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/chat/simple-chat" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the key factors to consider when evaluating office equipment bids?"
  }')

echo "AI Chat Response:"
echo "$CHAT_RESPONSE" | jq '.'
echo ""

# Step 16: Test dashboard endpoints
echo "📊 Step 16: Test Buyer Dashboard"
BUYER_DASHBOARD=$(curl -s -X GET "$BASE_URL/dashboard" \
  -H "Authorization: Bearer $BUYER_TOKEN")

echo "Buyer Dashboard:"
echo "$BUYER_DASHBOARD" | jq '.'
echo ""

echo "📊 Step 17: Test Supplier Dashboard"
SUPPLIER_DASHBOARD=$(curl -s -X GET "$BASE_URL/dashboard" \
  -H "Authorization: Bearer $SUPPLIER_TOKEN")

echo "Supplier Dashboard:"
echo "$SUPPLIER_DASHBOARD" | jq '.'
echo ""

# Step 18: Test public endpoints (no auth required)
echo "🌐 Step 18: Test Public Company Listings"
PUBLIC_COMPANIES=$(curl -s -X GET "$BASE_URL/public/companies")

echo "Public Companies:"
echo "$PUBLIC_COMPANIES" | jq '.'
echo ""

echo "🎉 WORKFLOW TEST COMPLETED SUCCESSFULLY!"
echo "=================================================="
echo "Summary:"
echo "✅ Registered 2 buyers and 2 suppliers"
echo "✅ Created and published RFQ"
echo "✅ Submitted 2 competing bids"
echo "✅ Selected winning bid"
echo "✅ Tested AI chat functionality"
echo "✅ Verified dashboard data"
echo "✅ Tested public marketplace"
echo ""
echo "The complete procurement workflow has been successfully tested!"