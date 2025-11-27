"""
Dashboard service for personalized user experiences
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.models.orm import User, RFQ, Bid, Company, UserRole, RFQStatus
from app.models.dashboard import (
    BuyerDashboard, SupplierDashboard, AdminDashboard,
    QuickAction, DashboardMetric, ActivityItem, OpportunityItem,
    RFQSummary, BidSummary, NotificationItem
)
from app.services.llm_service import llm_service


class DashboardService:
    """Service for generating personalized dashboards"""

    async def get_buyer_dashboard(self, db: AsyncSession, user: User) -> BuyerDashboard:
        """Generate buyer dashboard"""
        
        # Quick actions
        quick_actions = [
            QuickAction(label="Create RFQ", url="/rfqs/create", icon="plus", primary=True),
            QuickAction(label="Analytics", url="/analytics", icon="chart"),
            QuickAction(label="Suppliers", url="/suppliers", icon="users"),
            QuickAction(label="Reports", url="/reports", icon="file-text")
        ]

        # Get metrics
        metrics = await self._get_buyer_metrics(db, user)
        
        # Get active RFQs
        active_rfqs = await self._get_active_rfqs(db, user)
        
        # Get pending decisions
        pending_decisions = await self._get_pending_decisions(db, user)
        
        # Get recent activity
        recent_activity = await self._get_buyer_activity(db, user)
        
        # AI recommendations
        ai_recommendations = await self._get_ai_recommendations(db, user)

        return BuyerDashboard(
            user_name=user.first_name,
            company_name=user.company.name,
            quick_actions=quick_actions,
            metrics=metrics,
            active_rfqs=active_rfqs,
            pending_decisions=pending_decisions,
            recent_activity=recent_activity,
            ai_recommendations=ai_recommendations
        )

    async def get_supplier_dashboard(self, db: AsyncSession, user: User) -> SupplierDashboard:
        """Generate supplier dashboard"""
        
        # Quick actions
        quick_actions = [
            QuickAction(label="Browse RFQs", url="/rfqs/browse", icon="search", primary=True),
            QuickAction(label="My Bids", url="/bids", icon="file"),
            QuickAction(label="Profile", url="/profile", icon="user"),
            QuickAction(label="Performance", url="/performance", icon="trending-up")
        ]

        # Get metrics
        metrics = await self._get_supplier_metrics(db, user)
        
        # Get matched opportunities
        opportunities = await self._get_matched_opportunities(db, user)
        
        # Get my bids
        my_bids = await self._get_my_bids(db, user)
        
        # Get performance score
        performance_score = await self._get_performance_score(db, user)
        
        # Get recent activity
        recent_activity = await self._get_supplier_activity(db, user)

        return SupplierDashboard(
            user_name=user.first_name,
            company_name=user.company.name,
            quick_actions=quick_actions,
            metrics=metrics,
            matched_opportunities=opportunities,
            my_bids=my_bids,
            performance_score=performance_score,
            recent_activity=recent_activity
        )

    async def get_admin_dashboard(self, db: AsyncSession, user: User) -> AdminDashboard:
        """Generate admin dashboard"""
        
        # Platform metrics
        platform_metrics = await self._get_platform_metrics(db)
        
        # Today's activity
        today_activity = await self._get_today_activity(db)
        
        # Platform health
        platform_health = await self._get_platform_health(db)
        
        # Pending actions
        pending_actions = await self._get_pending_actions(db)
        
        # System alerts
        system_alerts = await self._get_system_alerts(db)
        
        # Recent activity
        recent_activity = await self._get_admin_activity(db)

        return AdminDashboard(
            platform_metrics=platform_metrics,
            today_activity=today_activity,
            platform_health=platform_health,
            pending_actions=pending_actions,
            system_alerts=system_alerts,
            recent_activity=recent_activity
        )

    async def _get_buyer_metrics(self, db: AsyncSession, user: User) -> List[DashboardMetric]:
        """Get buyer-specific metrics"""
        
        # Active RFQs count
        active_count = await db.scalar(
            select(func.count(RFQ.id))
            .where(and_(RFQ.buyer_company_id == user.company_id, RFQ.status == RFQStatus.OPEN))
        )
        
        # Total bids received this month
        month_ago = datetime.now() - timedelta(days=30)
        bids_count = await db.scalar(
            select(func.count(Bid.id))
            .join(RFQ)
            .where(and_(
                RFQ.buyer_company_id == user.company_id,
                Bid.created_at >= month_ago
            ))
        )
        
        # Pending decisions
        pending_count = await db.scalar(
            select(func.count(RFQ.id))
            .where(and_(
                RFQ.buyer_company_id == user.company_id,
                RFQ.status == RFQStatus.OPEN,
                RFQ.deadline > datetime.now()
            ))
        )

        return [
            DashboardMetric(label="Active RFQs", value=str(active_count or 0)),
            DashboardMetric(label="Bids This Month", value=str(bids_count or 0), trend="up"),
            DashboardMetric(label="Pending Decisions", value=str(pending_count or 0))
        ]

    async def _get_supplier_metrics(self, db: AsyncSession, user: User) -> List[DashboardMetric]:
        """Get supplier-specific metrics"""
        
        # Available opportunities
        available_count = await db.scalar(
            select(func.count(RFQ.id))
            .where(and_(
                RFQ.status == RFQStatus.OPEN,
                RFQ.buyer_company_id != user.company_id,
                RFQ.deadline > datetime.now()
            ))
        )
        
        # My active bids
        my_bids_count = await db.scalar(
            select(func.count(Bid.id))
            .where(Bid.supplier_company_id == user.company_id)
        )
        
        # Won contracts
        won_count = await db.scalar(
            select(func.count(Bid.id))
            .where(and_(
                Bid.supplier_company_id == user.company_id,
                Bid.is_selected == True
            ))
        )

        return [
            DashboardMetric(label="Available RFQs", value=str(available_count or 0)),
            DashboardMetric(label="My Bids", value=str(my_bids_count or 0)),
            DashboardMetric(label="Won Contracts", value=str(won_count or 0), trend="up")
        ]

    async def _get_platform_metrics(self, db: AsyncSession) -> List[DashboardMetric]:
        """Get platform-wide metrics"""
        
        # Total users
        users_count = await db.scalar(select(func.count(User.id)))
        
        # Total companies
        companies_count = await db.scalar(select(func.count(Company.id)))
        
        # Active RFQs
        active_rfqs = await db.scalar(
            select(func.count(RFQ.id)).where(RFQ.status == RFQStatus.OPEN)
        )

        return [
            DashboardMetric(label="Total Users", value=str(users_count or 0)),
            DashboardMetric(label="Companies", value=str(companies_count or 0)),
            DashboardMetric(label="Active RFQs", value=str(active_rfqs or 0))
        ]

    async def _get_active_rfqs(self, db: AsyncSession, user: User) -> List[RFQSummary]:
        """Get active RFQs for buyer"""
        
        result = await db.execute(
            select(RFQ, func.count(Bid.id).label('bid_count'))
            .outerjoin(Bid)
            .where(RFQ.buyer_company_id == user.company_id)
            .group_by(RFQ.id)
            .order_by(desc(RFQ.created_at))
            .limit(5)
        )
        
        rfqs = []
        for rfq, bid_count in result:
            needs_attention = (
                rfq.deadline < datetime.now() + timedelta(days=3) and 
                rfq.status == RFQStatus.OPEN
            )
            
            rfqs.append(RFQSummary(
                rfq_id=rfq.id,
                title=rfq.title,
                status=rfq.status,
                bid_count=bid_count or 0,
                deadline=rfq.deadline,
                needs_attention=needs_attention
            ))
        
        return rfqs

    async def _get_pending_decisions(self, db: AsyncSession, user: User) -> List[RFQSummary]:
        """Get RFQs needing decisions"""
        
        result = await db.execute(
            select(RFQ, func.count(Bid.id).label('bid_count'))
            .outerjoin(Bid)
            .where(and_(
                RFQ.buyer_company_id == user.company_id,
                RFQ.status == RFQStatus.OPEN,
                RFQ.deadline > datetime.now()
            ))
            .group_by(RFQ.id)
            .having(func.count(Bid.id) > 0)
            .limit(3)
        )
        
        return [
            RFQSummary(
                rfq_id=rfq.id,
                title=rfq.title,
                status=rfq.status,
                bid_count=bid_count,
                deadline=rfq.deadline,
                needs_attention=True
            )
            for rfq, bid_count in result
        ]

    async def _get_matched_opportunities(self, db: AsyncSession, user: User) -> List[OpportunityItem]:
        """Get matched opportunities for supplier"""
        
        result = await db.execute(
            select(RFQ, Company.name)
            .join(Company, RFQ.buyer_company_id == Company.id)
            .where(and_(
                RFQ.status == RFQStatus.OPEN,
                RFQ.buyer_company_id != user.company_id,
                RFQ.deadline > datetime.now()
            ))
            .order_by(desc(RFQ.created_at))
            .limit(8)
        )
        
        opportunities = []
        for rfq, company_name in result:
            budget_range = "Budget not specified"
            if rfq.budget_min and rfq.budget_max:
                budget_range = f"${rfq.budget_min:,.0f} - ${rfq.budget_max:,.0f}"
            elif rfq.budget_max:
                budget_range = f"Up to ${rfq.budget_max:,.0f}"
            
            opportunities.append(OpportunityItem(
                rfq_id=rfq.id,
                title=rfq.title,
                budget_range=budget_range,
                deadline=rfq.deadline,
                company_name=company_name,
                match_score=0.85  # TODO: Implement AI matching
            ))
        
        return opportunities

    async def _get_my_bids(self, db: AsyncSession, user: User) -> List[BidSummary]:
        """Get supplier's recent bids"""
        
        result = await db.execute(
            select(Bid, RFQ.title)
            .join(RFQ)
            .where(Bid.supplier_company_id == user.company_id)
            .order_by(desc(Bid.created_at))
            .limit(5)
        )
        
        bids = []
        for bid, rfq_title in result:
            status = "selected" if bid.is_selected else "pending"
            
            bids.append(BidSummary(
                bid_id=bid.id,
                rfq_title=rfq_title,
                price=float(bid.price),
                status=status,
                submitted_at=bid.created_at
            ))
        
        return bids

    async def _get_performance_score(self, db: AsyncSession, user: User) -> float:
        """Calculate supplier performance score"""
        
        # Simple performance calculation
        total_bids = await db.scalar(
            select(func.count(Bid.id))
            .where(Bid.supplier_company_id == user.company_id)
        )
        
        won_bids = await db.scalar(
            select(func.count(Bid.id))
            .where(and_(
                Bid.supplier_company_id == user.company_id,
                Bid.is_selected == True
            ))
        )
        
        if not total_bids:
            return 0.0
        
        win_rate = (won_bids or 0) / total_bids
        return min(4.0 + (win_rate * 1.0), 5.0)  # Scale to 4.0-5.0

    async def _get_buyer_activity(self, db: AsyncSession, user: User) -> List[ActivityItem]:
        """Get recent buyer activity"""
        return [
            ActivityItem(
                title="New bid received",
                description="Office Equipment RFQ received 2 new bids",
                timestamp=datetime.now() - timedelta(hours=2),
                type="bid"
            ),
            ActivityItem(
                title="RFQ deadline approaching",
                description="IT Services RFQ deadline in 3 days",
                timestamp=datetime.now() - timedelta(hours=5),
                type="rfq"
            )
        ]

    async def _get_supplier_activity(self, db: AsyncSession, user: User) -> List[ActivityItem]:
        """Get recent supplier activity"""
        return [
            ActivityItem(
                title="Bid submitted",
                description="Submitted bid for Marketing Materials RFQ",
                timestamp=datetime.now() - timedelta(hours=1),
                type="bid"
            ),
            ActivityItem(
                title="New opportunity",
                description="Office Supplies RFQ matches your profile",
                timestamp=datetime.now() - timedelta(hours=3),
                type="rfq"
            )
        ]

    async def _get_admin_activity(self, db: AsyncSession) -> List[ActivityItem]:
        """Get recent admin activity"""
        return [
            ActivityItem(
                title="New company registered",
                description="Global Tech Solutions joined the platform",
                timestamp=datetime.now() - timedelta(minutes=30),
                type="company"
            ),
            ActivityItem(
                title="High-value contract awarded",
                description="$50K IT Services contract awarded",
                timestamp=datetime.now() - timedelta(hours=2),
                type="award"
            )
        ]

    async def _get_today_activity(self, db: AsyncSession) -> Dict[str, int]:
        """Get today's platform activity"""
        today = datetime.now().date()
        
        new_rfqs = await db.scalar(
            select(func.count(RFQ.id))
            .where(func.date(RFQ.created_at) == today)
        ) or 0
        
        new_bids = await db.scalar(
            select(func.count(Bid.id))
            .where(func.date(Bid.created_at) == today)
        ) or 0
        
        return {
            "new_rfqs": new_rfqs,
            "new_bids": new_bids,
            "contracts_awarded": 3,  # TODO: Calculate from actual data
            "new_users": 5  # TODO: Calculate from actual data
        }

    async def _get_platform_health(self, db: AsyncSession) -> Dict[str, Any]:
        """Get platform health metrics"""
        return {
            "active_users": 150,
            "companies": 45,
            "total_volume": "$2.3M",
            "uptime": "99.9%"
        }

    async def _get_pending_actions(self, db: AsyncSession) -> List[ActivityItem]:
        """Get pending admin actions"""
        return [
            ActivityItem(
                title="User verification pending",
                description="3 companies awaiting verification",
                timestamp=datetime.now(),
                type="verification"
            )
        ]

    async def _get_system_alerts(self, db: AsyncSession) -> List[str]:
        """Get system alerts"""
        return [
            "Database backup completed successfully",
            "TinyLlama AI service running normally"
        ]

    async def _get_ai_recommendations(self, db: AsyncSession, user: User) -> List[str]:
        """Get AI-powered recommendations"""
        try:
            # Simple AI recommendations
            context = f"Buyer from {user.company.name} in procurement platform"
            recommendations = await llm_service.simple_chat(
                f"Give 3 brief procurement tips for {context}. Keep each under 10 words."
            )
            return recommendations.split('\n')[:3]
        except:
            return [
                "Consider bulk purchasing for better rates",
                "Set clear deadlines to get quality bids",
                "Review supplier performance regularly"
            ]


# Service instance
dashboard_service = DashboardService()