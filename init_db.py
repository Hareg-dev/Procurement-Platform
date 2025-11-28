#!/usr/bin/env python3
import asyncio
from app.core.db import init_db

async def main():
    """Initialize database tables"""
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully!")

if __name__ == "__main__":
    asyncio.run(main())