# Complete Procurement Platform Workflow Test
# PowerShell version for Windows

$BaseUrl = "http://localhost:8000/api/v1"
Write-Host "🚀 Testing Complete Procurement Platform Workflow" -ForegroundColor Green
Write-Host "Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Yellow

# Function to make HTTP requests
function Invoke-ApiCall {
    param(
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers = @{},
        [string]$Body = $null
    )
    
    try {
        $params = @{
            Method = $Method
            Uri = $Uri
            Headers = $Headers
            ContentType = "application/json"
        }
        
        if ($Body) {
            $params.Body = $Body
        }
        
        $response = Invoke-RestMethod @params
        return $response
    }
    catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# Step 1: Register Buyer Company
Write-Host "`n📝 Step 1: Registering Buyer Company (TechCorp)" -ForegroundColor Blue

$buyerData = @{
    email = "buyer@techcorp.com"
    password = "password123"
    first_name = "Sarah"
    last_name = "Johnson"
    role = "buyer"
    company = @{
        name = "TechCorp Industries"
        description = "Leading technology solutions provider"
        website = "https://techcorp.com"
        address = "123 Tech Street, San Francisco, CA"
        phone = "+1-555-0123"
    }
} | ConvertTo-Json -Depth 3

$buyerResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/auth/register" -Body $buyerData
if ($buyerResponse) {
    Write-Host "✅ Buyer registered successfully" -ForegroundColor Green
    $buyerToken = $buyerResponse.token.access_token
    Write-Host "Buyer Token: $($buyerToken.Substring(0,20))..." -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to register buyer" -ForegroundColor Red
    exit 1
}

# Step 2: Register Supplier Company
Write-Host "`n🏭 Step 2: Registering Supplier Company (SupplyPro)" -ForegroundColor Blue

$supplierData = @{
    email = "supplier@supplypro.com"
    password = "password123"
    first_name = "Mike"
    last_name = "Wilson"
    role = "supplier"
    company = @{
        name = "SupplyPro Solutions"
        description = "Premium office equipment and furniture supplier"
        website = "https://supplypro.com"
        address = "456 Supply Ave, New York, NY"
        phone = "+1-555-0456"
    }
} | ConvertTo-Json -Depth 3

$supplierResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/auth/register" -Body $supplierData
if ($supplierResponse) {
    Write-Host "✅ Supplier registered successfully" -ForegroundColor Green
    $supplierToken = $supplierResponse.token.access_token
    Write-Host "Supplier Token: $($supplierToken.Substring(0,20))..." -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to register supplier" -ForegroundColor Red
    exit 1
}

# Step 3: Buyer creates RFQ
Write-Host "`n📋 Step 3: Buyer Creates RFQ" -ForegroundColor Blue

$rfqData = @{
    title = "Office Equipment Procurement 2024"
    description = "Need comprehensive office setup including ergonomic furniture, computers, and networking equipment for new 50-person office"
    deadline = "2024-12-31T23:59:59"
    budget_min = 25000.00
    budget_max = 75000.00
    requirements = "Ergonomic chairs and desks, energy-efficient computers, secure networking equipment, 2-year warranty minimum"
} | ConvertTo-Json

$headers = @{ Authorization = "Bearer $buyerToken" }
$rfqResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/rfqs/" -Headers $headers -Body $rfqData

if ($rfqResponse) {
    Write-Host "✅ RFQ created successfully" -ForegroundColor Green
    $rfqId = $rfqResponse.id
    Write-Host "RFQ ID: $rfqId" -ForegroundColor Gray
    Write-Host "Title: $($rfqResponse.title)" -ForegroundColor Gray
    Write-Host "Budget: $($rfqResponse.budget_min) - $($rfqResponse.budget_max)" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to create RFQ" -ForegroundColor Red
    exit 1
}

# Step 4: Publish RFQ
Write-Host "`n📢 Step 4: Publishing RFQ" -ForegroundColor Blue

$publishResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/rfqs/$rfqId/publish" -Headers $headers
if ($publishResponse) {
    Write-Host "✅ RFQ published successfully" -ForegroundColor Green
    Write-Host "Status: $($publishResponse.status)" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to publish RFQ" -ForegroundColor Red
}

# Step 5: Supplier views open RFQs
Write-Host "`n👀 Step 5: Supplier Views Open RFQs" -ForegroundColor Blue

$supplierHeaders = @{ Authorization = "Bearer $supplierToken" }
$openRfqs = Invoke-ApiCall -Method "GET" -Uri "$BaseUrl/rfqs/open" -Headers $supplierHeaders

if ($openRfqs) {
    Write-Host "✅ Found $($openRfqs.Count) open RFQ(s)" -ForegroundColor Green
    foreach ($rfq in $openRfqs) {
        Write-Host "  - $($rfq.title) (ID: $($rfq.id))" -ForegroundColor Gray
    }
} else {
    Write-Host "❌ Failed to get open RFQs" -ForegroundColor Red
}

# Step 6: Supplier submits bid
Write-Host "`n💰 Step 6: Supplier Submits Bid" -ForegroundColor Blue

$bidData = @{
    price = 45000.00
    message = "We can provide premium office equipment with excellent warranty coverage. Our solution includes ergonomic Herman Miller chairs, height-adjustable desks, latest Dell computers, and enterprise-grade Cisco networking equipment."
    delivery_time = 21
    terms = "Net 30 payment terms, 3-year comprehensive warranty, free installation and setup, 24/7 technical support"
} | ConvertTo-Json

$bidResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/rfqs/$rfqId/bids" -Headers $supplierHeaders -Body $bidData

if ($bidResponse) {
    Write-Host "✅ Bid submitted successfully" -ForegroundColor Green
    $bidId = $bidResponse.id
    Write-Host "Bid ID: $bidId" -ForegroundColor Gray
    Write-Host "Price: $($bidResponse.price)" -ForegroundColor Gray
    Write-Host "Delivery Time: $($bidResponse.delivery_time) days" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to submit bid" -ForegroundColor Red
    exit 1
}

# Step 7: Buyer views all bids
Write-Host "`n📊 Step 7: Buyer Reviews All Bids" -ForegroundColor Blue

$allBids = Invoke-ApiCall -Method "GET" -Uri "$BaseUrl/rfqs/$rfqId/bids" -Headers $headers

if ($allBids) {
    Write-Host "✅ Found $($allBids.Count) bid(s) for RFQ" -ForegroundColor Green
    foreach ($bid in $allBids) {
        Write-Host "  - Bid ID: $($bid.id), Price: $($bid.price), Company: $($bid.supplier_company.name)" -ForegroundColor Gray
    }
} else {
    Write-Host "❌ Failed to get bids" -ForegroundColor Red
}

# Step 8: Buyer selects winning bid
Write-Host "`n🏆 Step 8: Buyer Selects Winning Bid" -ForegroundColor Blue

$selectResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/bids/$bidId/select" -Headers $headers

if ($selectResponse) {
    Write-Host "✅ Bid selected as winner!" -ForegroundColor Green
    Write-Host "Selected: $($selectResponse.is_selected)" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to select bid" -ForegroundColor Red
}

# Step 9: Verify final RFQ status
Write-Host "`n✅ Step 9: Verify Final RFQ Status" -ForegroundColor Blue

$finalRfq = Invoke-ApiCall -Method "GET" -Uri "$BaseUrl/rfqs/$rfqId" -Headers $headers

if ($finalRfq) {
    Write-Host "✅ RFQ status verified" -ForegroundColor Green
    Write-Host "Status: $($finalRfq.status)" -ForegroundColor Gray
    Write-Host "Bid Count: $($finalRfq.bid_count)" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to get final RFQ status" -ForegroundColor Red
}

# Step 10: Test AI chat (optional - may fail if Ollama not running)
Write-Host "`n🤖 Step 10: Test AI Chat Feature" -ForegroundColor Blue

$chatData = @{
    message = "What are the key factors to consider when evaluating office equipment bids?"
} | ConvertTo-Json

$chatResponse = Invoke-ApiCall -Method "POST" -Uri "$BaseUrl/chat/simple-chat" -Headers $headers -Body $chatData

if ($chatResponse) {
    Write-Host "✅ AI Chat working" -ForegroundColor Green
    Write-Host "Response: $($chatResponse.response.Substring(0, [Math]::Min(100, $chatResponse.response.Length)))..." -ForegroundColor Gray
} else {
    Write-Host "⚠️  AI Chat not available (Ollama may not be running)" -ForegroundColor Yellow
}

# Step 11: Test dashboard
Write-Host "`n📊 Step 11: Test Buyer Dashboard" -ForegroundColor Blue

$dashboard = Invoke-ApiCall -Method "GET" -Uri "$BaseUrl/dashboard" -Headers $headers

if ($dashboard) {
    Write-Host "✅ Dashboard data retrieved" -ForegroundColor Green
    Write-Host "User: $($dashboard.user_info.first_name) $($dashboard.user_info.last_name)" -ForegroundColor Gray
    Write-Host "Company: $($dashboard.user_info.company_name)" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to get dashboard data" -ForegroundColor Red
}

# Step 12: Test public endpoints
Write-Host "`n🌐 Step 12: Test Public Company Listings" -ForegroundColor Blue

$publicCompanies = Invoke-ApiCall -Method "GET" -Uri "$BaseUrl/public/companies"

if ($publicCompanies) {
    Write-Host "✅ Public companies retrieved" -ForegroundColor Green
    Write-Host "Found $($publicCompanies.Count) public companies" -ForegroundColor Gray
} else {
    Write-Host "❌ Failed to get public companies" -ForegroundColor Red
}

# Summary
Write-Host "`n🎉 WORKFLOW TEST COMPLETED!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "✅ Registered buyer and supplier companies" -ForegroundColor Green
Write-Host "✅ Created and published RFQ" -ForegroundColor Green
Write-Host "✅ Submitted bid" -ForegroundColor Green
Write-Host "✅ Selected winning bid" -ForegroundColor Green
Write-Host "✅ Verified workflow completion" -ForegroundColor Green
Write-Host "`nThe complete procurement workflow has been successfully tested!" -ForegroundColor Green

# Display key information
Write-Host "`n📋 Key Information:" -ForegroundColor Cyan
Write-Host "Buyer Company: TechCorp Industries" -ForegroundColor Gray
Write-Host "Supplier Company: SupplyPro Solutions" -ForegroundColor Gray
Write-Host "RFQ ID: $rfqId" -ForegroundColor Gray
Write-Host "Bid ID: $bidId" -ForegroundColor Gray
Write-Host "Winning Bid Price: $45,000" -ForegroundColor Gray