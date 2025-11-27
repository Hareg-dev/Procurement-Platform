"""
Dashboard API endpoints for enhanced user experience
"""

from typing import Union
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user
from app.core.db import get_db
from app.models.orm import User, UserRole
from app.models.dashboard import BuyerDashboard, SupplierDashboard, AdminDashboard, NotificationItem
from app.services.dashboard_service import dashboard_service
from app.services.notification_service import notification_service

router = APIRouter()


@router.get("/dashboard", response_model=Union[BuyerDashboard, SupplierDashboard, AdminDashboard])
async def get_user_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get personalized dashboard based on user role.
    
    Returns role-specific dashboard with:
    - Quick actions
    - Key metrics
    - Recent activity
    - Personalized recommendations
    """
    try:
        if current_user.role == UserRole.BUYER:
            return await dashboard_service.get_buyer_dashboard(db, current_user)
        elif current_user.role == UserRole.SUPPLIER:
            return await dashboard_service.get_supplier_dashboard(db, current_user)
        elif current_user.role == UserRole.ADMIN:
            return await dashboard_service.get_admin_dashboard(db, current_user)
        else:
            raise HTTPException(status_code=400, detail="Invalid user role")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dashboard: {str(e)}")


@router.get("/notifications")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get user notifications.
    
    Returns recent notifications for the current user.
    """
    try:
        notifications = await notification_service.get_user_notifications(db, current_user)
        unread_count = await notification_service.get_unread_count(db, current_user)
        
        return {
            "notifications": notifications,
            "unread_count": unread_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get notifications: {str(e)}")


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark notification as read"""
    try:
        success = await notification_service.mark_notification_read(db, current_user, notification_id)
        if success:
            return {"message": "Notification marked as read"}
        else:
            raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark notification: {str(e)}")


@router.get("/quick-stats")
async def get_quick_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get quick stats for header/sidebar display.
    
    Returns condensed metrics for quick reference.
    """
    if current_user.role == UserRole.BUYER:
        # Quick buyer stats
        return {
            "active_rfqs": 3,
            "pending_bids": 8,
            "this_month_savings": "$15,000"
        }
    elif current_user.role == UserRole.SUPPLIER:
        # Quick supplier stats
        return {
            "available_rfqs": 12,
            "my_bids": 5,
            "win_rate": "65%"
        }
    else:
        # Admin stats
        return {
            "platform_users": 150,
            "active_rfqs": 23,
            "today_volume": "$45,000"
        }