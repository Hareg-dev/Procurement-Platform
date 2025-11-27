import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from unittest.mock import AsyncMock, MagicMock
from app.services.ad_service import AdService
from app.models.orm import User, Company, UserRole, Advertisement


async def test_targeted_ads():
    print("Testing Targeted Ads Feature...")

    # Mock dependencies
    mock_db = AsyncMock()
    mock_ad_repo = AsyncMock()
    mock_llm_service = AsyncMock()

    # Initialize service with mocks
    service = AdService()
    service.ad_repo = mock_ad_repo
    service.llm_service = mock_llm_service

    # Test Case 1: User with company description getting targeted ads
    print("\nTest Case 1: User with company description")
    user = User(
        id=1,
        role=UserRole.BUYER,
        company=Company(description="We are a hospital needing medical supplies."),
    )

    # Mock LLM response
    mock_llm_service.extract_company_industry.return_value = ["Healthcare", "Medical"]

    # Mock Ad Repo response
    mock_ad = Advertisement(
        id=1,
        title="Medical Equipment Sale",
        content="Best medical equipment",
        target_industries=["Healthcare"],
    )
    mock_ad_repo.get_by_industries.return_value = [mock_ad]

    ads = await service.get_targeted_ads(mock_db, current_user=user)

    print(f"User Company: {user.company.description}")
    print(
        f"Identified Industries: {mock_llm_service.extract_company_industry.return_value}"
    )
    print(f"Returned Ads: {[ad.title for ad in ads]}")

    assert len(ads) == 1
    assert ads[0].title == "Medical Equipment Sale"
    print("✅ Test Case 1 Passed")

    # Test Case 2: User without company description (Generic ads)
    print("\nTest Case 2: User without company description")
    user_no_desc = User(id=2, role=UserRole.BUYER, company=Company(description=""))

    mock_generic_ad = Advertisement(
        id=2,
        title="Generic Office Supplies",
        content="Paper and pens",
        target_industries=[],
    )
    mock_ad_repo.get_multi.return_value = [mock_generic_ad]

    ads_generic = await service.get_targeted_ads(mock_db, current_user=user_no_desc)

    print(f"User Company Description: '{user_no_desc.company.description}'")
    print(f"Returned Ads: {[ad.title for ad in ads_generic]}")

    assert len(ads_generic) == 1
    assert ads_generic[0].title == "Generic Office Supplies"
    print("✅ Test Case 2 Passed")


if __name__ == "__main__":
    asyncio.run(test_targeted_ads())
