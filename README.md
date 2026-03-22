## Panini Album 2026 – Web App

Interactive, responsive web app to track your **FIFA World Cup 2026** sticker
collection. Built primarily with **Python (Flask)** and a small amount of
vanilla JavaScript for page transitions and Excel export.

### 1. Features

- **Album‑style navigation**
  - See a cover page when you open the site.
  - Flip pages left / right with arrow buttons or keyboard arrows.
  - Smooth horizontal sliding animation between pages.
- **Sticker tracking**
  - Each sticker is represented by a card (number + label).
  - Tick / untick stickers to mark which ones you already have.
  - State is stored in `localStorage` so your progress survives refreshes.
- **Team navigation**
  - Sticky navbar with a **Teams** dropdown.
  - Selecting a team jumps directly to that team’s page.
- **Excel export**
  - Button in the navbar generates an `missing_stickers.xlsx` file.
  - The backend compares your owned stickers with the full album definition.
  - Each row in the Excel file contains sticker ID, team, page, number, label.
- **Responsive UI + animations**
  - Works on desktop, tablet, and mobile.
  - Uses CSS transitions and gradients for a “premium album” feel.

### 2. Project structure and why it is organised this way

```text
panini_album/
├── app.py                  # Flask entry point (development server)
├── requirements.txt        # Python dependencies
└── album/                  # Application package
    ├── __init__.py         # Flask application factory
    ├── config.py           # Static album / team / sticker definitions
    ├── routes.py           # HTTP routes and Excel export logic
    ├── templates/
    │   ├── base.html       # Shared layout, navbar and footer
    │   └── album.html      # Main album view (pages + stickers)
    └── static/
        ├── css/
        │   └── style.css   # Styling, layout, animations, responsiveness
        └── js/
            └── app.js      # Page navigation, localStorage, Excel download
```

- **Package `album` with an app factory**
  - Keeps Flask configuration separate from `app.py`.
  - Easy to import in tests or WSGI servers later (`from album import create_app`).
- **`config.py` as a single source of truth**
  - All album metadata (pages, teams, stickers) is defined in Python.
  - You can expand the World Cup by adding more `_team_page(...)` entries.
  - Both the UI and Excel export use the exact same data, avoiding duplication.
- **Template + static separation**
  - `base.html` contains the skeleton (head + navbar + footer).
  - `album.html` only cares about rendering the album pages.
  - CSS / JS live under `static/` so Flask can serve them efficiently.
- **Vanilla JavaScript only where necessary**
  - Used for:
    - Keeping track of which stickers are checked (via `localStorage`).
    - Sliding the album pages left / right with CSS transforms.
    - Sending a POST request to `/export-missing` and triggering a download.
  - All core data and export logic stays in Python, as requested.

### 3. Running the project locally

1. **Create and activate a virtual environment (recommended)**

   ```bash
   cd panini_album
   python -m venv .venv
   .venv\Scripts\activate  # on Windows (PowerShell / CMD)
   # or:
   # source .venv/bin/activate  # on macOS / Linux
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Flask development server**

   ```bash
   python app.py
   ```

4. **Open the site**

   - Go to `http://127.0.0.1:5000/` (or `http://localhost:5000/`) in your browser.

### 4. How the main pieces work

- **Album pages (`album/templates/album.html`)**
  - Flask loops through `ALBUM_PAGES` (from `config.py`) and renders one
    `<article class="album-page">` per page.
  - Each page has a `data-page-id` and `data-page-index` used for navigation.
  - Stickers on a page are rendered as labelled checkboxes with a stable
    `data-sticker-id` that matches the Python configuration.

- **Navigation + state (`album/static/js/app.js`)**
  - Maintains the current page index and applies a
    `transform: translateX(-index * 100%)` on the track for smooth sliding.
  - Left / right arrows and keyboard arrow keys change the current page.
  - A page indicator at the bottom shows “Page X of Y”.
  - All sticker checkboxes share an event handler that updates a `Set` of
    owned IDs, which is synchronised to `localStorage`.

- **Excel export (`album/routes.py`)**
  - The client sends `POST /export-missing` with JSON:
    `{"owned_ids": ["ARG-1", "ARG-2", ...]}`.
  - The route compares these IDs against every sticker defined in `ALBUM_PAGES`.
  - Missing stickers are written into an in‑memory Excel workbook using
    `openpyxl`, then returned as a downloadable file.

### 5. Extending and improving

Some suggested next steps / improvements:

- **Full World Cup data**
  - Replace the small example in `config.py` with a complete list of teams and
    player stickers for the 2026 tournament.
  - Optionally load this data from a CSV / JSON file instead of hard‑coding it.
- **User profiles**
  - Currently, progress is stored per‑browser using `localStorage`.
  - If you want shared progress across devices, add a simple user system and
    store sticker ownership in a database (e.g. SQLite with SQLAlchemy).
- **Advanced analytics**
  - Show progress bars per team and for the whole album.
  - Add filters like “only show missing stickers for this team”.
- **Theming**
  - Add a light/dark theme toggle.
  - Allow custom accent colours for different users.

