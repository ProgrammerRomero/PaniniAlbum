"""
Database migration to fix unique constraint on user_stickers table.

The old constraint was just (user_id, sticker_id) but it should be
(user_id, sticker_id, album_version_id) to support multi-album versions.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from album import create_app, db
from sqlalchemy import text


def migrate():
    """Fix the unique constraint on user_stickers table."""
    app = create_app()

    with app.app_context():
        print("Starting database constraint fix...")

        # Check if we're using SQLite
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        print(f"Database URL: {db_url}")

        try:
            # For SQLite, we need to check what indexes exist
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='user_stickers'"
            )).fetchall()

            existing_indexes = [row[0] for row in result]
            print(f"Existing indexes on user_stickers: {existing_indexes}")

            # Check if the old unique constraint exists (sqlite_auto_index_user_stickers_1)
            # or any constraint that doesn't include album_version_id

            # First, let's check the current table schema
            schema_result = db.session.execute(text(
                "PRAGMA table_info(user_stickers)"
            )).fetchall()

            print("\nCurrent table schema:")
            for col in schema_result:
                print(f"  {col}")

            # Check for unique constraints/indexes
            index_result = db.session.execute(text(
                "PRAGMA index_list(user_stickers)"
              )).fetchall()

            print("\nCurrent indexes:")
            for idx in index_result:
                print(f"  {idx}")
                # Get index info
                idx_info = db.session.execute(text(
                    f"PRAGMA index_info({idx[1]})"
                )).fetchall()
                print(f"    Columns: {[col[2] for col in idx_info]}")

        except Exception as e:
            print(f"Error checking schema: {e}")

        # The proper fix is to recreate the table with the correct constraint
        # SQLite doesn't support ALTER TABLE for dropping constraints, so we need to:
        # 1. Create a new table with the correct schema
        # 2. Copy data from old table
        # 3. Drop old table
        # 4. Rename new table

        print("\n--- Applying Fix ---")

        try:
            # Step 1: Create new table with correct schema
            print("Creating new table with correct schema...")
            db.session.execute(text("""
                CREATE TABLE user_stickers_new (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    sticker_id VARCHAR(20) NOT NULL,
                    is_owned BOOLEAN DEFAULT 0,
                    duplicate_count INTEGER DEFAULT 0,
                    updated_at DATETIME,
                    album_version_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (album_version_id) REFERENCES album_versions (id),
                    UNIQUE (user_id, sticker_id, album_version_id)
                )
            """))

            # Step 2: Copy data from old table
            print("Copying data from old table...")
            db.session.execute(text("""
                INSERT INTO user_stickers_new
                SELECT id, user_id, sticker_id, is_owned, duplicate_count, updated_at, album_version_id
                FROM user_stickers
            """))

            # Step 3: Drop old table
            print("Dropping old table...")
            db.session.execute(text("DROP TABLE user_stickers"))

            # Step 4: Rename new table
            print("Renaming new table...")
            db.session.execute(text("ALTER TABLE user_stickers_new RENAME TO user_stickers"))

            # Step 5: Create indexes
            print("Creating indexes...")
            db.session.execute(text("CREATE INDEX idx_user_stickers_user_id ON user_stickers(user_id)"))
            db.session.execute(text("CREATE INDEX idx_user_stickers_sticker_id ON user_stickers(sticker_id)"))
            db.session.execute(text("CREATE INDEX idx_user_stickers_version_id ON user_stickers(album_version_id)"))

            db.session.commit()
            print("\nDatabase constraint fix completed successfully!")

            # Verify the fix
            print("\nVerifying new schema...")
            index_result = db.session.execute(text(
                "PRAGMA index_list(user_stickers)"
            )).fetchall()

            print("New indexes:")
            for idx in index_result:
                if idx[2] == 1:  # unique index
                    idx_info = db.session.execute(text(
                        f"PRAGMA index_info({idx[1]})"
                    )).fetchall()
                    print(f"  {idx[1]} (UNIQUE): columns = {[col[2] for col in idx_info]}")

        except Exception as e:
            db.session.rollback()
            print(f"\nError during migration: {e}")
            import traceback
            traceback.print_exc()
            return False

        return True


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
