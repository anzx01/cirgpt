#!/usr/bin/env python3
"""
Celery beat scheduler launcher
Run this script to start the Celery beat scheduler for periodic tasks
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.worker.celery_app import celery_app

if __name__ == "__main__":
    # Start Celery beat scheduler
    celery_app.start([
        "beat",
        "--loglevel=info"
    ])
