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

