from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User, UserRole
from app.models.domain import AdvertisementCreate, AdvertisementResponse
from app.repositories.ad_repo import ad_repository
from app.services.llm_service import llm_service


class AdService:
    """Service for Advertisement operations."""

    def __init__(self):
        self.ad_repo = ad_repository
        self.llm_service = llm_service

    async def create_ad(
        self, db: AsyncSession, *, ad_in: AdvertisementCreate, current_user: User
    ) -> AdvertisementResponse:
        """
        Create a new advertisement (Admin only).

        Args:
            db: Database session
            ad_in: Advertisement creation data
            current_user: Current authenticated user

        Returns:
            AdvertisementResponse: Created advertisement

        Raises:
            HTTPException: If user is not an admin
        """
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create advertisements",
            )

        ad = await self.ad_repo.create(db, obj_in=ad_in)
        return AdvertisementResponse.from_orm(ad)

    async def get_targeted_ads(
        self, db: AsyncSession, *, current_user: User, limit: int = 5
    ) -> List[AdvertisementResponse]:
        """
        Get targeted ads for the current user based on their company's industry.

        Args:
            db: Database session
            current_user: Current authenticated user
            limit: Maximum number of ads to return

        Returns:
            List[AdvertisementResponse]: List of targeted advertisements
        """
        # 1. Get user's company description
        if not current_user.company or not current_user.company.description:
            # Fallback to generic ads if no company info
            ads = await self.ad_repo.get_multi(db, limit=limit)
            return [AdvertisementResponse.from_orm(ad) for ad in ads]

        # 2. Extract industries using LLM
        # We could cache this result in the future
        industries = await self.llm_service.extract_company_industry(
            current_user.company.description
        )

        if not industries:
            ads = await self.ad_repo.get_multi(db, limit=limit)
            return [AdvertisementResponse.from_orm(ad) for ad in ads]

        # 3. Get matching ads
        ads = await self.ad_repo.get_by_industries(
            db, industries=industries, limit=limit
        )

        # If not enough targeted ads, fill with generic ones
        if len(ads) < limit:
            generic_ads = await self.ad_repo.get_multi(db, limit=limit - len(ads))
            # Avoid duplicates
            existing_ids = {ad.id for ad in ads}
            for ad in generic_ads:
                if ad.id not in existing_ids:
                    ads.append(ad)

        return [AdvertisementResponse.from_orm(ad) for ad in ads]


ad_service = AdService()
