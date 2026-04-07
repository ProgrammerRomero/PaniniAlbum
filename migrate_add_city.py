"""
Migration script to add city column to users table.

This script adds the missing city column that was added to the User model.
Supports both SQLite and PostgreSQL.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from album import create_app, db
from sqlalchemy import text


def migrate():
    """Add city column to users table."""
    app = create_app()

    with app.app_context():
        print("Starting city column migration...")

        try:
            # Try PostgreSQL approach first
            result = db.session.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'city'"
            )).fetchone()

            if result:
                print("   City column already exists - skipping migration")
                return True

        except Exception as e:
            print(f"   Not PostgreSQL or column check failed: {e}")
            # Fall through to SQLite approach

        try:
            # Add city column - works for both SQLite and PostgreSQL
            print("   Adding city column to users table...")
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN city VARCHAR(100)"
            ))
            db.session.commit()
            print("   Successfully added city column!")

        except Exception as e:
            print(f"   Error adding column: {e}")
            db.session.rollback()
            # Column likely already exists
            print("   Column may already exist - continuing...")

        print("\n✅ City column migration completed!")
        return True


if __name__ == "__main__":
    migrate()
