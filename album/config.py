"""
Static configuration describing the Panini-style album structure.

This file keeps *all* album / team / sticker metadata in one place so that:
- the Python routes can render pages from the same source of truth
- the JavaScript logic can reason about stickers using predictable IDs
- you can easily extend the album to the full World Cup by adding teams / numbers
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


class StickerDefinition(TypedDict):
    """Represents a single sticker's metadata."""

    id: str  # globally unique ID, e.g. "ARG-1"
    number: int  # numeric position inside the team / page
    label: str  # human‑friendly description that will be shown in the UI / Excel


class PageDefinition(TypedDict):
    """
    One physical "page" in the album.

    Each page can represent:
    - the cover
    - a collection of general tournament stickers
    - a specific national team
    """

    id: str  # used for navigation, must be unique, e.g. "cover", "team-arg"
    title: str
    section: str  # used for grouping in navigation, e.g. "General", "Teams"
    team_code: str | None  # "ARG", "MEX", etc.; None for non-team pages
    stickers: List[StickerDefinition]


def _team_page(team_code: str, team_name: str, sticker_numbers: range) -> PageDefinition:
    """
    Helper to build a page definition for a team.

    Sticker IDs follow the pattern "<TEAM_CODE>-<NUMBER>", e.g. "ARG-7".
    """
    stickers: List[StickerDefinition] = []
    for num in sticker_numbers:
        sticker_id = f"{team_code}-{num}"
        stickers.append(
            {
                "id": sticker_id,
                "number": num,
                "label": f"{team_name} #{num}",
            }
        )

    return {
        "id": f"team-{team_code.lower()}",
        "title": team_name,
        "section": "Teams",
        "team_code": team_code,
        "stickers": stickers,
    }


def build_album_structure() -> List[PageDefinition]:
    """
    Returns a list of pages describing the album.

    For brevity we only add a few example teams here. Extending the project to
    the complete World Cup means:
    - adding more `_team_page(...)` calls below
    - or generating them dynamically from a data file (CSV / JSON) later
    """
    pages: List[PageDefinition] = []

    # Cover page – shown first when opening the website.
    pages.append(
        {
            "id": "cover",
            "title": "FIFA World Cup 2026 – Sticker Album BY JULIAN ROMERO",
            "section": "General",
            "team_code": None,
            "stickers": [],
        }
    )

    # General tournament page with a few "special" stickers as an example.
    general_stickers: List[StickerDefinition] = [
        {"id": "GEN-1", "number": 1, "label": "Tournament Logo"},
        {"id": "GEN-2", "number": 2, "label": "Official Ball"},
        {"id": "GEN-3", "number": 3, "label": "World Cup Trophy"},
        {"id": "GEN-4", "number": 4, "label": "Mascot"},
    ]

    pages.append(
        {
            "id": "tournament",
            "title": "Tournament Specials",
            "section": "General",
            "team_code": None,
            "stickers": general_stickers,
        }
    )

    # Example team pages. You can expand these ranges or add more teams.
    pages.append(_team_page("ARG", "Argentina", range(1, 21)))
    pages.append(_team_page("ECU", "Ecuador", range(1, 21)))
    pages.append(_team_page("COL", "Colombia", range(1, 21)))
    pages.append(_team_page("URU", "Uruguay", range(1, 21)))
    pages.append(_team_page("BRA", "Brazil", range(1, 21)))
    pages.append(_team_page("PAR", "Paraguay", range(1, 21)))
    pages.append(_team_page("MEX", "Mexico", range(1, 21)))
    pages.append(_team_page("USA", "United States", range(1, 21)))

    return pages


# Pre-built album structure used by routes and templates.
ALBUM_PAGES: List[PageDefinition] = build_album_structure()


def team_pages_by_code() -> Dict[str, PageDefinition]:
    """
    Convenience index: maps "ARG" -> team page definition.

    Helpful for quickly jumping to the correct page from the navbar.
    """
    return {
        page["team_code"]: page
        for page in ALBUM_PAGES
        if page["team_code"] is not None
    }

