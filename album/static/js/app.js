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

  // Export dropdown elements
  const exportDropdown = document.getElementById("exportDropdown");
  const exportToggle = exportDropdown?.querySelector(".dropdown-toggle");
  const exportMenu = exportDropdown?.querySelector(".dropdown-menu");

  // Check if user is logged in by looking for user dropdown in navbar
  // If logged in, we use the database API; otherwise, localStorage
  const isLoggedIn = !!userDropdown;

  const STORAGE_KEY = "panini_album_owned_ids_v1";
  const DUPLICATES_KEY = "panini_album_duplicates_v1";

  // ===========================================================================
  // ALBUM VERSION MANAGEMENT
  // ===========================================================================

  // Get current album version from body data attribute
  const currentTheme = document.body.dataset.theme || 'blue';

  /**
   * Switch active album version
   * @param {string} versionCode - 'gold', 'blue', or 'orange'
   */
  async function switchAlbumVersion(versionCode) {
    try {
      const response = await fetch("/api/user/switch-version", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ version_code: versionCode }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Reload page to apply new theme and data
          window.location.reload();
        }
      } else {
        console.error("Failed to switch version:", await response.text());
      }
    } catch (e) {
      console.error("Error switching album version:", e);
    }
  }

  /**
   * Initialize version switcher if present
   */
  function initVersionSwitcher() {
    const versionSelect = document.getElementById("versionSelect");
    if (versionSelect) {
      versionSelect.addEventListener("change", function() {
        const selectedVersion = this.value;
        if (selectedVersion && selectedVersion !== currentTheme) {
          switchAlbumVersion(selectedVersion);
        }
      });
    }
  }

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

  // Album structure data embedded in the HTML by Flask or fetched via API
  let albumStructure = [];
  let albumStructureLoaded = false;

  /**
   * Load album structure from embedded JSON or fetch from API.
   * This allows the stats modal to work on all pages.
   */
  async function loadAlbumStructure() {
    if (albumStructureLoaded) return;

    try {
      // First try to parse embedded data
      const albumDataElement = document.getElementById("albumStructureData");
      if (albumDataElement) {
        const embeddedData = JSON.parse(albumDataElement.textContent);
        if (embeddedData && embeddedData.length > 0) {
          albumStructure = embeddedData;
          albumStructureLoaded = true;
          return;
        }
      }
    } catch (e) {
      console.warn("Failed to parse embedded album structure:", e);
    }

    // If no embedded data or empty, fetch from API
    try {
      const response = await fetch("/api/album-structure");
      if (response.ok) {
        albumStructure = await response.json();
        albumStructureLoaded = true;
      } else {
        console.warn("Failed to fetch album structure from API");
      }
    } catch (e) {
      console.warn("Failed to load album structure:", e);
    }
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
  let currentVersionId = null;
  let isSyncingFromState = false; // Flag to prevent event loops

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

    // Clear existing state before loading new data
    // This prevents stale data from persisting across version switches
    ownedIds = new Set();
    duplicatesData = {};

    try {
      if (isLoggedIn) {
        // Fetch from database API with cache-busting to ensure fresh data
        const response = await fetch("/api/user/stickers?_=" + Date.now(), {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache",
          }
        });
        if (response.ok) {
          const data = await response.json();
          ownedIds = new Set(data.owned || []);
          duplicatesData = data.duplicates || {};
          currentVersionId = data.version_id;
          console.log("Loaded stickers for version:", data.version_id, "Count:", ownedIds.size);
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
      // Always ensure we have a version ID - fallback to body data attribute
      if (!currentVersionId) {
        const versionFromBody = document.body.dataset.versionId;
        if (versionFromBody) {
          currentVersionId = parseInt(versionFromBody);
          console.log("Set version ID from body attribute:", currentVersionId);
        }
      }

      if (!currentVersionId) {
        console.error("CRITICAL: Could not determine current version ID - saves may fail");
      }

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
   * Get CSRF token from meta tag for authenticated requests.
   */
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  /**
   * Save ownership status to appropriate storage.
   * @returns {Promise<boolean>} - True if save succeeded, false otherwise
   */
  async function saveOwnership(stickerId, isOwned) {
    if (isLoggedIn) {
      try {
        const response = await fetch("/api/sticker/own", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ sticker_id: stickerId, is_owned: isOwned, version_id: currentVersionId }),
        });
        if (!response.ok) {
          console.error("Failed to save sticker ownership:", response.status, await response.text());
          return false;
        }
        return true;
      } catch (e) {
        console.warn("Failed to save to API:", e);
        return false;
      }
    } else {
      // Save to localStorage
      try {
        const arr = Array.from(ownedIds);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
        return true;
      } catch (e) {
        console.warn("Failed to save to localStorage:", e);
        return false;
      }
    }
  }

  /**
   * Save ownership status for multiple stickers in one request (batch).
   * @returns {Promise<boolean>} - True if save succeeded, false otherwise
   */
  async function saveOwnershipBatch(stickerIds, isOwned) {
    if (isLoggedIn) {
      try {
        const response = await fetch("/api/sticker/own-batch", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ sticker_ids: stickerIds, is_owned: isOwned, version_id: currentVersionId }),
        });
        if (!response.ok) {
          console.error("Failed to save batch sticker ownership:", response.status, await response.text());
          return false;
        }
        return true;
      } catch (e) {
        console.warn("Failed to save batch to API:", e);
        return false;
      }
    } else {
      // Save all at once to localStorage
      try {
        const arr = Array.from(ownedIds);
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
        return true;
      } catch (e) {
        console.warn("Failed to save to localStorage:", e);
        return false;
      }
    }
  }

  /**
   * Save duplicate count to appropriate storage.
   * @returns {Promise<boolean>} - True if save succeeded, false otherwise
   */
  async function saveDuplicate(stickerId, count) {
    if (isLoggedIn) {
      try {
        const response = await fetch("/api/sticker/duplicate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ sticker_id: stickerId, count: count, version_id: currentVersionId }),
        });
        if (!response.ok) {
          console.error("Failed to save duplicate count:", response.status, await response.text());
          return false;
        }
        return true;
      } catch (e) {
        console.warn("Failed to save duplicate to API:", e);
        return false;
      }
    } else {
      // Save to localStorage
      try {
        window.localStorage.setItem(DUPLICATES_KEY, JSON.stringify(duplicatesData));
        return true;
      } catch (e) {
        console.warn("Failed to save duplicates to localStorage:", e);
        return false;
      }
    }
  }

  // ===========================================================================
  // STICKER CHECKBOXES
  // ===========================================================================

  function syncCheckboxesFromState() {
    // Set flag before updating checkboxes to prevent event handlers from firing
    isSyncingFromState = true;

    const checkboxes = document.querySelectorAll(".sticker-checkbox");
    checkboxes.forEach((cb) => {
      const id = cb.getAttribute("data-sticker-id");
      const shouldBeChecked = ownedIds.has(id);
      // Only update if different to avoid unnecessary events
      if (cb.checked !== shouldBeChecked) {
        cb.checked = shouldBeChecked;
      }
    });

    // Clear flag synchronously - all DOM updates are done
    isSyncingFromState = false;
  }

  async function handleCheckboxChange(event) {
    // Skip if we're syncing from state (prevents event loops)
    if (isSyncingFromState) return;

    const cb = event.target;
    if (!(cb instanceof HTMLInputElement)) return;
    if (!cb.classList.contains("sticker-checkbox")) return;

    const id = cb.getAttribute("data-sticker-id");
    if (!id) return;

    // Update local state first (optimistic UI)
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

    // Save to server
    const saveSuccess = await saveOwnership(id, cb.checked);

    if (!saveSuccess) {
      // Save failed - revert checkbox to previous state
      console.error(`Failed to save sticker ${id}, reverting UI`);
      if (cb.checked) {
        ownedIds.delete(id);
        cb.checked = false;
      } else {
        ownedIds.add(id);
        cb.checked = true;
      }
      return;
    }

    // Update team completion status
    const card = cb.closest(".sticker-card");
    if (card) {
      const page = card.closest(".album-page");
      if (page) {
        const toggle = page.querySelector(".team-toggle[data-team-code]");
        if (toggle) {
          const teamCode = toggle.getAttribute("data-team-code");
          const stickerIdsJson = toggle.getAttribute("data-sticker-ids");
          if (teamCode && stickerIdsJson) {
            try {
              const stickerIds = JSON.parse(stickerIdsJson);
              updateTeamCompletionStatus(teamCode, stickerIds);
            } catch (e) {
              console.error("Failed to update team completion:", e);
            }
          }
        }
      }
    }
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

    // Update URL hash to reflect current team page (for back button support)
    const currentPage = pages[currentPageIndex];
    if (currentPage && typeof window.updateHashForPage === 'function') {
      window.updateHashForPage(currentPage.dataset.pageId);
    }
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
    if (teamsDropdown && teamsDropdown.classList.contains("open")) {
      teamsDropdown.classList.remove("open");
    }
  }

  function initDropdown() {
    if (!teamsDropdown || !dropdownToggle || !dropdownMenu) return;

    dropdownToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      // Close all other dropdowns first
      closeUserDropdown();
      closeExportDropdown();
      teamsDropdown.classList.toggle("open");
    });

    dropdownMenu.addEventListener("click", (event) => {
      const target = event.target.closest(".dropdown-item");
      if (!target) return;

      // Prevent any default behavior
      event.preventDefault();
      event.stopPropagation();

      const pageId = target.getAttribute("data-target-page-id");
      console.log("Team clicked:", pageId, "pages.length:", pages.length);

      if (pageId) {
        if (pages.length > 0) {
          // On album page, navigate directly
          console.log("Navigating directly to:", pageId);
          goToPageId(pageId);
        } else {
          // Not on album page, redirect via hash fragment for direct navigation
          // This avoids the flash of cover page that happens with query parameters
          console.log("Redirecting to /#team-" + pageId);
          window.location.href = "/#team-" + pageId;
        }
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
    if (userDropdown && userDropdown.classList.contains("open")) {
      userDropdown.classList.remove("open");
    }
  }

  function initUserDropdown() {
    if (!userDropdown || !userToggle || !userMenu) return;

    // Toggle dropdown on button click
    userToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      // Close all other dropdowns first
      closeDropdown();
      closeExportDropdown();
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
  // EXPORT DROPDOWN
  // ===========================================================================

  function closeExportDropdown() {
    if (exportDropdown && exportDropdown.classList.contains("open")) {
      exportDropdown.classList.remove("open");
    }
  }

  function initExportDropdown() {
    if (!exportDropdown || !exportToggle || !exportMenu) return;

    // Toggle dropdown on button click
    exportToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      // Close all other dropdowns first
      closeDropdown();
      closeUserDropdown();
      exportDropdown.classList.toggle("open");
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (event) => {
      if (!exportDropdown.contains(event.target)) {
        closeExportDropdown();
      }
    });

    // Close dropdown when clicking any item
    exportMenu.querySelectorAll(".dropdown-item").forEach((item) => {
      item.addEventListener("click", () => {
        closeExportDropdown();
      });
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

  async function calculateStats() {
    // Ensure album structure and user data are loaded
    await Promise.all([loadAlbumStructure(), loadUserData()]);

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

  async function openStatsModal() {
    const stats = await calculateStats();

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
      statsModal.style.display = "flex";
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
    const inputEl = document.querySelector(`.duplicate-count-input[data-sticker-id="${stickerId}"]`);
    const minusBtn = document.querySelector(`.minus-btn[data-sticker-id="${stickerId}"]`);

    const count = getDuplicateCount(stickerId);

    if (inputEl) inputEl.value = count;
    if (minusBtn) minusBtn.disabled = count === 0;
  }

  function syncDuplicatesFromState() {
    const inputElements = document.querySelectorAll(".duplicate-count-input");
    inputElements.forEach((el) => {
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

  async function handleDuplicateInput(event) {
    const input = event.target;
    if (!input.classList.contains("duplicate-count-input")) return;

    const stickerId = input.getAttribute("data-sticker-id");
    if (!stickerId) return;

    if (!ownedIds.has(stickerId)) {
      input.value = 0;
      return;
    }

    // Handle Enter key
    if (event.key === "Enter") {
      input.blur();
      return;
    }

    // Only allow numbers
    const value = input.value.replace(/[^0-9]/g, "");
    if (value !== input.value) {
      input.value = value;
    }
  }

  async function handleDuplicateInputBlur(event) {
    const input = event.target;
    if (!input.classList.contains("duplicate-count-input")) return;

    const stickerId = input.getAttribute("data-sticker-id");
    if (!stickerId) return;

    if (!ownedIds.has(stickerId)) {
      input.value = 0;
      return;
    }

    const newCount = parseInt(input.value, 10) || 0;
    const currentCount = getDuplicateCount(stickerId);

    if (newCount !== currentCount) {
      await setDuplicateCount(stickerId, newCount);
    } else {
      // Ensure display is correct even if no change
      input.value = currentCount;
    }
  }

  // ===========================================================================
  // TEAM COMPLETION TOGGLE
  // ===========================================================================

  // Custom confirmation modal state
  let teamConfirmCallback = null;
  let teamConfirmToggle = null;
  let teamConfirmStickerIds = null;

  function showTeamConfirmModal(teamCode, isCompleting, callback) {
    const modal = document.getElementById("teamConfirmModal");
    const message = document.getElementById("teamConfirmMessage");
    const confirmBtn = modal.querySelector(".team-confirm-confirm");

    // Set message based on action
    if (isCompleting) {
      message.innerHTML = `Mark all stickers for <strong>${teamCode}</strong> as completed?`;
      confirmBtn.textContent = "Mark Complete";
      confirmBtn.classList.remove("team-confirm-danger");
    } else {
      message.innerHTML = `Remove all stickers for <strong>${teamCode}</strong>?`;
      confirmBtn.textContent = "Remove All";
      confirmBtn.classList.add("team-confirm-danger");
    }

    // Store callback
    teamConfirmCallback = callback;

    // Show modal
    modal.style.display = "flex";
  }

  function hideTeamConfirmModal() {
    const modal = document.getElementById("teamConfirmModal");
    modal.style.display = "none";
    teamConfirmCallback = null;
  }

  // Global functions for onclick handlers
  window.confirmTeamToggle = function() {
    if (teamConfirmCallback) {
      teamConfirmCallback(true);
    }
    hideTeamConfirmModal();
  };

  window.cancelTeamToggle = function() {
    if (teamConfirmCallback) {
      teamConfirmCallback(false);
    }
    hideTeamConfirmModal();
  };

  async function handleTeamToggleChange(event) {
    // Skip if we're syncing from state (prevents event loops)
    if (isSyncingFromState) return;

    const toggle = event.target;

    if (!toggle.classList.contains("team-toggle")) return;

    const teamCode = toggle.getAttribute("data-team-code");
    if (!teamCode) return;

    const stickerIdsJson = toggle.getAttribute("data-sticker-ids");
    if (!stickerIdsJson) return;

    let stickerIds;
    try {
      stickerIds = JSON.parse(stickerIdsJson);
    } catch (e) {
      console.error("Failed to parse sticker IDs:", e);
      return;
    }

    const isChecked = toggle.checked;

    // Show custom confirmation modal
    showTeamConfirmModal(teamCode, isChecked, async (confirmed) => {
      if (!confirmed) {
        // User cancelled - revert toggle
        toggle.checked = !isChecked;
        return;
      }

      let saveSuccess = false;

      if (isChecked) {
        // Mark all stickers as owned - batch update
        for (const stickerId of stickerIds) {
          ownedIds.add(stickerId);
        }
        saveSuccess = await saveOwnershipBatch(stickerIds, true);
      } else {
        // Remove all stickers from owned - batch update
        for (const stickerId of stickerIds) {
          ownedIds.delete(stickerId);
          // Clear duplicates when unmarking
          if (duplicatesData[stickerId]) {
            delete duplicatesData[stickerId];
          }
        }
        saveSuccess = await saveOwnershipBatch(stickerIds, false);
      }

      if (saveSuccess) {
        // Sync UI only if save succeeded
        syncCheckboxesFromState();
        syncDuplicatesFromState();
        updateTeamCompletionStatus(teamCode, stickerIds);
        console.log(`Team ${teamCode} toggle ${isChecked ? 'ON' : 'OFF'} - saved successfully`);
      } else {
        // Save failed - reload data from server to restore correct state
        console.error(`Team ${teamCode} toggle save failed - reloading data`);
        await loadUserData();
        syncCheckboxesFromState();
        syncDuplicatesFromState();
        updateTeamCompletionStatus(teamCode, stickerIds);
      }
    });
  }

  function updateTeamCompletionStatus(teamCode, stickerIds) {
    const tag = document.querySelector(`.team-completed-tag[data-team-code="${teamCode}"]`);
    const toggle = document.querySelector(`.team-toggle[data-team-code="${teamCode}"]`);
    if (!tag || !toggle) return;

    const allOwned = stickerIds.every(id => ownedIds.has(id));

    // Update toggle state without triggering events
    isSyncingFromState = true;
    toggle.checked = allOwned;
    isSyncingFromState = false;

    // Show/hide completed tag
    if (allOwned) {
      tag.style.display = "inline-flex";
    } else {
      tag.style.display = "none";
    }
  }

  function updateAllTeamCompletionStatus() {
    isSyncingFromState = true;
    const toggles = document.querySelectorAll(".team-toggle[data-team-code]");
    toggles.forEach(toggle => {
      const teamCode = toggle.getAttribute("data-team-code");
      const stickerIdsJson = toggle.getAttribute("data-sticker-ids");
      if (!teamCode || !stickerIdsJson) return;

      try {
        const stickerIds = JSON.parse(stickerIdsJson);
        const tag = document.querySelector(`.team-completed-tag[data-team-code="${teamCode}"]`);
        if (!tag || !toggle) return;

        const allOwned = stickerIds.every(id => ownedIds.has(id));

        // Update toggle state
        toggle.checked = allOwned;

        // Show/hide completed tag
        if (allOwned) {
          tag.style.display = "inline-flex";
        } else {
          tag.style.display = "none";
        }
      } catch (e) {
        console.error("Failed to parse sticker IDs:", e);
      }
    });
    isSyncingFromState = false;
  }

  // ===========================================================================
  // CLICK HANDLER FOR TEAM TOGGLE (backup for label clicks)
  // ===========================================================================

  async function handleTeamToggleClick(event) {
    // Handle clicks on the toggle wrapper/slider as well
    const target = event.target;
    const wrapper = target.closest(".team-toggle-wrapper");
    if (!wrapper) return;

    const toggle = wrapper.querySelector(".team-toggle");
    if (!toggle) return;

    // If the click was directly on the toggle, let the change handler handle it
    if (target === toggle) return;

    // Otherwise, toggle the checkbox manually
    event.preventDefault();
    toggle.checked = !toggle.checked;

    // Manually trigger the change event
    const changeEvent = new Event("change", { bubbles: true });
    toggle.dispatchEvent(changeEvent);
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

    // Initialize version switcher (if present)
    initVersionSwitcher();

    // Pre-load album structure and user data for stats modal (needed on all authenticated pages)
    // These run in parallel with other init tasks
    const albumStructurePromise = loadAlbumStructure();
    const userDataPromise = isLoggedIn ? loadUserData() : Promise.resolve();

    // Logo click - go to cover page (not on login/register pages)
    const logoHomeLink = document.getElementById("logoHomeLink");
    if (logoHomeLink && logoHomeLink.tagName === "A") {
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

    // Initialize export dropdown (if present)
    initExportDropdown();

    // Stats modal event listeners (works on all pages)
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

    // Album-specific initialization (only on album page)
    if (!track || pages.length === 0) {
      // We're on a page without the album (e.g., profile page)
      return;
    }

    // Wait for user data to be loaded (already started above)
    await userDataPromise;

    // Check for initial team from redirect BEFORE setting page position
    const initialTeamEl = document.getElementById("initialTeamData");
    let targetPageId = null;

    // First check hash-based navigation (e.g., /#team-arg) - takes precedence
    // This handles navigation from other pages via dropdown
    const hash = window.location.hash;
    if (hash && hash.startsWith("#team-")) {
      targetPageId = hash.substring(6); // Remove "#team-" prefix
      console.log("Initial team from hash:", targetPageId);
    } else if (initialTeamEl) {
      // Fall back to server-rendered initial team (legacy ?team= param)
      try {
        targetPageId = JSON.parse(initialTeamEl.textContent);
        console.log("Initial team from redirect:", targetPageId);
      } catch (e) {
        console.error("Failed to parse initial team:", e);
      }
    }

    // Sync UI with loaded data
    syncCheckboxesFromState();
    syncDuplicatesFromState();

    // If we have an initial team, go there; otherwise start at cover
    if (targetPageId) {
      const targetIndex = pages.findIndex((p) => p.dataset.pageId === targetPageId);
      if (targetIndex >= 0) {
        currentPageIndex = targetIndex;
        console.log("Navigating directly to team page:", targetPageId, "index:", targetIndex);
      } else {
        console.warn("Team page not found:", targetPageId);
      }
      // Clean up the URL - replace query params with hash if needed
      if (hash && hash.startsWith("#team-")) {
        // Keep the hash for back button support, just remove any query params
        history.replaceState(null, null, window.location.pathname + hash);
      } else {
        // Legacy query param mode - clean up the URL
        history.replaceState(null, null, window.location.pathname);
      }
    }

    updatePagePosition();

    // Hide loading overlay after album is positioned
    // Small delay ensures smooth transition for direct team navigation
    const loadingOverlay = document.getElementById("albumLoadingOverlay");
    if (loadingOverlay) {
      setTimeout(() => {
        loadingOverlay.classList.add("hidden");
        // Remove from DOM after fade animation completes
        setTimeout(() => {
          loadingOverlay.style.display = "none";
        }, 350);
      }, targetPageId ? 300 : 100);
      // Longer delay when navigating to specific team (300ms) vs normal load (100ms)
    }

    // Event listeners
    document.addEventListener("change", handleCheckboxChange);
    document.addEventListener("change", handleTeamToggleChange);
    document.addEventListener("click", handleTeamToggleClick);

    // Check team completion status on page load
    updateAllTeamCompletionStatus();

    if (leftArrow) {
      leftArrow.addEventListener("click", () => goToPageIndex(currentPageIndex - 1));
    }
    if (rightArrow) {
      rightArrow.addEventListener("click", () => goToPageIndex(currentPageIndex + 1));
    }

    if (exportBtn) {
      exportBtn.addEventListener("click", exportMissing);
    }

    // Duplicate tracking event listeners
    document.addEventListener("click", handleDuplicateClick);
    document.addEventListener("input", handleDuplicateInput);
    document.addEventListener("blur", handleDuplicateInputBlur, true);
    document.addEventListener("keydown", handleDuplicateInput);
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

    // Listen for hash navigation events from the inline hash handler
    window.addEventListener('hashNavigation', (event) => {
      if (event.detail && typeof event.detail.pageIndex === 'number') {
        currentPageIndex = event.detail.pageIndex;
        updatePagePosition();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
