# Advertisement API Test Commands

## Setup
```bash
# Set base URL
BASE_URL=http://localhost:8000/api/v1

# Get admin token (replace with actual token after registration)
ADMIN_TOKEN="your_admin_token_here"
USER_TOKEN="your_user_token_here"
```

## 1. Create Advertisement (Admin Only)
```bash
curl -X POST "$BASE_URL/ads/" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Premium Office Solutions",
    "content": "Get the best office equipment and furniture for your business. Special discounts available!",
    "image_url": "https://example.com/office-ad.jpg",
    "target_industries": ["technology", "software", "consulting"]
  }'
```

## 2. Try Creating Ad as Regular User (Should Fail)
```bash
curl -X POST "$BASE_URL/ads/" \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Ad",
    "content": "This should fail"
  }'
```

## 3. Get Targeted Ads
```bash
curl -X GET "$BASE_URL/ads/targeted" \
  -H "Authorization: Bearer $USER_TOKEN"
```

## 4. Get Targeted Ads with Limit
```bash
curl -X GET "$BASE_URL/ads/targeted?limit=3" \
  -H "Authorization: Bearer $USER_TOKEN"
```

## Expected Responses

### Create Ad Success (Admin):
```json
{
  "id": 1,
  "title": "Premium Office Solutions",
  "content": "Get the best office equipment...",
  "image_url": "https://example.com/office-ad.jpg",
  "target_industries": ["technology", "software", "consulting"],
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Create Ad Failure (User):
```json
{
  "detail": "Only admins can create advertisements"
}
```

### Targeted Ads:
```json
[
  {
    "id": 1,
    "title": "Premium Office Solutions",
    "content": "Get the best office equipment...",
    "image_url": "https://example.com/office-ad.jpg",
    "target_industries": ["technology", "software", "consulting"],
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```