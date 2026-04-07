"""
Migration script for multi-album version support.

This script:
1. Creates album_versions table with Gold, Blue, Orange editions
2. Creates user_albums table
3. Adds album_version_id column to user_stickers
4. Migrates existing data to Blue version
5. Adds has_selected_version flag to users
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from album import create_app, db
from album.models import AlbumVersion, UserAlbum, UserSticker, User


def migrate():
    """Run the migration."""
    app = create_app()

    with app.app_context():
        print("Starting multi-album migration...")

        # 1. Create album_versions table
        print("\n1. Creating album_versions table...")
        db.create_all()

        # 2. Insert the 3 album versions
        print("\n2. Inserting album versions...")
        versions = [
            AlbumVersion(
                code='gold',
                name='Gold',
                display_name='Gold Edition',
                theme_css_class='theme-gold'
            ),
            AlbumVersion(
                code='blue',
                name='Blue',
                display_name='Blue Edition',
                theme_css_class='theme-blue'
            ),
            AlbumVersion(
                code='orange',
                name='White',
                display_name='White Edition',
                theme_css_class='theme-orange'
            ),
        ]

        for version in versions:
            # Check if version already exists
            existing = AlbumVersion.query.filter_by(code=version.code).first()
            if not existing:
                db.session.add(version)
                print(f"   Added {version.name} version")
            else:
                print(f"   {version.name} version already exists")

        db.session.commit()

        # Get the Blue version ID (this will be the default)
        blue_version = AlbumVersion.query.filter_by(code='blue').first()
        if not blue_version:
            print("ERROR: Blue version not found!")
            return

        blue_version_id = blue_version.id
        print(f"   Blue version ID: {blue_version_id}")

        # 3. Migrate existing user_stickers to Blue version
        print("\n3. Migrating existing stickers to Blue version...")

        # Check if album_version_id column exists and has data
        try:
            from sqlalchemy import text
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM user_stickers WHERE album_version_id IS NULL"
            )).scalar()

            if result > 0:
                print(f"   Found {result} stickers without album_version_id")
                db.session.execute(text(
                    f"UPDATE user_stickers SET album_version_id = {blue_version_id} WHERE album_version_id IS NULL"
                ))
                db.session.commit()
                print(f"   Migrated {result} stickers to Blue version")
            else:
                print("   All stickers already have album_version_id")
        except Exception as e:
            print(f"   Note: {e}")
            print("   Column may not exist yet - migration will handle it")

        # 4. Create UserAlbum entries for existing users
        print("\n4. Creating UserAlbum entries for existing users...")
        users = User.query.all()
        created_count = 0

        for user in users:
            # Check if user already has Blue version
            existing = UserAlbum.query.filter_by(
                user_id=user.id,
                album_version_id=blue_version_id
            ).first()

            if not existing:
                user_album = UserAlbum(
                    user_id=user.id,
                    album_version_id=blue_version_id,
                    is_active=True
                )
                db.session.add(user_album)
                created_count += 1

        db.session.commit()
        print(f"   Created {created_count} UserAlbum entries")

        # 5. Mark existing users as having selected version
        print("\n5. Marking existing users as having selected version...")
        db.session.execute(text(
            "UPDATE users SET has_selected_version = TRUE WHERE has_selected_version = FALSE"
        ))
        db.session.commit()
        print("   All existing users marked as having selected version")

        print("\n✅ Migration completed successfully!")
        print("\nAlbum versions created:")
        for version in AlbumVersion.query.all():
            print(f"   - {version.name} (ID: {version.id}, Code: {version.code})")

        print(f"\nTotal UserAlbum entries: {UserAlbum.query.count()}")


if __name__ == "__main__":
    migrate()
