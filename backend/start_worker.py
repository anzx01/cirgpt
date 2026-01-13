#!/usr/bin/env python3
"""
Celery worker launcher
Run this script to start the Celery worker for background tasks
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from app.worker.celery_app import celery_app

if __name__ == "__main__":
    # Start Celery worker
    celery_app.start([
        "worker",
        "--loglevel=info",
        "--concurrency=2",  # Number of worker processes
        "--max-tasks-per-child=50"
    ])
