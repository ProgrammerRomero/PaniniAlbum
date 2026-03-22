from __future__ import annotations

from io import BytesIO
from typing import List, Set

from flask import Blueprint, jsonify, render_template, request, send_file

from .config import ALBUM_PAGES, team_pages_by_code

bp = Blueprint("album", __name__)


@bp.route("/")
def index():
    """
    Render the main album view.

    All navigation (page flipping, team selection, ticking stickers) is then
    handled on the client side using a small amount of JavaScript.
    """
    teams_index = team_pages_by_code()
    return render_template(
        "album.html",
        album_pages=ALBUM_PAGES,
        team_pages=teams_index,
    )


@bp.route("/api/album-structure")
def album_structure_api():
    """
    Lightweight JSON endpoint exposing the album metadata.

    The front‑end does not *need* this for the current UI, but keeping it
    around is helpful if you ever want to build a richer client (mobile app,
    React UI, etc.) that consumes the same data.
    """
    return jsonify(ALBUM_PAGES)


@bp.route("/export-missing", methods=["POST"])
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

