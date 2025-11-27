"""
Dashboard domain models for enhanced user experience
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.orm import UserRole, RFQStatus


class QuickAction(BaseModel):
    """Quick action button for dashboard"""
    label: str
    url: str
    icon: str
    primary: bool = False


class DashboardMetric(BaseModel):
    """Dashboard metric display"""
    label: str
    value: str
    change: Optional[str] = None
    trend: Optional[str] = None  # "up", "down", "stable"


class ActivityItem(BaseModel):
    """Recent activity item"""
    title: str
    description: str
    timestamp: datetime
    type: str  # "rfq", "bid", "award", "message"
    url: Optional[str] = None


class OpportunityItem(BaseModel):
    """Opportunity for suppliers"""
    rfq_id: int
    title: str
    budget_range: str
    deadline: datetime
    match_score: Optional[float] = None
    company_name: str


class RFQSummary(BaseModel):
    """RFQ summary for buyers"""
    rfq_id: int
    title: str
    status: RFQStatus
    bid_count: int
    deadline: datetime
    needs_attention: bool = False


class BidSummary(BaseModel):
    """Bid summary for suppliers"""
    bid_id: int
    rfq_title: str
    price: float
    status: str  # "pending", "selected", "rejected"
    submitted_at: datetime


class BuyerDashboard(BaseModel):
    """Buyer dashboard data"""
    user_name: str
    company_name: str
    quick_actions: List[QuickAction]
    metrics: List[DashboardMetric]
    active_rfqs: List[RFQSummary]
    pending_decisions: List[RFQSummary]
    recent_activity: List[ActivityItem]
    ai_recommendations: List[str]


class SupplierDashboard(BaseModel):
    """Supplier dashboard data"""
    user_name: str
    company_name: str
    quick_actions: List[QuickAction]
    metrics: List[DashboardMetric]
    matched_opportunities: List[OpportunityItem]
    my_bids: List[BidSummary]
    performance_score: Optional[float] = None
    recent_activity: List[ActivityItem]


class AdminDashboard(BaseModel):
    """Admin dashboard data"""
    platform_metrics: List[DashboardMetric]
    today_activity: Dict[str, int]
    platform_health: Dict[str, Any]
    pending_actions: List[ActivityItem]
    system_alerts: List[str]
    recent_activity: List[ActivityItem]


class NotificationItem(BaseModel):
    """Notification item"""
    id: int
    title: str
    message: str
    type: str  # "info", "warning", "success", "error"
    timestamp: datetime
    read: bool = False
    url: Optional[str] = None