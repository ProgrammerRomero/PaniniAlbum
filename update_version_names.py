"""
Update album version names in the database.

Changes:
- Euro Edition -> Blue Edition
- Orange Edition -> White Edition
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from album import create_app, db
from album.models import AlbumVersion
from sqlalchemy import text


def update_names():
    """Update the display names for album versions."""
    app = create_app()

    with app.app_context():
        print("Updating album version names...")

        try:
            # Update Gold version (was Gold Crumple)
            gold = AlbumVersion.query.filter_by(code='gold').first()
            if gold:
                old_name = gold.name
                old_display = gold.display_name
                gold.name = 'Gold'
                gold.display_name = 'Gold Edition'
                print(f"Updated gold version: '{old_display}' -> 'Gold Edition'")

            # Update Blue version (was Euro)
            blue = AlbumVersion.query.filter_by(code='blue').first()
            if blue:
                old_name = blue.name
                old_display = blue.display_name
                blue.name = 'Blue'
                blue.display_name = 'Blue Edition'
                print(f"Updated blue version: '{old_display}' -> 'Blue Edition'")

            # Update Orange version (keep code as orange, change name to Orange)
            orange = AlbumVersion.query.filter_by(code='orange').first()
            if orange:
                old_name = orange.name
                old_display = orange.display_name
                orange.name = 'Orange'
                orange.display_name = 'Orange Edition'
                print(f"Updated orange version: '{old_display}' -> 'Orange Edition'")

            db.session.commit()
            print("\nAlbum version names updated successfully!")

            # Verify changes
            print("\nCurrent versions in database:")
            for version in AlbumVersion.query.all():
                print(f"  - Code: {version.code}, Name: {version.name}, Display: {version.display_name}")

        except Exception as e:
            db.session.rollback()
            print(f"\nError updating names: {e}")
            import traceback
            traceback.print_exc()
            return False

        return True


if __name__ == "__main__":
    success = update_names()
    sys.exit(0 if success else 1)
