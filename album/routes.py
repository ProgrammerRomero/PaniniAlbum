from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from time import time
from typing import List, Set

from flask import Blueprint, current_app, jsonify, render_template, request, send_file, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy import text

from .config import ALBUM_PAGES, team_pages_by_code
from .models import db, UserSticker, AlbumVersion, UserAlbum

# Start time for uptime tracking
_start_time = time()

bp = Blueprint("album", __name__)


@bp.route("/")
@login_required
def index():
    """
    Render the main album view.

    All navigation (page flipping, team selection, ticking stickers) is then
    handled on the client side using a small amount of JavaScript.

    Redirects to version selection if user hasn't selected an album version.
    """
    from .models import UserAlbum, AlbumVersion

    # Check if user has selected an album version
    has_version = UserAlbum.query.filter_by(user_id=current_user.id).first()
    if not has_version:
        return redirect(url_for("auth.select_version"))

    # Get user's active version for theme
    active_album = UserAlbum.query.filter_by(
        user_id=current_user.id, is_active=True
    ).first()

    if active_album:
        current_version = active_album.version
    else:
        # Default to blue
        current_version = AlbumVersion.query.filter_by(code="blue").first()

    teams_index = team_pages_by_code()
    # Check if user wants to go directly to a specific team
    initial_team = request.args.get("team", None)
    return render_template(
        "album.html",
        album_pages=ALBUM_PAGES,
        team_pages=teams_index,
        initial_team=initial_team,
        current_version=current_version,
    )


@bp.route("/api/album-structure")
@login_required
def album_structure_api():
    """
    Lightweight JSON endpoint exposing the album metadata.

    The front‑end does not *need* this for the current UI, but keeping it
    around is helpful if you ever want to build a richer client (mobile app,
    React UI, etc.) that consumes the same data.
    """
    return jsonify(ALBUM_PAGES)


@bp.route("/export-missing", methods=["POST"])
@login_required
def export_missing():
    """
    Generate an Excel file listing **missing** stickers.

    The request body must contain JSON with a `owned_ids` list describing
    every sticker the user has already collected (based on the `id` used
    in `config.ALBUM_PAGES`).

    Example payload:
        {"owned_ids": ["ARG-1", "ARG-2", "GEN-1"]}

    The server compares this list to the album definition and generates a
    workbook with one row per missing sticker.
    """
    data = request.get_json(silent=True) or {}
    owned_ids_raw = data.get("owned_ids", [])

    # Normalise and validate the IDs into a set for quick membership checks.
    owned_ids: Set[str] = {
        str(sticker_id).strip() for sticker_id in owned_ids_raw if sticker_id
    }

    # Collect a flat list of all defined stickers, enriched with page metadata.
    missing_rows: List[dict] = []
    for page in ALBUM_PAGES:
        for sticker in page.get("stickers", []):
            sticker_id = sticker["id"]
            if sticker_id in owned_ids:
                continue

            missing_rows.append(
                {
                    "Sticker ID": sticker_id,
                    "Team Code": page.get("team_code") or "GENERAL",
                    "Page Title": page["title"],
                    "Number": sticker["number"],
                    "Label": sticker["label"],
                }
            )

    # Build an in‑memory Excel file using openpyxl.
    # Writing to disk would be unnecessary overhead here.
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Missing Stickers"

    if missing_rows:
        headers = list(missing_rows[0].keys())
        ws.append(headers)

        for row in missing_rows:
            ws.append([row[h] for h in headers])
    else:
        ws.append(["All stickers collected! 🎉"])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # `as_attachment=True` tells the browser to download the file instead of
    # trying to render it in‑place.
    return send_file(
        output,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name="missing_stickers.xlsx",
    )


@bp.route("/export-duplicates", methods=["POST"])
@login_required
def export_duplicates():
    """
    Generate an Excel file listing **duplicate** stickers for trading.

    The request body must contain JSON with a `duplicates` list describing
    each sticker the user has duplicates of, along with the count.

    Example payload:
        {
            "duplicates": [
                {"id": "ARG-1", "count": 2},
                {"id": "BRA-5", "count": 1}
            ]
        }

    The server looks up each sticker in the album definition and generates
    a workbook with details suitable for sharing with other collectors.
    This helps users trade duplicates to complete their collections.

    Columns in the output:
        - Sticker ID
        - Team Code
        - Page Title
        - Number
        - Label
        - Duplicates Available (count)
    """
    data = request.get_json(silent=True) or {}
    duplicates_raw = data.get("duplicates", [])

    # Build a lookup of sticker details from album structure
    # This maps sticker_id -> {page, sticker details}
    sticker_lookup = {}
    for page in ALBUM_PAGES:
        for sticker in page.get("stickers", []):
            sticker_lookup[sticker["id"]] = {
                "page": page,
                "sticker": sticker,
            }

    # Build rows for the Excel file
    duplicate_rows: List[dict] = []
    for item in duplicates_raw:
        if not isinstance(item, dict):
            continue

        sticker_id = str(item.get("id", "")).strip()
        count = int(item.get("count", 0))

        if not sticker_id or count <= 0:
            continue

        # Look up sticker details in album structure
        lookup = sticker_lookup.get(sticker_id)
        if not lookup:
            # Sticker not found in album (shouldn't happen)
            continue

        page = lookup["page"]
        sticker = lookup["sticker"]

        duplicate_rows.append(
            {
                "Sticker ID": sticker_id,
                "Team Code": page.get("team_code") or "GENERAL",
                "Page Title": page["title"],
                "Number": sticker["number"],
                "Label": sticker["label"],
                "Duplicates Available": count,
            }
        )

    # Sort by team code and then by sticker number for easy reading
    duplicate_rows.sort(key=lambda r: (r["Team Code"], r["Number"]))

    # Build an in-memory Excel file using openpyxl
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Duplicates for Trade"

    if duplicate_rows:
        headers = list(duplicate_rows[0].keys())
        ws.append(headers)

        for row in duplicate_rows:
            ws.append([row[h] for h in headers])
    else:
        ws.append(["No duplicates recorded yet! 🎴"])
        ws.append(["Use the + button on owned stickers to mark duplicates."])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name="duplicates_for_trade.xlsx",
    )


# =============================================================================
# DATABASE API ENDPOINTS (for logged-in users)
# =============================================================================

@bp.route("/api/user/stickers", methods=["GET"])
@login_required
def get_user_stickers():
    """
    Get all stickers owned by the current user for a specific album version.

    Query params:
        - version: Album version code (gold, blue, orange) - defaults to active version

    Returns JSON with:
        - owned: list of sticker IDs the user owns
        - duplicates: dict of sticker_id -> count
        - version_id: the album version ID

    This replaces the localStorage data when user is logged in.
    """
    version_code = request.args.get("version", None)

    # Get the album version ID
    if version_code:
        version = AlbumVersion.query.filter_by(code=version_code).first()
        if not version:
            return jsonify({"error": "Invalid version code"}), 400
        version_id = version.id
    else:
        # Use user's active version
        active_album = UserAlbum.query.filter_by(user_id=current_user.id, is_active=True).first()
        if active_album:
            version_id = active_album.album_version_id
        else:
            # Default to blue version
            blue = AlbumVersion.query.filter_by(code="blue").first()
            version_id = blue.id if blue else 1

    stickers = UserSticker.query.filter_by(
        user_id=current_user.id,
        album_version_id=version_id
    ).all()

    owned = []
    duplicates = {}

    for s in stickers:
        if s.is_owned:
            owned.append(s.sticker_id)
        if s.duplicate_count > 0:
            duplicates[s.sticker_id] = s.duplicate_count

    response = jsonify({
        "owned": owned,
        "duplicates": duplicates,
        "version_id": version_id,
    })
    # Prevent caching to ensure fresh data after version switches
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@bp.route("/api/sticker/own", methods=["POST"])
@login_required
def update_sticker_ownership():
    """
    Update ownership status of a sticker for a specific album version.

    Request body:
        - sticker_id: The sticker ID (e.g., "ARG-1")
        - is_owned: Boolean indicating if user owns it
        - version_id: Album version ID (optional, defaults to active version)

    Saves to database for persistent storage.
    """
    data = request.get_json(silent=True) or {}
    sticker_id = data.get("sticker_id", "").strip()
    is_owned = bool(data.get("is_owned", False))
    version_id = data.get("version_id")

    if not sticker_id:
        return jsonify({"error": "sticker_id is required"}), 400

    # Get album version ID
    if version_id:
        version_id = int(version_id)
    else:
        # Use user's active version
        active_album = UserAlbum.query.filter_by(user_id=current_user.id, is_active=True).first()
        if active_album:
            version_id = active_album.album_version_id
        else:
            # Default to blue version
            blue = AlbumVersion.query.filter_by(code="blue").first()
            version_id = blue.id if blue else 1

    # Ensure user has this album version (auto-create if missing)
    user_album = UserAlbum.query.filter_by(
        user_id=current_user.id,
        album_version_id=version_id
    ).first()
    if not user_album:
        # Auto-create UserAlbum entry for existing users
        user_album = UserAlbum(
            user_id=current_user.id,
            album_version_id=version_id,
            is_active=True
        )
        db.session.add(user_album)
        db.session.commit()

    # Find or create the sticker record
    user_sticker = UserSticker.query.filter_by(
        user_id=current_user.id,
        sticker_id=sticker_id,
        album_version_id=version_id
    ).first()

    if user_sticker:
        user_sticker.is_owned = is_owned
        # If unmarking as owned, clear duplicates too
        if not is_owned:
            user_sticker.duplicate_count = 0
    else:
        user_sticker = UserSticker(
            user_id=current_user.id,
            sticker_id=sticker_id,
            album_version_id=version_id,
            is_owned=is_owned,
            duplicate_count=0,
        )
        db.session.add(user_sticker)

    db.session.commit()

    response = jsonify({
        "success": True,
        "sticker_id": sticker_id,
        "is_owned": is_owned,
        "version_id": version_id,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@bp.route("/api/sticker/own-batch", methods=["POST"])
@login_required
def update_sticker_ownership_batch():
    """
    Update ownership status of multiple stickers in one request.

    Request body:
        - sticker_ids: List of sticker IDs (e.g., ["ARG-1", "ARG-2"])
        - is_owned: Boolean indicating if user owns them
        - version_id: Album version ID (optional, defaults to active version)

    Saves to database for persistent storage.
    """
    data = request.get_json(silent=True) or {}
    sticker_ids = data.get("sticker_ids", [])
    is_owned = bool(data.get("is_owned", False))
    version_id = data.get("version_id")

    if not sticker_ids or not isinstance(sticker_ids, list):
        return jsonify({"error": "sticker_ids array is required"}), 400

    # Get album version ID
    if version_id:
        version_id = int(version_id)
    else:
        # Use user's active version
        active_album = UserAlbum.query.filter_by(user_id=current_user.id, is_active=True).first()
        if active_album:
            version_id = active_album.album_version_id
        else:
            # Default to blue version
            blue = AlbumVersion.query.filter_by(code="blue").first()
            version_id = blue.id if blue else 1

    # Ensure user has this album version (auto-create if missing)
    user_album = UserAlbum.query.filter_by(
        user_id=current_user.id,
        album_version_id=version_id
    ).first()
    if not user_album:
        # Auto-create UserAlbum entry for existing users
        user_album = UserAlbum(
            user_id=current_user.id,
            album_version_id=version_id,
            is_active=True
        )
        db.session.add(user_album)
        db.session.commit()

    # Process all stickers in a single transaction
    for sticker_id in sticker_ids:
        user_sticker = UserSticker.query.filter_by(
            user_id=current_user.id,
            sticker_id=sticker_id,
            album_version_id=version_id
        ).first()

        if user_sticker:
            user_sticker.is_owned = is_owned
            # If unmarking as owned, clear duplicates too
            if not is_owned:
                user_sticker.duplicate_count = 0
        else:
            user_sticker = UserSticker(
                user_id=current_user.id,
                sticker_id=sticker_id,
                album_version_id=version_id,
                is_owned=is_owned,
                duplicate_count=0,
            )
            db.session.add(user_sticker)

    db.session.commit()

    response = jsonify({
        "success": True,
        "updated_count": len(sticker_ids),
        "is_owned": is_owned,
        "version_id": version_id,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@bp.route("/api/sticker/duplicate", methods=["POST"])
@login_required
def update_sticker_duplicate():
    """
    Update duplicate count for a sticker.

    Request body:
        - sticker_id: The sticker ID
        - count: Number of duplicates (0 or more)
        - version_id: Album version ID (optional, defaults to active version)

    Only works if the sticker is marked as owned.
    """
    data = request.get_json(silent=True) or {}
    sticker_id = data.get("sticker_id", "").strip()
    count = int(data.get("count", 0))
    version_id = data.get("version_id")

    if not sticker_id:
        return jsonify({"error": "sticker_id is required"}), 400

    if count < 0:
        count = 0

    # Get album version ID
    if version_id:
        version_id = int(version_id)
    else:
        # Use user's active version
        active_album = UserAlbum.query.filter_by(user_id=current_user.id, is_active=True).first()
        if active_album:
            version_id = active_album.album_version_id
        else:
            # Default to blue version
            blue = AlbumVersion.query.filter_by(code="blue").first()
            version_id = blue.id if blue else 1

    # Ensure user has this album version (auto-create if missing)
    user_album = UserAlbum.query.filter_by(
        user_id=current_user.id,
        album_version_id=version_id
    ).first()
    if not user_album:
        # Auto-create UserAlbum entry for existing users
        user_album = UserAlbum(
            user_id=current_user.id,
            album_version_id=version_id,
            is_active=True
        )
        db.session.add(user_album)
        db.session.commit()

    # Find or create the sticker record
    user_sticker = UserSticker.query.filter_by(
        user_id=current_user.id,
        sticker_id=sticker_id,
        album_version_id=version_id
    ).first()

    if user_sticker:
        user_sticker.duplicate_count = count
        # Automatically mark as owned if duplicates exist
        if count > 0:
            user_sticker.is_owned = True
    else:
        # If setting duplicates, also mark as owned
        user_sticker = UserSticker(
            user_id=current_user.id,
            sticker_id=sticker_id,
            album_version_id=version_id,
            is_owned=count > 0,
            duplicate_count=count,
        )
        db.session.add(user_sticker)

    db.session.commit()

    response = jsonify({
        "success": True,
        "sticker_id": sticker_id,
        "duplicate_count": count,
        "version_id": version_id,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# =============================================================================
# HEALTH CHECK ENDPOINT (For Railway/Docker monitoring)
# =============================================================================

@bp.route("/health")
def health_check():
    """
    Health check endpoint for Railway/Docker monitoring.

    Returns:
        JSON with status, timestamp, uptime, and database connectivity.
    """
    status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time() - _start_time),
        "service": "panini-album",
        "version": "1.0.0",
    }

    # Check database connectivity
    try:
        db.session.execute(text("SELECT 1"))
        status["database"] = "connected"
    except Exception as e:
        status["database"] = "disconnected"
        status["database_error"] = str(e)
        status["status"] = "unhealthy"
        return jsonify(status), 503

    # Memory usage (approximate)
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        status["memory_mb"] = round(mem_info.rss / 1024 / 1024, 2)
    except Exception:
        status["memory_mb"] = None

    return jsonify(status), 200


@bp.route("/ready")
def readiness_check():
    """
    Readiness check for Railway deployment.

    Returns 200 when app is ready to receive traffic.
    """
    return jsonify({"ready": True}), 200


# =============================================================================
# ALBUM VERSION MANAGEMENT ENDPOINTS
# =============================================================================

@bp.route("/api/album-versions", methods=["GET"])
@login_required
def get_album_versions():
    """
    Get all available album versions.

    Returns:
        JSON list of album versions with id, code, name, display_name, theme_css_class
    """
    versions = AlbumVersion.query.filter_by(is_active=True).all()
    return jsonify([{
        "id": v.id,
        "code": v.code,
        "name": v.name,
        "display_name": v.display_name,
        "theme_css_class": v.theme_css_class,
    } for v in versions])


@bp.route("/api/user/album-versions", methods=["GET"])
@login_required
def get_user_album_versions():
    """
    Get all album versions the user has selected.

    Returns:
        JSON list of user's album versions with active flag
    """
    user_albums = UserAlbum.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        "id": ua.id,
        "version_id": ua.album_version_id,
        "code": ua.version.code,
        "name": ua.version.name,
        "display_name": ua.version.display_name,
        "theme_css_class": ua.version.theme_css_class,
        "is_active": ua.is_active,
    } for ua in user_albums])


@bp.route("/api/user/switch-version", methods=["POST"])
@login_required
def switch_album_version():
    """
    Switch the active album version for the current user.

    Request body:
        - version_id: ID of the version to switch to
        OR
        - version_code: Code of the version to switch to (gold, blue, orange)

    Returns:
        JSON with success status and new active version
    """
    data = request.get_json(silent=True) or {}
    version_id = data.get("version_id")
    version_code = data.get("version_code")

    # Get version ID from code if provided
    if version_code and not version_id:
        version = AlbumVersion.query.filter_by(code=version_code).first()
        if not version:
            return jsonify({"error": "Invalid version code"}), 400
        version_id = version.id

    if not version_id:
        return jsonify({"error": "version_id or version_code is required"}), 400

    version_id = int(version_id)

    # Check if user has this version
    user_album = UserAlbum.query.filter_by(
        user_id=current_user.id,
        album_version_id=version_id
    ).first()

    if not user_album:
        return jsonify({"error": "User does not have this album version"}), 403

    # Deactivate all other versions
    UserAlbum.query.filter_by(user_id=current_user.id).update({"is_active": False})

    # Activate selected version
    user_album.is_active = True
    db.session.commit()

    return jsonify({
        "success": True,
        "version_id": version_id,
        "code": user_album.version.code,
        "name": user_album.version.name,
    })


@bp.route("/api/user/add-version", methods=["POST"])
@login_required
def add_album_version():
    """
    Add a new album version to the user's collection.

    Request body:
        - version_id: ID of the version to add
        OR
        - version_code: Code of the version to add (gold, blue, orange)

    Returns:
        JSON with success status
    """
    data = request.get_json(silent=True) or {}
    version_id = data.get("version_id")
    version_code = data.get("version_code")

    # Get version ID from code if provided
    if version_code and not version_id:
        version = AlbumVersion.query.filter_by(code=version_code).first()
        if not version:
            return jsonify({"error": "Invalid version code"}), 400
        version_id = version.id

    if not version_id:
        return jsonify({"error": "version_id or version_code is required"}), 400

    version_id = int(version_id)

    # Check if version exists
    version = AlbumVersion.query.get(version_id)
    if not version:
        return jsonify({"error": "Version not found"}), 404

    # Check if user already has this version
    existing = UserAlbum.query.filter_by(
        user_id=current_user.id,
        album_version_id=version_id
    ).first()

    if existing:
        return jsonify({"error": "User already has this album version"}), 400

    # Count user's current versions
    current_count = UserAlbum.query.filter_by(user_id=current_user.id).count()

    # Add new version
    user_album = UserAlbum(
        user_id=current_user.id,
        album_version_id=version_id,
        is_active=(current_count == 0)  # Make active if first version
    )
    db.session.add(user_album)
    db.session.commit()

    return jsonify({
        "success": True,
        "version_id": version_id,
        "code": version.code,
        "name": version.name,
        "is_active": user_album.is_active,
    })

