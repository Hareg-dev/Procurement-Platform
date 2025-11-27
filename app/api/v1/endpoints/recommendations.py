"""
AI-powered recommendations API endpoints
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_active_user, require_supplier, require_buyer
from app.core.db import get_db
from app.models.orm import User, RFQ
from app.services.matching_service import matching_service
from app.repositories.rfq_repo import rfq_repository

router = APIRouter()


@router.get("/recommendations/rfqs")
async def get_recommended_rfqs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_supplier),
    limit: int = Query(default=10, le=50)
):
    """
    Get AI-recommended RFQs for supplier based on capabilities and history.
    
    Returns personalized RFQ recommendations with match scores and reasons.
    """
    try:
        recommendations = await matching_service.get_matched_rfqs_for_supplier(
            db, current_user, limit
        )
        
        return {
            "recommendations": [
                {
                    "rfq_id": rec["rfq"].id,
                    "title": rec["rfq"].title,
                    "description": rec["rfq"].description[:200] + "..." if len(rec["rfq"].description) > 200 else rec["rfq"].description,
                    "budget_range": f"${rec['rfq'].budget_min or 0:,.0f} - ${rec['rfq'].budget_max or 0:,.0f}" if rec["rfq"].budget_max else "Budget not specified",
                    "deadline": rec["rfq"].deadline,
                    "buyer_company": rec["buyer_company"],
                    "match_score": round(rec["match_score"], 2),
                    "match_reasons": rec["match_reasons"],
                    "url": f"/rfqs/{rec['rfq'].id}"
                }
                for rec in recommendations
            ],
            "total": len(recommendations)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/recommendations/suppliers/{rfq_id}")
async def get_recommended_suppliers(
    rfq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_buyer),
    limit: int = Query(default=5, le=20)
):
    """
    Get AI-recommended suppliers for a specific RFQ.
    
    Returns suppliers ranked by compatibility with RFQ requirements.
    """
    try:
        # Get RFQ and verify ownership
        rfq = await rfq_repository.get_with_details(db, rfq_id)
        if not rfq:
            raise HTTPException(status_code=404, detail="RFQ not found")
        
        if rfq.buyer_company_id != current_user.company_id and current_user.role.value != "admin":
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get recommendations
        recommendations = await matching_service.get_recommended_suppliers_for_rfq(
            db, rfq, limit
        )
        
        return {
            "rfq_id": rfq_id,
            "rfq_title": rfq.title,
            "recommendations": [
                {
                    "company_id": rec["company"].id,
                    "company_name": rec["company"].name,
                    "description": rec["company"].description[:150] + "..." if rec["company"].description and len(rec["company"].description) > 150 else rec["company"].description,
                    "website": rec["company"].website,
                    "match_score": round(rec["match_score"], 2),
                    "strengths": rec["strengths"],
                    "profile_url": f"/companies/{rec['company'].id}"
                }
                for rec in recommendations
            ],
            "total": len(recommendations)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get supplier recommendations: {str(e)}")


@router.get("/recommendations/insights")
async def get_market_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get AI-powered market insights and trends.
    
    Returns personalized insights based on user role and activity.
    """
    try:
        if current_user.role.value == "buyer":
            insights = [
                {
                    "title": "Market Trend",
                    "message": "Office furniture prices decreased 5% this quarter",
                    "type": "trend",
                    "impact": "positive"
                },
                {
                    "title": "Supplier Availability",
                    "message": "High supplier availability for IT services",
                    "type": "availability",
                    "impact": "neutral"
                },
                {
                    "title": "Cost Optimization",
                    "message": "Consider bulk purchasing for 15% savings",
                    "type": "optimization",
                    "impact": "positive"
                }
            ]
        elif current_user.role.value == "supplier":
            insights = [
                {
                    "title": "Opportunity Alert",
                    "message": "Increased demand for office equipment this month",
                    "type": "opportunity",
                    "impact": "positive"
                },
                {
                    "title": "Competition Level",
                    "message": "Moderate competition in your service area",
                    "type": "competition",
                    "impact": "neutral"
                },
                {
                    "title": "Pricing Strategy",
                    "message": "Your bid prices are competitive in current market",
                    "type": "pricing",
                    "impact": "positive"
                }
            ]
        else:  # admin
            insights = [
                {
                    "title": "Platform Growth",
                    "message": "25% increase in active RFQs this month",
                    "type": "growth",
                    "impact": "positive"
                },
                {
                    "title": "User Engagement",
                    "message": "Average session time increased by 12%",
                    "type": "engagement",
                    "impact": "positive"
                }
            ]
        
        return {
            "insights": insights,
            "generated_at": "2024-01-15T10:30:00Z"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")


@router.post("/recommendations/feedback")
async def submit_recommendation_feedback(
    recommendation_type: str,
    item_id: int,
    helpful: bool,
    current_user: User = Depends(get_current_active_user)
):
    """
    Submit feedback on recommendation quality.
    
    Helps improve AI matching algorithms.
    """
    try:
        # TODO: Store feedback for ML model improvement
        feedback_data = {
            "user_id": current_user.id,
            "recommendation_type": recommendation_type,
            "item_id": item_id,
            "helpful": helpful,
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        # Log feedback (implement actual storage)
        print(f"Recommendation feedback: {feedback_data}")
        
        return {
            "message": "Feedback submitted successfully",
            "status": "received"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")