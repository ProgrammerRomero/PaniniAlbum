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
    section: str  # used for grouping in navigation, e.g. "General", "Group A"
    team_code: str | None  # "ARG", "MEX", etc.; None for non-team pages
    confederation: str | None  # "UEFA", "CONMEBOL", "CONCACAF", "CAF", "AFC", "OFC"
    stickers: List[StickerDefinition]


def _team_page(team_code: str, team_name: str, confederation: str, sticker_numbers: range) -> PageDefinition:
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
        "confederation": confederation,
        "stickers": stickers,
    }


def build_album_structure() -> List[PageDefinition]:
    """
    Returns a list of pages describing the complete FIFA World Cup 2026 album.

    HOW THE WORLD CUP 2026 QUALIFICATION WORKS:
    ===========================================

    The 2026 FIFA World Cup is the first to feature 48 teams (previously 32).
    The extra 16 spots are distributed across all confederations.

    Confederation Breakdown:
    ------------------------
    - UEFA (Europe):           16 spots (was 13) - 3 extra
    - CAF (Africa):             9 spots (was 5)  - 4 extra
    - AFC (Asia):               8 spots (was 4)  - 4 extra
    - CONCACAF (N/C America):   6 spots (was 3)  - 3 extra
    - CONMEBOL (S. America):     6 spots (was 4)  - 2 extra
    - OFC (Oceania):             2 spots (was 0)  - 2 new guaranteed
    - Playoff Tournament:        2 spots (was 2)  - same

    Total: 48 teams + 2 playoff = 50 nations competing for 48 spots

    The 2026 tournament is hosted by three nations:
    - United States (primary host)
    - Canada (first time hosting)
    - Mexico (third time hosting - 1970, 1986, 2026)
    All three hosts automatically qualify.

    ALBUM STRUCTURE:
    ================

    The album contains:
    1. Cover page (no stickers - welcome screen)
    2. General tournament stickers (logos, trophy, stadiums, etc.)
    3. 48 team pages, each with 20 stickers:
       - Team photo
       - Coach
       - Star players
       - Team logo
       - Various action shots

    Total stickers in album: 970
    - General: 10 stickers
    - Teams: 48 teams × 20 stickers = 960 stickers
    - Grand Total: 970 stickers
    """
    pages: List[PageDefinition] = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    # Shown first when opening the website - no stickers, just welcome
    pages.append(
        {
            "id": "cover",
            "title": "FIFA World Cup 2026",
            "section": "General",
            "team_code": None,
            "stickers": [],
        }
    )

    # =========================================================================
    # GENERAL TOURNAMENT STICKERS
    # =========================================================================
    # Special stickers for the tournament (logos, trophy, stadiums, etc.)
    general_stickers: List[StickerDefinition] = [
        {"id": "GEN-1", "number": 1, "label": "Tournament Logo"},
        {"id": "GEN-2", "number": 2, "label": "Official Ball"},
        {"id": "GEN-3", "number": 3, "label": "World Cup Trophy"},
        {"id": "GEN-4", "number": 4, "label": "Mascot"},
        {"id": "GEN-5", "number": 5, "label": "Official Poster"},
        {"id": "GEN-6", "number": 6, "label": "Opening Match"},
        {"id": "GEN-7", "number": 7, "label": "Final Match"},
        {"id": "GEN-8", "number": 8, "label": "Stadium - USA"},
        {"id": "GEN-9", "number": 9, "label": "Stadium - Canada"},
        {"id": "GEN-10", "number": 10, "label": "Stadium - Mexico"},
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

    # =========================================================================
    # WORLD CUP 2026 GROUPS (48 teams, 12 groups of 4)
    # =========================================================================

    # GROUP A
    pages.append(_team_page("MEX", "Mexico", "CONCACAF", range(1, 21)))
    pages.append(_team_page("CZE", "Czech Republic", "UEFA", range(1, 21)))
    pages.append(_team_page("RSA", "South Africa", "CAF", range(1, 21)))
    pages.append(_team_page("KOR", "South Korea", "AFC", range(1, 21)))

    # GROUP B
    pages.append(_team_page("CAN", "Canada", "CONCACAF", range(1, 21)))
    pages.append(_team_page("BIH", "Bosnia and Herzegovina", "UEFA", range(1, 21)))
    pages.append(_team_page("QAT", "Qatar", "AFC", range(1, 21)))
    pages.append(_team_page("SUI", "Switzerland", "UEFA", range(1, 21)))

    # GROUP C
    pages.append(_team_page("BRA", "Brazil", "CONMEBOL", range(1, 21)))
    pages.append(_team_page("HAI", "Haiti", "CONCACAF", range(1, 21)))
    pages.append(_team_page("MAR", "Morocco", "CAF", range(1, 21)))
    pages.append(_team_page("SCO", "Scotland", "UEFA", range(1, 21)))

    # GROUP D
    pages.append(_team_page("USA", "United States", "CONCACAF", range(1, 21)))
    pages.append(_team_page("AUS", "Australia", "AFC", range(1, 21)))
    pages.append(_team_page("PAR", "Paraguay", "CONMEBOL", range(1, 21)))
    pages.append(_team_page("TUR", "Türkiye", "UEFA", range(1, 21)))

    # GROUP E
    pages.append(_team_page("GER", "Germany", "UEFA", range(1, 21)))
    pages.append(_team_page("ECU", "Ecuador", "CONMEBOL", range(1, 21)))
    pages.append(_team_page("CIV", "Ivory Coast", "CAF", range(1, 21)))
    pages.append(_team_page("CUW", "Curaçao", "CONCACAF", range(1, 21)))

    # GROUP F
    pages.append(_team_page("NED", "Netherlands", "UEFA", range(1, 21)))
    pages.append(_team_page("JPN", "Japan", "AFC", range(1, 21)))
    pages.append(_team_page("SWE", "Sweden", "UEFA", range(1, 21)))
    pages.append(_team_page("TUN", "Tunisia", "CAF", range(1, 21)))

    # GROUP G
    pages.append(_team_page("BEL", "Belgium", "UEFA", range(1, 21)))
    pages.append(_team_page("EGY", "Egypt", "CAF", range(1, 21)))
    pages.append(_team_page("IRN", "Iran", "AFC", range(1, 21)))
    pages.append(_team_page("NZL", "New Zealand", "OFC", range(1, 21)))

    # GROUP H
    pages.append(_team_page("ESP", "Spain", "UEFA", range(1, 21)))
    pages.append(_team_page("URU", "Uruguay", "CONMEBOL", range(1, 21)))
    pages.append(_team_page("KSA", "Saudi Arabia", "AFC", range(1, 21)))
    pages.append(_team_page("CPV", "Cape Verde", "CAF", range(1, 21)))

    # GROUP I
    pages.append(_team_page("FRA", "France", "UEFA", range(1, 21)))
    pages.append(_team_page("NOR", "Norway", "UEFA", range(1, 21)))
    pages.append(_team_page("SEN", "Senegal", "CAF", range(1, 21)))
    pages.append(_team_page("IRQ", "Iraq", "AFC", range(1, 21)))

    # GROUP J
    pages.append(_team_page("ARG", "Argentina", "CONMEBOL", range(1, 21)))
    pages.append(_team_page("AUT", "Austria", "UEFA", range(1, 21)))
    pages.append(_team_page("ALG", "Algeria", "CAF", range(1, 21)))
    pages.append(_team_page("JOR", "Jordan", "AFC", range(1, 21)))

    # GROUP K
    pages.append(_team_page("POR", "Portugal", "UEFA", range(1, 21)))
    pages.append(_team_page("COL", "Colombia", "CONMEBOL", range(1, 21)))
    pages.append(_team_page("UZB", "Uzbekistan", "AFC", range(1, 21)))
    pages.append(_team_page("COD", "DR Congo", "CAF", range(1, 21)))

    # GROUP L
    pages.append(_team_page("ENG", "England", "UEFA", range(1, 21)))
    pages.append(_team_page("CRO", "Croatia", "UEFA", range(1, 21)))
    pages.append(_team_page("GHA", "Ghana", "CAF", range(1, 21)))
    pages.append(_team_page("PAN", "Panama", "CONCACAF", range(1, 21)))

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

