from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Advertisement
from app.models.domain import AdvertisementCreate, AdvertisementUpdate
from app.repositories.base import BaseRepository


class AdRepository(
    BaseRepository[Advertisement, AdvertisementCreate, AdvertisementUpdate]
):
    """Repository for Advertisement operations."""

    async def get_by_industries(
        self, db: AsyncSession, industries: List[str], limit: int = 10
    ) -> List[Advertisement]:
        """
        Get ads that match any of the provided industries.

        Args:
            db: Database session
            industries: List of industries to match
            limit: Maximum number of ads to return

        Returns:
            List[Advertisement]: List of matching advertisements
        """
        # Fetch all ads (assuming small number for MVP) and filter in Python
        # In a real production app with many ads, this should be done in SQL
        # using PostgreSQL's JSONB operators (e.g., ?| array['ind1', 'ind2'])
        result = await db.execute(select(self.model))
        all_ads = result.scalars().all()

        matched_ads = []
        normalized_industries = {ind.lower() for ind in industries}

        for ad in all_ads:
            # Check if any of the ad's target industries match the requested industries
            ad_industries = {ind.lower() for ind in ad.target_industries}
            if not ad_industries or ad_industries.intersection(normalized_industries):
                matched_ads.append(ad)

        return matched_ads[:limit]


ad_repository = AdRepository(Advertisement)
