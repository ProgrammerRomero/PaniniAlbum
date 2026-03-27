"""
Database Migration Script for Panini Album

This script adds the new columns and tables required for the messaging system.
Run this after updating the models.
"""

import sqlite3
import os

def migrate_database():
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'album.db')

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("The database will be created automatically when you run the app.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting database migration...")

    # Check if star_count column exists in users table
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'star_count' not in columns:
        print("Adding star_count column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN star_count INTEGER DEFAULT 0")
        print("[OK] star_count column added")
    else:
        print("[OK] star_count column already exists")

    # Check if messages table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
    if not cursor.fetchone():
        print("Creating messages table...")
        cursor.execute('''
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT 0,
                read_at DATETIME,
                trade_id INTEGER,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id),
                FOREIGN KEY (trade_id) REFERENCES trades (id)
            )
        ''')
        cursor.execute('CREATE INDEX idx_message_sender ON messages(sender_id)')
        cursor.execute('CREATE INDEX idx_message_recipient ON messages(recipient_id)')
        cursor.execute('CREATE INDEX idx_message_trade ON messages(trade_id)')
        print("[OK] messages table created")
    else:
        print("[OK] messages table already exists")

    # Check if trades table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
    if not cursor.fetchone():
        print("Creating trades table...")
        cursor.execute('''
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiator_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                stickers_offered TEXT,
                stickers_requested TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (initiator_id) REFERENCES users (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('CREATE INDEX idx_trade_initiator ON trades(initiator_id)')
        cursor.execute('CREATE INDEX idx_trade_recipient ON trades(recipient_id)')
        print("[OK] trades table created")
    else:
        print("[OK] trades table already exists")

    # Check if trade_confirmations table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_confirmations'")
    if not cursor.fetchone():
        print("Creating trade_confirmations table...")
        cursor.execute('''
            CREATE TABLE trade_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                confirmed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trade_id) REFERENCES trades (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(trade_id, user_id)
            )
        ''')
        cursor.execute('CREATE INDEX idx_confirmation_trade ON trade_confirmations(trade_id)')
        cursor.execute('CREATE INDEX idx_confirmation_user ON trade_confirmations(user_id)')
        print("[OK] trade_confirmations table created")
    else:
        print("[OK] trade_confirmations table already exists")

    conn.commit()
    conn.close()

    print("")
    print("Migration complete!")
    print("You can now run the Flask app.")

if __name__ == "__main__":
    migrate_database()
