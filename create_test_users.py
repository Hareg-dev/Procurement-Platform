#!/usr/bin/env python3
"""
Create test users for advertisement system testing.
Run this to create admin and supplier users.
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import AsyncSessionLocal
from app.models.orm import User, Company, UserRole
from app.core.security import get_password_hash

async def create_test_users():
    """Create admin and supplier test users."""
    async with AsyncSessionLocal() as db:
        try:
            # Create Admin Company
            admin_company = Company(
                name="Platform Admin",
                description="System administration company",
                is_active=True
            )
            db.add(admin_company)
            await db.flush()
            
            # Create Admin User
            admin_user = User(
                email="admin@procurement.com",
                hashed_password=get_password_hash("admin123"),
                first_name="Admin",
                last_name="User",
                role=UserRole.ADMIN,
                company_id=admin_company.id,
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            
            # Create Supplier Company
            supplier_company = Company(
                name="TechSupply Corp",
                description="Technology equipment supplier specializing in IT hardware and software solutions",
                website="https://techsupply.com",
                is_active=True
            )
            db.add(supplier_company)
            await db.flush()
            
            # Create Supplier User
            supplier_user = User(
                email="supplier@techsupply.com",
                hashed_password=get_password_hash("supplier123"),
                first_name="John",
                last_name="Supplier",
                role=UserRole.SUPPLIER,
                company_id=supplier_company.id,
                is_active=True,
                is_verified=True
            )
            db.add(supplier_user)
            
            # Create Buyer Company
            buyer_company = Company(
                name="Manufacturing Inc",
                description="Large manufacturing company in automotive industry",
                is_active=True
            )
            db.add(buyer_company)
            await db.flush()
            
            # Create Buyer User
            buyer_user = User(
                email="buyer@manufacturing.com",
                hashed_password=get_password_hash("buyer123"),
                first_name="Jane",
                last_name="Buyer",
                role=UserRole.BUYER,
                company_id=buyer_company.id,
                is_active=True,
                is_verified=True
            )
            db.add(buyer_user)
            
            await db.commit()
            
            print("✅ Test users created successfully!")
            print("\n🔑 Login Credentials:")
            print("=" * 50)
            print("ADMIN:")
            print("  Email: admin@procurement.com")
            print("  Password: admin123")
            print("  Role: admin")
            print()
            print("SUPPLIER:")
            print("  Email: supplier@techsupply.com") 
            print("  Password: supplier123")
            print("  Role: supplier")
            print()
            print("BUYER:")
            print("  Email: buyer@manufacturing.com")
            print("  Password: buyer123")
            print("  Role: buyer")
            print("=" * 50)
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Error creating users: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(create_test_users())