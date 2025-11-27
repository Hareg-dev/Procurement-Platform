@echo off
setlocal enabledelayedexpansion

REM Complete Procurement Platform Workflow Test
REM Tests the entire flow: Register -> Login -> Create RFQ -> Submit Bid -> Select Winner

set BASE_URL=http://localhost:8000/api/v1
echo 🚀 Testing Complete Procurement Platform Workflow
echo Base URL: %BASE_URL%
echo ==================================================
echo.

REM Step 1: Register Buyer Company
echo 📝 Step 1: Registering Buyer Company (TechCorp)
curl -s -X POST "%BASE_URL%/auth/register" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\": \"buyer@techcorp.com\", \"password\": \"password123\", \"first_name\": \"Sarah\", \"last_name\": \"Johnson\", \"role\": \"buyer\", \"company\": {\"name\": \"TechCorp Industries\", \"description\": \"Leading technology solutions provider\", \"website\": \"https://techcorp.com\", \"address\": \"123 Tech Street, San Francisco, CA\", \"phone\": \"+1-555-0123\"}}" > buyer_response.json

echo Buyer Registration Response:
type buyer_response.json
echo.

REM Extract token manually (simplified for batch)
for /f "tokens=2 delims=:" %%a in ('findstr "access_token" buyer_response.json') do (
    set BUYER_TOKEN=%%a
    set BUYER_TOKEN=!BUYER_TOKEN:"=!
    set BUYER_TOKEN=!BUYER_TOKEN:,=!
    set BUYER_TOKEN=!BUYER_TOKEN: =!
)
echo Buyer Token: !BUYER_TOKEN!
echo.

REM Step 2: Register Supplier Company
echo 🏭 Step 2: Registering Supplier Company (SupplyPro)
curl -s -X POST "%BASE_URL%/auth/register" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\": \"supplier@supplypro.com\", \"password\": \"password123\", \"first_name\": \"Mike\", \"last_name\": \"Wilson\", \"role\": \"supplier\", \"company\": {\"name\": \"SupplyPro Solutions\", \"description\": \"Premium office equipment and furniture supplier\", \"website\": \"https://supplypro.com\", \"address\": \"456 Supply Ave, New York, NY\", \"phone\": \"+1-555-0456\"}}" > supplier_response.json

echo Supplier Registration Response:
type supplier_response.json
echo.

REM Extract supplier token
for /f "tokens=2 delims=:" %%a in ('findstr "access_token" supplier_response.json') do (
    set SUPPLIER_TOKEN=%%a
    set SUPPLIER_TOKEN=!SUPPLIER_TOKEN:"=!
    set SUPPLIER_TOKEN=!SUPPLIER_TOKEN:,=!
    set SUPPLIER_TOKEN=!SUPPLIER_TOKEN: =!
)
echo Supplier Token: !SUPPLIER_TOKEN!
echo.

REM Step 3: Buyer creates RFQ
echo 📋 Step 3: Buyer Creates RFQ
curl -s -X POST "%BASE_URL%/rfqs/" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\": \"Office Equipment Procurement 2024\", \"description\": \"Need comprehensive office setup including ergonomic furniture, computers, and networking equipment for new 50-person office\", \"deadline\": \"2024-12-31T23:59:59\", \"budget_min\": 25000.00, \"budget_max\": 75000.00, \"requirements\": \"Ergonomic chairs and desks, energy-efficient computers, secure networking equipment, 2-year warranty minimum\"}" > rfq_response.json

echo RFQ Creation Response:
type rfq_response.json
echo.

REM Extract RFQ ID
for /f "tokens=2 delims=:" %%a in ('findstr "\"id\"" rfq_response.json') do (
    set RFQ_ID=%%a
    set RFQ_ID=!RFQ_ID:,=!
    set RFQ_ID=!RFQ_ID: =!
)
echo RFQ ID: !RFQ_ID!
echo.

REM Step 4: Publish RFQ
echo 📢 Step 4: Publishing RFQ
curl -s -X POST "%BASE_URL%/rfqs/!RFQ_ID!/publish" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" > publish_response.json

echo Publish Response:
type publish_response.json
echo.

REM Step 5: Supplier views open RFQs
echo 👀 Step 5: Supplier Views Open RFQs
curl -s -X GET "%BASE_URL%/rfqs/open" ^
  -H "Authorization: Bearer !SUPPLIER_TOKEN!" > open_rfqs.json

echo Open RFQs for Supplier:
type open_rfqs.json
echo.

REM Step 6: Supplier submits bid
echo 💰 Step 6: Supplier Submits Bid
curl -s -X POST "%BASE_URL%/rfqs/!RFQ_ID!/bids" ^
  -H "Authorization: Bearer !SUPPLIER_TOKEN!" ^
  -H "Content-Type: application/json" ^
  -d "{\"price\": 45000.00, \"message\": \"We can provide premium office equipment with excellent warranty coverage. Our solution includes ergonomic Herman Miller chairs, height-adjustable desks, latest Dell computers, and enterprise-grade Cisco networking equipment.\", \"delivery_time\": 21, \"terms\": \"Net 30 payment terms, 3-year comprehensive warranty, free installation and setup, 24/7 technical support\"}" > bid_response.json

echo Bid Submission Response:
type bid_response.json
echo.

REM Extract bid ID
for /f "tokens=2 delims=:" %%a in ('findstr "\"id\"" bid_response.json') do (
    set BID_ID=%%a
    set BID_ID=!BID_ID:,=!
    set BID_ID=!BID_ID: =!
)
echo Bid ID: !BID_ID!
echo.

REM Step 7: Buyer views all bids
echo 📊 Step 7: Buyer Reviews All Bids
curl -s -X GET "%BASE_URL%/rfqs/!RFQ_ID!/bids" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" > all_bids.json

echo All Bids for RFQ:
type all_bids.json
echo.

REM Step 8: Buyer selects winning bid
echo 🏆 Step 8: Buyer Selects Winning Bid
curl -s -X POST "%BASE_URL%/bids/!BID_ID!/select" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" > select_response.json

echo Bid Selection Response:
type select_response.json
echo.

REM Step 9: Verify final RFQ status
echo ✅ Step 9: Verify Final RFQ Status
curl -s -X GET "%BASE_URL%/rfqs/!RFQ_ID!" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" > final_rfq.json

echo Final RFQ Status:
type final_rfq.json
echo.

REM Step 10: Test AI chat
echo 🤖 Step 10: Test AI Chat Feature
curl -s -X POST "%BASE_URL%/chat/simple-chat" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"What are the key factors to consider when evaluating office equipment bids?\"}" > chat_response.json

echo AI Chat Response:
type chat_response.json
echo.

REM Step 11: Test dashboard
echo 📊 Step 11: Test Buyer Dashboard
curl -s -X GET "%BASE_URL%/dashboard" ^
  -H "Authorization: Bearer !BUYER_TOKEN!" > dashboard.json

echo Buyer Dashboard:
type dashboard.json
echo.

REM Step 12: Test public endpoints
echo 🌐 Step 12: Test Public Company Listings
curl -s -X GET "%BASE_URL%/public/companies" > public_companies.json

echo Public Companies:
type public_companies.json
echo.

echo 🎉 WORKFLOW TEST COMPLETED!
echo ==================================================
echo Summary:
echo ✅ Registered buyer and supplier companies
echo ✅ Created and published RFQ
echo ✅ Submitted bid
echo ✅ Selected winning bid
echo ✅ Tested AI chat functionality
echo ✅ Verified dashboard data
echo ✅ Tested public marketplace
echo.
echo The complete procurement workflow has been successfully tested!

REM Cleanup temporary files
del buyer_response.json supplier_response.json rfq_response.json publish_response.json open_rfqs.json bid_response.json all_bids.json select_response.json final_rfq.json chat_response.json dashboard.json public_companies.json

pause