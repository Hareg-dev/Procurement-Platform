from fastapi import APIRouter

from app.api.v2.endpoints import (
    approvals,
    audit,
    budgets,
    policies,
    requisitions,
    sourcing,
)

api_v2_router = APIRouter()

api_v2_router.include_router(requisitions.router)
api_v2_router.include_router(approvals.router)
api_v2_router.include_router(budgets.router)
api_v2_router.include_router(policies.router)
api_v2_router.include_router(audit.router)
api_v2_router.include_router(sourcing.router)
