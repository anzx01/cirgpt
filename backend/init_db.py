#!/usr/bin/env python3
"""
Database initialization script
Run this script to create all database tables
"""
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from models import init_db
from app.config import settings


def main():
    """Initialize the database"""
    print(f"Initializing database at: {settings.DB_URL}")
    try:
        init_db()
        print("SUCCESS: Database initialized successfully!")
        print("Tables created:")
        print("  - circuit_designs")
        print("  - design_history")
    except Exception as e:
        print(f"ERROR: Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
