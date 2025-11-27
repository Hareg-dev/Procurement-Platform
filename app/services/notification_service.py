"""
Real-time notification service for enhanced user experience
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.orm import User, RFQ, Bid, UserRole, RFQStatus
from app.models.dashboard import NotificationItem


class NotificationService:
    """Service for managing user notifications"""

    async def get_user_notifications(
        self, 
        db: AsyncSession, 
        user: User, 
        limit: int = 20
    ) -> List[NotificationItem]:
        """Get notifications for a specific user"""
        
        notifications = []
        
        if user.role == UserRole.BUYER:
            notifications.extend(await self._get_buyer_notifications(db, user, limit))
        elif user.role == UserRole.SUPPLIER:
            notifications.extend(await self._get_supplier_notifications(db, user, limit))
        elif user.role == UserRole.ADMIN:
            notifications.extend(await self._get_admin_notifications(db, user, limit))
        
        # Sort by timestamp (newest first)
        notifications.sort(key=lambda x: x.timestamp, reverse=True)
        
        return notifications[:limit]

    async def _get_buyer_notifications(
        self, 
        db: AsyncSession, 
        user: User, 
        limit: int
    ) -> List[NotificationItem]:
        """Get buyer-specific notifications"""
        
        notifications = []
        
        # New bids on RFQs
        recent_bids = await db.execute(
            select(Bid, RFQ.title)
            .join(RFQ)
            .where(and_(
                RFQ.buyer_company_id == user.company_id,
                Bid.created_at >= datetime.now() - timedelta(days=7)
            ))
            .order_by(desc(Bid.created_at))
            .limit(10)
        )
        
        for bid, rfq_title in recent_bids:
            notifications.append(NotificationItem(
                id=f"bid_{bid.id}",
                title="New Bid Received",
                message=f"New bid received for '{rfq_title}'",
                type="info",
                timestamp=bid.created_at,
                read=False,
                url=f"/rfqs/{bid.rfq_id}"
            ))
        
        # Approaching deadlines
        approaching_deadlines = await db.execute(
            select(RFQ)
            .where(and_(
                RFQ.buyer_company_id == user.company_id,
                RFQ.status == RFQStatus.OPEN,
                RFQ.deadline <= datetime.now() + timedelta(days=3),
                RFQ.deadline > datetime.now()
            ))
        )
        
        for rfq in approaching_deadlines:
            days_left = (rfq.deadline - datetime.now()).days
            notifications.append(NotificationItem(
                id=f"deadline_{rfq.id}",
                title="Deadline Approaching",
                message=f"'{rfq.title}' deadline in {days_left} day{'s' if days_left != 1 else ''}",
                type="warning",
                timestamp=datetime.now(),
                read=False,
                url=f"/rfqs/{rfq.id}"
            ))
        
        return notifications

    async def _get_supplier_notifications(
        self, 
        db: AsyncSession, 
        user: User, 
        limit: int
    ) -> List[NotificationItem]:
        """Get supplier-specific notifications"""
        
        notifications = []
        
        # Bid status updates
        recent_bid_updates = await db.execute(
            select(Bid, RFQ.title)
            .join(RFQ)
            .where(and_(
                Bid.supplier_company_id == user.company_id,
                Bid.updated_at >= datetime.now() - timedelta(days=7)
            ))
            .order_by(desc(Bid.updated_at))
            .limit(5)
        )
        
        for bid, rfq_title in recent_bid_updates:
            if bid.is_selected:
                notifications.append(NotificationItem(
                    id=f"bid_won_{bid.id}",
                    title="Bid Selected! 🎉",
                    message=f"Your bid for '{rfq_title}' was selected",
                    type="success",
                    timestamp=bid.updated_at,
                    read=False,
                    url=f"/bids/{bid.id}"
                ))
        
        # New matching RFQs (simplified)
        new_rfqs = await db.execute(
            select(RFQ, Company.name)
            .join(Company, RFQ.buyer_company_id == Company.id)
            .where(and_(
                RFQ.status == RFQStatus.OPEN,
                RFQ.buyer_company_id != user.company_id,
                RFQ.created_at >= datetime.now() - timedelta(days=3),
                RFQ.deadline > datetime.now()
            ))
            .order_by(desc(RFQ.created_at))
            .limit(3)
        )
        
        for rfq, company_name in new_rfqs:
            notifications.append(NotificationItem(
                id=f"new_rfq_{rfq.id}",
                title="New Opportunity",
                message=f"New RFQ from {company_name}: '{rfq.title}'",
                type="info",
                timestamp=rfq.created_at,
                read=False,
                url=f"/rfqs/{rfq.id}"
            ))
        
        return notifications

    async def _get_admin_notifications(
        self, 
        db: AsyncSession, 
        user: User, 
        limit: int
    ) -> List[NotificationItem]:
        """Get admin-specific notifications"""
        
        notifications = []
        
        # New user registrations
        new_users = await db.execute(
            select(User, Company.name)
            .join(Company)
            .where(and_(
                User.created_at >= datetime.now() - timedelta(days=7),
                User.is_verified == False
            ))
            .order_by(desc(User.created_at))
            .limit(5)
        )
        
        for new_user, company_name in new_users:
            notifications.append(NotificationItem(
                id=f"new_user_{new_user.id}",
                title="New User Registration",
                message=f"{new_user.first_name} {new_user.last_name} from {company_name} needs verification",
                type="info",
                timestamp=new_user.created_at,
                read=False,
                url=f"/admin/users/{new_user.id}"
            ))
        
        # High-value RFQs
        high_value_rfqs = await db.execute(
            select(RFQ, Company.name)
            .join(Company, RFQ.buyer_company_id == Company.id)
            .where(and_(
                RFQ.budget_max >= 50000,
                RFQ.created_at >= datetime.now() - timedelta(days=3)
            ))
            .order_by(desc(RFQ.created_at))
            .limit(3)
        )
        
        for rfq, company_name in high_value_rfqs:
            notifications.append(NotificationItem(
                id=f"high_value_{rfq.id}",
                title="High-Value RFQ",
                message=f"${rfq.budget_max:,.0f} RFQ from {company_name}",
                type="info",
                timestamp=rfq.created_at,
                read=False,
                url=f"/admin/rfqs/{rfq.id}"
            ))
        
        return notifications

    async def mark_notification_read(
        self, 
        db: AsyncSession, 
        user: User, 
        notification_id: str
    ) -> bool:
        """Mark a notification as read"""
        # TODO: Implement actual notification storage and marking
        # For now, just return success
        return True

    async def get_unread_count(self, db: AsyncSession, user: User) -> int:
        """Get count of unread notifications"""
        notifications = await self.get_user_notifications(db, user, 50)
        return len([n for n in notifications if not n.read])

    async def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "info",
        url: Optional[str] = None
    ) -> NotificationItem:
        """Create a new notification"""
        # TODO: Store in database
        return NotificationItem(
            id=f"custom_{datetime.now().timestamp()}",
            title=title,
            message=message,
            type=notification_type,
            timestamp=datetime.now(),
            read=False,
            url=url
        )


# Service instance
notification_service = NotificationService()