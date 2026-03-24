// Main client-side behaviour for the Panini Album.
//
// This script intentionally stays lightweight and framework-free:
// - state is stored in `localStorage` so progress persists per browser
// - page navigation is purely CSS transform based (no re-rendering)
// - communication with the Python backend is limited to the Excel export

(function () {
  const track = document.getElementById("albumTrack");
  const pages = Array.from(document.querySelectorAll(".album-page"));
  const leftArrow = document.getElementById("pageArrowLeft");
  const rightArrow = document.getElementById("pageArrowRight");
  const pageIndicator = document.getElementById("pageIndicator");
  const exportBtn = document.getElementById("exportMissingBtn");

  const teamsDropdown = document.getElementById("teamsDropdown");
  const dropdownToggle = teamsDropdown?.querySelector(".dropdown-toggle");
  const dropdownMenu = teamsDropdown?.querySelector(".dropdown-menu");

  const STORAGE_KEY = "panini_album_owned_ids_v1";

  // ===========================================================================
  // STATS MODAL ELEMENTS
  // ===========================================================================
  // These elements are used for the statistics dashboard feature.
  // They will be null if the elements don't exist (defensive coding).
  // ===========================================================================

  const statsBtn = document.getElementById("statsBtn");               // Button in navbar to open modal
  const statsModal = document.getElementById("statsModal");           // Modal container
  const statsModalClose = document.getElementById("statsModalClose"); // X button to close modal
  const statsModalOverlay = document.getElementById("statsModalOverlay"); // Clickable overlay to close
  const statsOverallPercent = document.getElementById("statsOverallPercent"); // Big percentage display
  const statsOverallCount = document.getElementById("statsOverallCount");     // Owned/total count display
  const statsTeamList = document.getElementById("statsTeamList");     // Container for team progress bars

  // Album structure data embedded in the HTML by Flask.
  // This contains all pages, teams, and stickers defined in config.py.
  // We parse it once at startup and cache it for statistics calculations.
  let albumStructure = [];
  try {
    const albumDataElement = document.getElementById("albumStructureData");
    if (albumDataElement) {
      albumStructure = JSON.parse(albumDataElement.textContent);
    }
  } catch (e) {
    console.warn("Failed to parse album structure data:", e);
  }

  let currentPageIndex = 0;

  /* -----------------------------------------------------------------------
   * Local storage helpers
   * --------------------------------------------------------------------- */

  function loadOwnedIds() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return new Set();
      return new Set(arr.map(String));
    } catch (e) {
      console.warn("Failed to load owned stickers from localStorage", e);
      return new Set();
    }
  }

  function saveOwnedIds(set) {
    try {
      const arr = Array.from(set);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
    } catch (e) {
      console.warn("Failed to save owned stickers to localStorage", e);
    }
  }

  const ownedIds = loadOwnedIds();

  /* -----------------------------------------------------------------------
   * Sticker checkboxes
   * --------------------------------------------------------------------- */

  function syncCheckboxesFromState() {
    const checkboxes = document.querySelectorAll(".sticker-checkbox");
    checkboxes.forEach((cb) => {
      const id = cb.getAttribute("data-sticker-id");
      cb.checked = ownedIds.has(id);
    });
  }

  function handleCheckboxChange(event) {
    const cb = event.target;
    if (!(cb instanceof HTMLInputElement)) return;
    if (!cb.classList.contains("sticker-checkbox")) return;

    const id = cb.getAttribute("data-sticker-id");
    if (!id) return;

    if (cb.checked) {
      ownedIds.add(id);
    } else {
      ownedIds.delete(id);
    }
    saveOwnedIds(ownedIds);
  }

  /* -----------------------------------------------------------------------
   * Page navigation
   * --------------------------------------------------------------------- */

  // This function ensures the given page index (idx) stays within the valid range of available album pages.
  // If idx is less than 0, it returns 0. If idx is greater than the last page index, it returns the last index.
  // Otherwise, it returns idx as-is.
  function clampPageIndex(idx) {
    return Math.max(0, Math.min(pages.length - 1, idx));
  }

  function updatePagePosition() {
    const pct = currentPageIndex * -100;
    track.style.transform = `translateX(${pct}%)`;

    if (leftArrow) {
      leftArrow.disabled = currentPageIndex === 0;
    }
    if (rightArrow) {
      rightArrow.disabled = currentPageIndex === pages.length - 1;
    }

    if (pageIndicator) {
      pageIndicator.textContent = `Page ${currentPageIndex + 1} of ${pages.length
        }`;
    }
  }

  function goToPageIndex(idx) {
    currentPageIndex = clampPageIndex(idx);
    updatePagePosition();
  }

  function goToPageId(pageId) {
    const index = pages.findIndex((p) => p.dataset.pageId === pageId);
    if (index >= 0) {
      goToPageIndex(index);
    }
  }

  /* -----------------------------------------------------------------------
   * Dropdown (Teams)
   * --------------------------------------------------------------------- */

  function closeDropdown() {
    if (teamsDropdown) {
      teamsDropdown.classList.remove("open");
    }
  }

  function initDropdown() {
    if (!teamsDropdown || !dropdownToggle || !dropdownMenu) return;

    dropdownToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      teamsDropdown.classList.toggle("open");
    });

    dropdownMenu.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!target.classList.contains("dropdown-item")) return;

      const pageId = target.getAttribute("data-target-page-id");
      if (pageId) {
        goToPageId(pageId);
      }
      closeDropdown();
    });

    document.addEventListener("click", (event) => {
      if (!teamsDropdown.contains(event.target)) {
        closeDropdown();
      }
    });
  }

  /* -----------------------------------------------------------------------
   * Excel export
   * --------------------------------------------------------------------- */

  async function exportMissing() {
    const payload = { owned_ids: Array.from(ownedIds) };

    try {
      exportBtn.disabled = true;
      exportBtn.textContent = "Generating…";

      const response = await fetch("/export-missing", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Export failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "missing_stickers.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export Excel file", err);
      alert(
        "Something went wrong while generating the Excel file. Please try again."
      );
    } finally {
      exportBtn.disabled = false;
      exportBtn.textContent = "Export Missing (Excel)";
    }
  }

  /* -----------------------------------------------------------------------
   * Statistics Dashboard
   * -----------------------------------------------------------------------
   *
   * The stats feature calculates and displays collection progress.
   * It reads from two sources:
   * 1. albumStructure: Array of pages/teams/stickers from server (config.py)
   * 2. ownedIds: Set of sticker IDs the user has marked as owned
   *
   * It calculates:
   * - Overall: total owned / total stickers in album
   * - Per-team: owned per team / total stickers for that team
   *
   * Results are displayed in a modal with:
   * - Large percentage display
   * - Progress bars for each team
   * --------------------------------------------------------------------- */

  /**
   * Calculates statistics for the entire album and per team.
   *
   * HOW IT WORKS:
   * 1. Iterate through all pages in albumStructure
   * 2. For each page with stickers, count how many sticker IDs
   *    are present in the ownedIds Set
   * 3. Build up totals for overall stats
   * 4. Build up per-team stats
   *
   * @returns {Object} Statistics object containing:
   *   - overall: { owned, total, percent }
   *   - teams: Array of { teamCode, teamName, owned, total, percent }
   */
  function calculateStats() {
    // Initialize counters for overall statistics
    let totalOwned = 0;      // Count of stickers the user owns
    let totalStickers = 0;   // Total stickers in the entire album

    // Array to store per-team statistics
    // Each entry: { teamCode, teamName, owned, total, percent }
    const teamStats = [];

    // Iterate through each page in the album structure
    // Pages include: cover (no stickers), tournament specials, and team pages
    albumStructure.forEach((page) => {
      const stickers = page.stickers || [];  // Array of sticker definitions
      const teamCode = page.team_code;        // 3-letter code or null
      const teamName = page.title;            // Display name (e.g., "Argentina")

      if (stickers.length === 0) {
        // Skip pages with no stickers (e.g., cover page)
        return;
      }

      // Count how many stickers on this page the user owns
      // We check if each sticker's ID exists in the ownedIds Set
      let pageOwned = 0;
      stickers.forEach((sticker) => {
        totalStickers++;  // Increment total album count
        if (ownedIds.has(sticker.id)) {
          pageOwned++;    // Increment owned count
          totalOwned++;   // Increment overall owned count
        }
      });

      // Only track team pages separately (not general/tournament pages)
      if (teamCode) {
        teamStats.push({
          teamCode: teamCode,
          teamName: teamName,
          owned: pageOwned,
          total: stickers.length,
          percent: Math.round((pageOwned / stickers.length) * 100),
        });
      }
    });

    // Calculate overall percentage (rounded to nearest integer)
    const overallPercent = totalStickers > 0
      ? Math.round((totalOwned / totalStickers) * 100)
      : 0;

    return {
      overall: {
        owned: totalOwned,
        total: totalStickers,
        percent: overallPercent,
      },
      teams: teamStats,
    };
  }

  /**
   * Opens the statistics modal and populates it with current data.
   *
   * HOW IT WORKS:
   * 1. Calculate current statistics using calculateStats()
   * 2. Update the overall stats display (percentage and count)
   * 3. Build HTML for team progress bars
   * 4. Show the modal by changing display style
   *
   * The modal shows a snapshot of the user's collection at the moment
   * they clicked the Stats button. It does NOT auto-update - if the user
   * checks more stickers while the modal is open, they need to close
   * and reopen it to see updated numbers.
   */
  function openStatsModal() {
    // Calculate current statistics
    const stats = calculateStats();

    // Update the overall percentage display (big number)
    // Example: "47%"
    if (statsOverallPercent) {
      statsOverallPercent.textContent = `${stats.overall.percent}%`;
    }

    // Update the overall count display
    // Example: "142 / 300"
    if (statsOverallCount) {
      statsOverallCount.textContent = `${stats.overall.owned} / ${stats.overall.total}`;
    }

    // Build HTML for team progress bars
    // Each team gets a row with name, progress bar, and count
    if (statsTeamList) {
      // Sort teams by completion percentage (highest first)
      // This helps users see which teams are closest to completion
      const sortedTeams = [...stats.teams].sort((a, b) => b.percent - a.percent);

      // Build HTML string for all team rows
      const html = sortedTeams.map((team) => {
        // Determine color based on completion:
        // - 100%: Green (completed)
        // - >=50%: Orange (in progress)
        // - <50%: Blue (just started)
        const barColor = team.percent === 100
          ? "#22c55e"  // Green for complete
          : team.percent >= 50
            ? "#f97316"  // Orange for halfway
            : "#38bdf8"; // Blue for starting

        return `
          <div class="stats-team-row">
            <div class="stats-team-header">
              <span class="stats-team-name">${team.teamCode} – ${team.teamName}</span>
              <span class="stats-team-count">${team.owned}/${team.total}</span>
            </div>
            <div class="stats-progress-container">
              <div
                class="stats-progress-bar"
                style="width: ${team.percent}%; background-color: ${barColor};"
                role="progressbar"
                aria-valuenow="${team.percent}"
                aria-valuemin="0"
                aria-valuemax="100"
              ></div>
            </div>
          </div>
        `;
      }).join("");

      statsTeamList.innerHTML = html;
    }

    // Show the modal by removing 'display: none'
    if (statsModal) {
      statsModal.style.display = "block";

      // Add animation class for fade-in effect
      // We use requestAnimationFrame to ensure the browser applies the display
      // change before adding the animation class, which triggers the transition
      requestAnimationFrame(() => {
        statsModal.classList.add("modal-open");
      });
    }
  }

  /**
   * Closes the statistics modal.
   *
   * HOW IT WORKS:
   * 1. Remove the animation class (triggers fade-out)
   * 2. Wait for animation to complete, then hide completely
   * 3. Restore focus to the Stats button (accessibility)
   */
  function closeStatsModal() {
    if (!statsModal) return;

    // Remove animation class (triggers CSS transition)
    statsModal.classList.remove("modal-open");

    // Wait for animation to complete before hiding
    // This ensures the fade-out animation is visible
    setTimeout(() => {
      if (statsModal) {
        statsModal.style.display = "none";
      }
    }, 200); // Matches CSS transition duration
  }

  /* -----------------------------------------------------------------------
   * Initialisation
   * --------------------------------------------------------------------- */

  function init() {
    if (!track || pages.length === 0) return;

    syncCheckboxesFromState();
    updatePagePosition();
    initDropdown();

    document.addEventListener("change", handleCheckboxChange);

    if (leftArrow) {
      leftArrow.addEventListener("click", () =>
        goToPageIndex(currentPageIndex - 1)
      );
    }
    if (rightArrow) {
      rightArrow.addEventListener("click", () =>
        goToPageIndex(currentPageIndex + 1)
      );
    }

    if (exportBtn) {
      exportBtn.addEventListener("click", exportMissing);
    }

    /* -----------------------------------------------------------------------
     * Stats modal event listeners
     * --------------------------------------------------------------------- */

    // Open modal when Stats button is clicked
    if (statsBtn) {
      statsBtn.addEventListener("click", openStatsModal);
    }

    // Close modal when X button is clicked
    if (statsModalClose) {
      statsModalClose.addEventListener("click", closeStatsModal);
    }

    // Close modal when clicking the overlay (outside the content)
    if (statsModalOverlay) {
      statsModalOverlay.addEventListener("click", closeStatsModal);
    }

    // Close modal when pressing Escape key
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && statsModal && statsModal.style.display === "block") {
        closeStatsModal();
      }
    });

    // Optional: allow keyboard navigation with arrow keys.
    document.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") {
        goToPageIndex(currentPageIndex - 1);
      } else if (event.key === "ArrowRight") {
        goToPageIndex(currentPageIndex + 1);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

