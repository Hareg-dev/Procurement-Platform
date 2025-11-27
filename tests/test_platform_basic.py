"""
Simple test to verify the platform imports and basic functionality work.
This test doesn't require a database connection.
"""

import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Testing Procurement Platform...")
print("=" * 50)

# Test 1: Import core modules
print("\n✓ Test 1: Importing core modules...")
try:
    from app.core.config import settings
    from app.models.orm import Advertisement, User, Company, RFQ, Bid
    from app.models.domain import AdvertisementCreate, AdvertisementResponse

    print("  ✅ All core modules imported successfully")
except Exception as e:
    print(f"  ❌ Failed to import modules: {e}")
    sys.exit(1)

# Test 2: Check Ollama configuration
print("\n✓ Test 2: Checking Ollama configuration...")
try:
    print(f"  - Ollama URL: {settings.ollama_base_url}")
    print(f"  - Ollama Model: {settings.ollama_model}")
    print(f"  - Temperature: {settings.ollama_temperature}")
    print("  ✅ Ollama configuration loaded")
except Exception as e:
    print(f"  ❌ Failed to load config: {e}")
    sys.exit(1)

# Test 3: Test Advertisement model
print("\n✓ Test 3: Testing Advertisement model...")
try:
    # Create a mock advertisement
    ad_data = AdvertisementCreate(
        title="Test Medical Equipment",
        content="High-quality medical supplies",
        image_url="https://example.com/image.jpg",
        target_industries=["Healthcare", "Medical"],
    )
    print(f"  - Title: {ad_data.title}")
    print(f"  - Target Industries: {ad_data.target_industries}")
    print("  ✅ Advertisement model works correctly")
except Exception as e:
    print(f"  ❌ Failed to create advertisement: {e}")
    sys.exit(1)

# Test 4: Import services
print("\n✓ Test 4: Importing services...")
try:
    from app.services.llm_service import llm_service
    from app.services.ad_service import ad_service

    print("  ✅ All services imported successfully")
except Exception as e:
    print(f"  ❌ Failed to import services: {e}")
    sys.exit(1)

# Test 5: Import API endpoints
print("\n✓ Test 5: Importing API endpoints...")
try:
    from app.api.v1.endpoints import ads
    from app.api.v1 import api

    print("  ✅ All API endpoints imported successfully")
except Exception as e:
    print(f"  ❌ Failed to import API: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("✅ ALL TESTS PASSED!")
print("\nThe platform is ready to use. To run it:")
print("1. Ensure PostgreSQL is running and create 'procurement_db' database")
print("2. Run: uv run alembic upgrade head")
print("3. Start Ollama: ollama serve")
print("4. Run: uv run uvicorn app.main:app --reload")
