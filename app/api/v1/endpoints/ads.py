from typing import List

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_admin
from app.core.db import get_db
from app.models.domain import AdvertisementCreate, AdvertisementResponse
from app.models.orm import User
from app.services.ad_service import ad_service

router = APIRouter()


@router.post(
    "/", response_model=AdvertisementResponse, status_code=status.HTTP_201_CREATED
)
async def create_advertisement(
    *,
    db: AsyncSession = Depends(get_db),
    ad_in: AdvertisementCreate,
    current_user: User = Depends(require_admin),
):
    """
    Create a new advertisement.

    Requires admin privileges.
    """
    return await ad_service.create_ad(db, ad_in=ad_in, current_user=current_user)


@router.post("/client-request", response_model=dict)
async def request_advertisement(
    *,
    db: AsyncSession = Depends(get_db),
    ad_in: AdvertisementCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Submit advertisement request for admin approval.
    
    Clients can request ads that admins review and approve.
    """
    return await ad_service.request_ad(db, ad_in=ad_in, current_user=current_user)


@router.get("/pending", response_model=List[dict])
async def get_pending_ads(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Get pending advertisement requests for admin approval.
    """
    return await ad_service.get_pending_ads(db)


@router.post("/approve/{ad_id}")
async def approve_advertisement(
    *,
    db: AsyncSession = Depends(get_db),
    ad_id: int,
    current_user: User = Depends(require_admin),
):
    """
    Approve a pending advertisement request.
    """
    try:
        return await ad_service.approve_ad(db, ad_id=ad_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve advertisement: {str(e)}"
        )


@router.get("/targeted", response_model=List[AdvertisementResponse])
async def get_targeted_ads(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 5,
):
    """
    Get targeted advertisements for the current user.

    Uses AI to match user's company industry with advertisement target industries.
    """
    return await ad_service.get_targeted_ads(db, current_user=current_user, limit=limit)
