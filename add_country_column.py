#!/usr/bin/env python
"""
Script to add the 'country' column to the users table.
Run this after updating the User model.
"""

import sqlite3
import os

# Path to the database file - adjust if needed
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'album.db')

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Please check the path and try again.")
        exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'country' in columns:
        print("Column 'country' already exists in users table.")
    else:
        # Add the country column
        cursor.execute("ALTER TABLE users ADD COLUMN country VARCHAR(100)")
        conn.commit()
        print("Successfully added 'country' column to users table.")

    conn.close()
    print("Done!")
