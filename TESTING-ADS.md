# Advertisement System Testing Guide

## 🚀 Quick Setup

### 1. Start the System
```bash
docker-compose -f docker-compose.hub.yml up -d
```

### 2. Create Test Users
```bash
python create_test_users.py
```

### 3. Access API Documentation
- Open: http://localhost:8000/docs

## 🧪 Testing Workflow

### Step 1: Login as Supplier
```bash
# POST /api/v1/auth/login
{
  "email": "supplier@techsupply.com",
  "password": "supplier123"
}
```

### Step 2: Supplier Requests Advertisement
```bash
# POST /api/v1/ads/client-request
# Use supplier JWT token
{
  "title": "Premium IT Hardware Solutions",
  "content": "We provide enterprise-grade servers, networking equipment, and cloud infrastructure solutions for businesses of all sizes.",
  "image_url": "https://example.com/tech-ad.jpg",
  "target_industries": ["technology", "manufacturing", "healthcare"]
}
```

### Step 3: Login as Admin (New Browser/Incognito)
```bash
# POST /api/v1/auth/login
{
  "email": "admin@procurement.com", 
  "password": "admin123"
}
```

### Step 4: Admin Views Pending Ads
```bash
# GET /api/v1/ads/pending
# Use admin JWT token
```

### Step 5: Admin Approves Advertisement
```bash
# POST /api/v1/ads/approve/{ad_id}
# Use admin JWT token
# Replace {ad_id} with actual ID from pending list
```

### Step 6: View Targeted Ads (Any User)
```bash
# GET /api/v1/ads/targeted?limit=5
# Use any user JWT token
```

## 🌐 Browser Testing

### Browser 1 (Supplier):
1. Go to http://localhost:8000/docs
2. Login with supplier credentials
3. Submit ad request

### Browser 2 (Admin):
1. Go to http://localhost:8000/docs (incognito/private)
2. Login with admin credentials  
3. View pending ads
4. Approve the supplier's ad

### Browser 3 (Buyer):
1. Go to http://localhost:8000/docs
2. Login with buyer credentials
3. View targeted ads (should see approved ad)

## 📱 API Endpoints Summary

- `POST /api/v1/auth/login` - Login
- `POST /api/v1/ads/client-request` - Supplier requests ad
- `GET /api/v1/ads/pending` - Admin views pending ads
- `POST /api/v1/ads/approve/{id}` - Admin approves ad
- `GET /api/v1/ads/targeted` - View targeted ads

Ready to test the advertisement approval workflow! 🎯