// Main client-side behaviour for the Panini Album.
//
// This script now supports both localStorage (for guests) and database
// storage (for logged-in users) to enable multi-device access.
//
// Storage Strategy:
// - If user is logged in (detected by presence of user dropdown), use database API
// - If user is not logged in, fall back to localStorage for persistence
//
// Communication with backend:
// - GET /api/user/stickers - Load user's stickers from database
// - POST /api/sticker/own - Update ownership status
// - POST /api/sticker/duplicate - Update duplicate count

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

  // User dropdown elements
  const userDropdown = document.getElementById("userDropdown");
  const userToggle = userDropdown?.querySelector(".dropdown-toggle");
  const userMenu = userDropdown?.querySelector(".dropdown-menu");

  // Check if user is logged in by looking for user dropdown in navbar
  // If logged in, we use the database API; otherwise, localStorage
  const isLoggedIn = !!userDropdown;

  const STORAGE_KEY = "panini_album_owned_ids_v1";
  const DUPLICATES_KEY = "panini_album_duplicates_v1";

  // ===========================================================================
  // STATS MODAL ELEMENTS
  // ===========================================================================

  const statsBtn = document.getElementById("statsBtn");
  const statsModal = document.getElementById("statsModal");
  const statsModalClose = document.getElementById("statsModalClose");
  const statsModalOverlay = document.getElementById("statsModalOverlay");
  const statsOverallPercent = document.getElementById("statsOverallPercent");
  const statsOverallCount = document.getElementById("statsOverallCount");
  const statsTeamList = document.getElementById("statsTeamList");

  // Album structure data embedded in the HTML by Flask
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

  // ===========================================================================
  // STATE MANAGEMENT
  // ===========================================================================
  // Owned stickers and duplicates are stored in memory and synced to
  // either database (if logged in) or localStorage (if guest)
  // ===========================================================================

  let ownedIds = new Set();
  let duplicatesData = {};
  let isLoading = false;

  // ===========================================================================
  // DATA LOADING (from database or localStorage)
  // ===========================================================================

  /**
   * Load user data from appropriate source.
   * If logged in: fetch from /api/user/stickers
   * If guest: load from localStorage
   */
  async function loadUserData() {
    if (isLoading) return;
    isLoading = true;

    try {
      if (isLoggedIn) {
        // Fetch from database API
        const response = await fetch("/api/user/stickers");
        if (response.ok) {
          const data = await response.json();
          ownedIds = new Set(data.owned || []);
          duplicatesData = data.duplicates || {};
        } else {
          console.warn("Failed to load user data from API, using localStorage fallback");
          loadFromLocalStorage();
        }
      } else {
        // Load from localStorage
        loadFromLocalStorage();
      }
    } catch (e) {
      console.warn("Error loading user data:", e);
      loadFromLocalStorage();
    } finally {
      isLoading = false;
      // Sync UI with loaded data
      syncCheckboxesFromState();
      syncDuplicatesFromState();
    }
  }

  function loadFromLocalStorage() {
    // Load owned IDs
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          ownedIds = new Set(arr.map(String));
        }
      }
    } catch (e) {
      console.warn("Failed to load from localStorage:", e);
      ownedIds = new Set();
    }

    // Load duplicates
    try {
      const raw = window.localStorage.getItem(DUPLICATES_KEY);
      if (raw) {
        duplicatesData = JSON.parse(raw);
        if (typeof duplicatesData !== "object") {
          duplicatesData = {};
        }
      }
    } catch (e) {
      console.warn("Failed to load duplicates from localStorage:", e);
      duplicatesData = {};
    }
  }

  // ===========================================================================
  // DATA SAVING (to database or localStorage)
  // ===========================================================================

  /**
   * Save ownership status to appropriate storage.
   */
  async function saveOwnership(stickerId, isOwned) {
    if (isLoggedIn) {
      try {
        await fetch("/api/sticker/own", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sticker_id: stickerId, is_owned: isOwned }),
        });
      } catch (e) {
        console.warn("Failed to save to API:", e);
      }
    } else {
      // Save to localStorage
      try {
        const arr = Array.from(ownedIds);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
      } catch (e) {
        console.warn("Failed to save to localStorage:", e);
      }
    }
  }

  /**
   * Save duplicate count to appropriate storage.
   */
  async function saveDuplicate(stickerId, count) {
    if (isLoggedIn) {
      try {
        await fetch("/api/sticker/duplicate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sticker_id: stickerId, count: count }),
        });
      } catch (e) {
        console.warn("Failed to save duplicate to API:", e);
      }
    } else {
      // Save to localStorage
      try {
        window.localStorage.setItem(DUPLICATES_KEY, JSON.stringify(duplicatesData));
      } catch (e) {
        console.warn("Failed to save duplicates to localStorage:", e);
      }
    }
  }

  // ===========================================================================
  // STICKER CHECKBOXES
  // ===========================================================================

  function syncCheckboxesFromState() {
    const checkboxes = document.querySelectorAll(".sticker-checkbox");
    checkboxes.forEach((cb) => {
      const id = cb.getAttribute("data-sticker-id");
      cb.checked = ownedIds.has(id);
    });
  }

  async function handleCheckboxChange(event) {
    const cb = event.target;
    if (!(cb instanceof HTMLInputElement)) return;
    if (!cb.classList.contains("sticker-checkbox")) return;

    const id = cb.getAttribute("data-sticker-id");
    if (!id) return;

    if (cb.checked) {
      ownedIds.add(id);
    } else {
      ownedIds.delete(id);
      // Clear duplicates when unmarking as owned
      if (duplicatesData[id]) {
        delete duplicatesData[id];
        updateDuplicateDisplay(id);
      }
    }

    await saveOwnership(id, cb.checked);
  }

  // ===========================================================================
  // PAGE NAVIGATION
  // ===========================================================================

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
      pageIndicator.textContent = `Page ${currentPageIndex + 1} of ${pages.length}`;
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

  // ===========================================================================
  // DROPDOWN (Teams)
  // ===========================================================================

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

  // ===========================================================================
  // USER DROPDOWN (when logged in)
  // ===========================================================================

  function closeUserDropdown() {
    if (userDropdown) {
      userDropdown.classList.remove("open");
    }
  }

  function initUserDropdown() {
    if (!userDropdown || !userToggle || !userMenu) return;

    // Toggle dropdown on button click
    userToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      userDropdown.classList.toggle("open");
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (event) => {
      if (!userDropdown.contains(event.target)) {
        closeUserDropdown();
      }
    });
  }

  // ===========================================================================
  // EXCEL EXPORTS
  // ===========================================================================

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
      alert("Something went wrong while generating the Excel file. Please try again.");
    } finally {
      exportBtn.disabled = false;
      exportBtn.textContent = "Export Missing (Excel)";
    }
  }

  // ===========================================================================
  // STATISTICS DASHBOARD
  // ===========================================================================

  function calculateStats() {
    let totalOwned = 0;
    let totalStickers = 0;
    const teamStats = [];

    albumStructure.forEach((page) => {
      const stickers = page.stickers || [];
      const teamCode = page.team_code;
      const teamName = page.title;

      if (stickers.length === 0) return;

      let pageOwned = 0;
      stickers.forEach((sticker) => {
        totalStickers++;
        if (ownedIds.has(sticker.id)) {
          pageOwned++;
          totalOwned++;
        }
      });

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

  function openStatsModal() {
    const stats = calculateStats();

    if (statsOverallPercent) {
      statsOverallPercent.textContent = `${stats.overall.percent}%`;
    }

    if (statsOverallCount) {
      statsOverallCount.textContent = `${stats.overall.owned} / ${stats.overall.total}`;
    }

    if (statsTeamList) {
      const sortedTeams = [...stats.teams].sort((a, b) => b.percent - a.percent);

      const html = sortedTeams.map((team) => {
        const barColor = team.percent === 100
          ? "#22c55e"
          : team.percent >= 50
            ? "#f97316"
            : "#38bdf8";

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

    if (statsModal) {
      statsModal.style.display = "block";
      requestAnimationFrame(() => {
        statsModal.classList.add("modal-open");
      });
    }
  }

  function closeStatsModal() {
    if (!statsModal) return;
    statsModal.classList.remove("modal-open");
    setTimeout(() => {
      if (statsModal) {
        statsModal.style.display = "none";
      }
    }, 200);
  }

  // ===========================================================================
  // DUPLICATE STICKER TRACKING
  // ===========================================================================

  const exportDuplicatesBtn = document.getElementById("exportDuplicatesBtn");

  function getDuplicateCount(stickerId) {
    return duplicatesData[stickerId] || 0;
  }

  async function setDuplicateCount(stickerId, count) {
    const validCount = Math.max(0, parseInt(count, 10) || 0);

    if (validCount > 0) {
      duplicatesData[stickerId] = validCount;
    } else {
      delete duplicatesData[stickerId];
    }

    await saveDuplicate(stickerId, validCount);
    updateDuplicateDisplay(stickerId);
  }

  function updateDuplicateDisplay(stickerId) {
    const countEl = document.querySelector(`.duplicate-count[data-sticker-id="${stickerId}"]`);
    const badgeEl = document.querySelector(`.duplicate-badge[data-sticker-id="${stickerId}"]`);
    const minusBtn = document.querySelector(`.minus-btn[data-sticker-id="${stickerId}"]`);

    const count = getDuplicateCount(stickerId);

    if (countEl) countEl.textContent = count;
    if (badgeEl) badgeEl.style.display = count > 0 ? "inline" : "none";
    if (minusBtn) minusBtn.disabled = count === 0;
  }

  function syncDuplicatesFromState() {
    const countElements = document.querySelectorAll(".duplicate-count");
    countElements.forEach((el) => {
      const stickerId = el.getAttribute("data-sticker-id");
      if (stickerId) {
        updateDuplicateDisplay(stickerId);
      }
    });
  }

  async function handleDuplicateClick(event) {
    const btn = event.target;
    if (!btn.classList.contains("duplicate-btn")) return;

    const stickerId = btn.getAttribute("data-sticker-id");
    if (!stickerId) return;

    if (!ownedIds.has(stickerId)) {
      console.log("Cannot add duplicates to unowned sticker");
      return;
    }

    const currentCount = getDuplicateCount(stickerId);
    const isPlus = btn.classList.contains("plus-btn");
    const isMinus = btn.classList.contains("minus-btn");

    let newCount = currentCount;
    if (isPlus) {
      newCount = currentCount + 1;
    } else if (isMinus && currentCount > 0) {
      newCount = currentCount - 1;
    }

    if (newCount !== currentCount) {
      await setDuplicateCount(stickerId, newCount);
    }
  }

  async function exportDuplicates() {
    const duplicatesList = [];
    for (const [stickerId, count] of Object.entries(duplicatesData)) {
      if (count > 0) {
        duplicatesList.push({ id: stickerId, count: count });
      }
    }

    if (duplicatesList.length === 0) {
      alert("No tienes stickers duplicados para exportar.\n\nMarca stickers como duplicados usando los botones + y - en cada tarjeta.");
      return;
    }

    const payload = { duplicates: duplicatesList };

    try {
      exportDuplicatesBtn.disabled = true;
      exportDuplicatesBtn.textContent = "Generando…";

      const response = await fetch("/export-duplicates", {
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
      a.download = "duplicates_for_trade.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export duplicates Excel file", err);
      alert("Ocurrió un error al generar el archivo Excel. Por favor intenta de nuevo.");
    } finally {
      exportDuplicatesBtn.disabled = false;
      exportDuplicatesBtn.textContent = "📋 Export Duplicates";
    }
  }

  // ===========================================================================
  // INITIALISATION
  // ===========================================================================

  async function init() {
    // ALWAYS initialize user dropdown (works on all pages including profile)
    initUserDropdown();

    // Logo click - go to cover page (works on all pages)
    const logoHomeLink = document.getElementById("logoHomeLink");
    if (logoHomeLink) {
      logoHomeLink.addEventListener("click", (event) => {
        event.preventDefault();
        // Only navigate if we have the album pages loaded
        if (pages.length > 0) {
          goToPageId("cover");
        } else {
          // On profile page, redirect to home
          window.location.href = "/";
        }
      });
    }

    // Initialize teams dropdown (if present)
    initDropdown();

    // Album-specific initialization (only on album page)
    if (!track || pages.length === 0) {
      // We're on a page without the album (e.g., profile page)
      // User dropdown is already initialized above
      return;
    }

    // Load user data first (from database or localStorage)
    await loadUserData();

    // Sync UI with loaded data
    syncCheckboxesFromState();
    syncDuplicatesFromState();
    updatePagePosition();

    // Event listeners
    document.addEventListener("change", handleCheckboxChange);

    if (leftArrow) {
      leftArrow.addEventListener("click", () => goToPageIndex(currentPageIndex - 1));
    }
    if (rightArrow) {
      rightArrow.addEventListener("click", () => goToPageIndex(currentPageIndex + 1));
    }

    if (exportBtn) {
      exportBtn.addEventListener("click", exportMissing);
    }

    // Stats modal event listeners
    if (statsBtn) {
      statsBtn.addEventListener("click", openStatsModal);
    }
    if (statsModalClose) {
      statsModalClose.addEventListener("click", closeStatsModal);
    }
    if (statsModalOverlay) {
      statsModalOverlay.addEventListener("click", closeStatsModal);
    }
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && statsModal && statsModal.style.display === "block") {
        closeStatsModal();
      }
    });

    // Duplicate tracking event listeners
    document.addEventListener("click", handleDuplicateClick);
    if (exportDuplicatesBtn) {
      exportDuplicatesBtn.addEventListener("click", exportDuplicates);
    }

    // Keyboard navigation
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
