#!/usr/bin/env python3
"""
Railway startup script with error handling
"""
import os
import sys
import uvicorn
from app.main import app

def main():
    # Check required environment variables
    required_vars = ["DATABASE_URL", "SECRET_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Missing environment variables: {missing_vars}")
        sys.exit(1)
    
    # Get port from environment
    port = int(os.getenv("PORT", 8000))
    
    print(f"Starting server on port {port}")
    print(f"Database URL: {os.getenv('DATABASE_URL', 'Not set')[:50]}...")
    
    # Start the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()