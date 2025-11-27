#!/usr/bin/env python3
"""
Celery worker startup script for the procurement platform.

This script starts the Celery worker to process background tasks
including AI summarization and other async operations.

Usage:
    python start_celery.py

Make sure Redis is running before starting the worker.
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

# Import and start Celery
from app.tasks.celery_app import celery_app

if __name__ == "__main__":
    # Start Celery worker
    celery_app.start([
        "worker",
        "--loglevel=info",
        "--concurrency=2",
        "--pool=solo" if os.name == "nt" else "--pool=prefork"  # Use solo pool on Windows
    ])
