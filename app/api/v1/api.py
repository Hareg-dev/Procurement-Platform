from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, rfqs, bids, public, chat, ads, dashboard, recommendations, messages

api_router = APIRouter()

# Authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# User management routes
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Dashboard routes
api_router.include_router(dashboard.router, tags=["dashboard"])

# AI Recommendations routes
api_router.include_router(recommendations.router, tags=["recommendations"])

# RFQ routes
api_router.include_router(rfqs.router, prefix="/rfqs", tags=["rfqs"])

# Bid routes (includes both /rfqs/{rfq_id}/bids and /bids endpoints)
api_router.include_router(bids.router, tags=["bids"])

# Public routes (unauthenticated marketplace endpoints)
api_router.include_router(public.router, prefix="/public", tags=["public"])

# AI Chat WebSocket routes
api_router.include_router(chat.router, prefix="/chat", tags=["ai-chat"])

# Advertisement routes
api_router.include_router(ads.router, prefix="/ads", tags=["ads"])

# Direct messaging routes
api_router.include_router(messages.router, prefix="/messages", tags=["messaging"])
