from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List

from app.api.v1.dependencies import get_current_user
from app.core.db import get_db
from app.models.orm import User, Company

router = APIRouter()

@router.get("/search")
async def search_users(
    q: str = Query(..., min_length=2, description="Search query"),
    role: str = Query(None, description="Filter by role: supplier, buyer, admin"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Search users for messaging"""
    
    query = select(User, Company).join(Company).where(
        User.id != current_user.id,
        User.is_active == True,
        or_(
            User.first_name.ilike(f"%{q}%"),
            User.last_name.ilike(f"%{q}%"),
            Company.name.ilike(f"%{q}%")
        )
    )
    
    if role:
        query = query.where(User.role == role.upper())
    
    result = await db.execute(query.limit(20))
    rows = result.all()
    
    return [
        {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "company": company.name,
            "role": user.role.lower()
        }
        for user, company in rows
    ]