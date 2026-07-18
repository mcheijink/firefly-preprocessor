import { apiGet, apiSend, jobIdFromShell } from "../api.js";
import { mountStepper } from "../stepper.js";
import { escapeHtml, amountClass, renderPageButtonsHtml, TableColumnManager } from "../tables.js";

const jobId = jobIdFromShell();
mountStepper(jobId);

const dupGateSummary = document.getElementById("duplicate-review-gate");
const dupBody = document.getElementById("duplicates-body");
const dupSummary = document.getElementById("dup-summary");
const dupPageSummaryEl = document.getElementById("dup-page-summary");
const toggleAllDupVisible = document.getElementById("toggle-all-dup-visible");

const dupSearchInput = document.getElementById("dup-search");
const applyDupFiltersBtn = document.getElementById("apply-dup-filters");
const refreshDupReviewBtn = document.getElementById("refresh-dup-review");
const selectVisibleDupBtn = document.getElementById("select-visible-dup");
const clearDupSelectionBtn = document.getElementById("clear-dup-selection");
const restoreDupSelectedBtn = document.getElementById("restore-dup-selected");
const confirmDupReviewBtn = document.getElementById("confirm-dup-review");
const dupColumnsBtn = document.getElementById("dup-columns-btn");
const dupPageSizeInput = document.getElementById("dup-page-size");
const dupSourceFileFilter = document.getElementById("dup-source-file-filter");
const dupSortBy = document.getElementById("dup-sort-by");
const dupSortDir = document.getElementById("dup-sort-dir");
const dupPageFirstBtn = document.getElementById("dup-page-first");
const dupPagePrevBtn = document.getElementById("dup-page-prev");
const dupPageButtons = document.getElementById("dup-page-buttons");
const dupPageNextBtn = document.getElementById("dup-page-next");
const dupPageLastBtn = document.getElementById("dup-page-last");

// Module-level review state. Was scattered across SPA globals in app.js
// (selectedDuplicateRows, dupPage, dupPageSize, dupTotal, duplicateReviewStatus,
// preferredDupSourceFile); this page owns them directly since there is no
// cross-tab/session state to share them with.
const selectedDuplicateRows = new Set();
let dupPage = 1;
let dupPageSize = Math.max(1, Number((dupPageSizeInput && dupPageSizeInput.value) || 20));
let dupTotal = 0;
let duplicateReviewStatus = {
  required: false,
  confirmed: true,
  can_proceed: true,
  pending_duplicates: 0,
  initial_duplicates: 0,
  restored_rows_total: 0,
};
let preferredDupSourceFile = "";

// ── tables.js column manager ────────────────────────────────────────────────
const tcmDuplicates = new TableColumnManager({
  tableId: "duplicates-table",
  columns: [
    { key: "select", label: "Select", alwaysVisible: true },
    { key: "dropped_id", label: "Dropped ID" },
    { key: "reason", label: "Reason", sortKey: "reason" },
    { key: "reasoning", label: "Reasoning", sortKey: "reasoning", defaultHidden: true },
    { key: "dropped_date", label: "Dropped Date", sortKey: "date" },
    { key: "dropped_amount", label: "Dropped Amount", sortKey: "amount" },
    { key: "dropped_description", label: "Dropped Description", sortKey: "description" },
    { key: "dropped_source", label: "Dropped Source", sortKey: "source_file" },
    { key: "kept_id", label: "Kept ID", defaultHidden: true },
    { key: "kept_date", label: "Kept Date", sortKey: "kept_date" },
    { key: "kept_amount", label: "Kept Amount", sortKey: "kept_amount" },
    { key: "kept_description", label: "Kept Description" },
    { key: "details", label: "Details", alwaysVisible: true },
  ],
  sortByEl: dupSortBy,
  sortDirEl: dupSortDir,
  applyEl: applyDupFiltersBtn,
});
tcmDuplicates.bindHeaderEvents();
if (dupColumnsBtn) {
  dupColumnsBtn.addEventListener("click", () => tcmDuplicates.openPicker(dupColumnsBtn));
}

// ── API layer, extracted from app.js:826-877 (fetchDuplicateReviewStatus,
// buildDuplicateReviewQuery, fetchDuplicateReviewRows,
// restoreDuplicateRowsRequest, confirmDuplicateReviewRequest) and rewired
// onto api.js's apiGet/apiSend (which already extract `detail` from error
// responses, so the manual `response.ok`/`payload.detail` checks are dropped).
async function fetchDuplicateReviewStatus(id) {
  return apiGet(`/api/jobs/${id}/duplicates/review/status`);
}

function buildDuplicateReviewQuery(offset, limit) {
  const params = new URLSearchParams();
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  params.set("search", String((dupSearchInput && dupSearchInput.value) || ""));
  params.set("source_file", String((dupSourceFileFilter && dupSourceFileFilter.value) || ""));
  params.set("sort_by", String((dupSortBy && dupSortBy.value) || "date"));
  params.set("sort_dir", String((dupSortDir && dupSortDir.value) || "asc"));
  return params;
}

async function fetchDuplicateReviewRows(id, offset, limit) {
  return apiGet(`/api/jobs/${id}/duplicates/review?${buildDuplicateReviewQuery(offset, limit).toString()}`);
}

async function restoreDuplicateRowsRequest(id, duplicateRowIndices) {
  return apiSend(`/api/jobs/${id}/duplicates/review/restore`, "POST", {
    duplicate_row_indices: duplicateRowIndices,
  });
}

async function confirmDuplicateReviewRequest(id) {
  return apiSend(`/api/jobs/${id}/duplicates/review/confirm`, "POST");
}

// ── Rendering, extracted from app.js:1457-1745 (getDupTotalPages,
// renderDuplicateReviewRows, updateDuplicateReviewSummary, updateDupPagination,
// loadDuplicateReview) and app.js:1531-1578 (updateDuplicateReviewGateUI,
// populateDuplicateSourceFileFilter). GLOBAL -> MODULE-LOCAL: all reads of
// duplicateReviewStatus/dupPage/dupPageSize/dupTotal/selectedDuplicateRows/
// preferredDupSourceFile now hit the module-level state declared above
// instead of SPA globals shared with other tabs.
//
// applyDuplicateReviewGateToActions (app.js:1461) and updateWorkflowStepper
// (app.js:1481) are DROPPED: they gated the SPA's categorize/export tab
// buttons and the old inline stepper, neither of which exists on this page
// -- stepper.js's mountStepper (called above) polls /summary independently
// and owns the pipeline rail instead.
//
// The Dropped/Kept "Details" buttons in review.html keep their markup (ported
// unchanged from the table row template) but are NOT wired to a detail
// modal: app.js's openTransactionDetail()/showToast() modal machinery is
// SPA-only session/tab state with no equivalent element in this template, so
// wiring it is out of this task's scope (duplicate review's own status/table
// refresh + restore/confirm flow).
function getDupTotalPages() {
  return Math.max(1, Math.ceil(dupTotal / Math.max(1, dupPageSize)));
}

function updateDuplicateReviewGateUI() {
  if (!dupGateSummary) {
    return;
  }
  const status = duplicateReviewStatus || {};
  const pending = Number(status.pending_duplicates || 0);
  const restored = Number(status.restored_rows_total || 0);
  const initial = Number(status.initial_duplicates || 0);
  const confirmed = !!status.confirmed;
  const required = !!status.required;
  if (!required) {
    dupGateSummary.textContent = `No blocking duplicate review is pending. Initial duplicates: ${initial}, remaining: ${pending}, restored: ${restored}.`;
    return;
  }
  if (confirmed) {
    dupGateSummary.textContent = `Duplicate review confirmed. Remaining suspected duplicates: ${pending}. Restored: ${restored}.`;
    return;
  }
  dupGateSummary.textContent =
    `Duplicate review required before categorization/export. Remaining suspected duplicates: ${pending}. ` +
    `Review rows below, restore any false positives, then click Confirm Review.`;
}

function populateDuplicateSourceFileFilter(files, keepCurrent = true) {
  if (!dupSourceFileFilter) {
    return;
  }
  const sourceFiles = Array.isArray(files) ? files : [];
  const current = keepCurrent ? String(dupSourceFileFilter.value || "") : "";
  dupSourceFileFilter.innerHTML = [
    `<option value="">All source files</option>`,
    ...sourceFiles.map((f) => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`),
  ].join("");
  if (current && sourceFiles.includes(current)) {
    dupSourceFileFilter.value = current;
    preferredDupSourceFile = current;
    return;
  }
  if (preferredDupSourceFile && sourceFiles.includes(preferredDupSourceFile)) {
    dupSourceFileFilter.value = preferredDupSourceFile;
    return;
  }
  dupSourceFileFilter.value = "";
}

function renderDuplicateReviewRows(rows) {
  if (!dupBody) {
    return;
  }
  if (!rows.length) {
    dupBody.innerHTML = `<tr><td colspan="13">No suspected duplicates for current filters.</td></tr>`;
    return;
  }
  dupBody.innerHTML = rows
    .map((row) => {
      const dupIdx = Number(row.duplicate_row_index || 0);
      const selected = dupIdx > 0 && selectedDuplicateRows.has(dupIdx) ? "checked" : "";
      const keptIdx = Number(row.kept_merge_row_index || 0);
      const hasMatch = String(row._has_match || "0") === "1";
      const keptId = keptIdx > 0 ? String(keptIdx) : "none";
      const matchClass = hasMatch ? "decision-badge merged" : "decision-badge dropped";
      const matchText = hasMatch ? "Matched kept row" : "No kept match";
      return `
        <tr class="dup-suspect" data-dup-row-index="${dupIdx}">
          <td data-col="select" data-label="Select"><input type="checkbox" class="dup-row-checkbox" data-dup-row-index="${dupIdx}" ${selected}></td>
          <td data-col="dropped_id" data-label="Dropped ID"><code>${escapeHtml(String(row.id || ""))}</code></td>
          <td data-col="reason" data-label="Reason">${escapeHtml(String(row.duplicate_reason || ""))}</td>
          <td data-col="reasoning" data-label="Reasoning">${escapeHtml(String(row.duplicate_reasoning || ""))}</td>
          <td data-col="dropped_date" data-label="Dropped Date">${escapeHtml(String(row.duplicate_date || ""))}</td>
          <td data-col="dropped_amount" data-label="Dropped Amount" class="num${amountClass(row.duplicate_amount)}">${escapeHtml(String(row.duplicate_amount || ""))}</td>
          <td data-col="dropped_description" data-label="Dropped Description">${escapeHtml(String(row.duplicate_description || ""))}</td>
          <td data-col="dropped_source" data-label="Dropped Source">${escapeHtml(String(row.source_file || ""))}</td>
          <td data-col="kept_id" data-label="Kept ID"><code>${escapeHtml(keptId)}</code></td>
          <td data-col="kept_date" data-label="Kept Date">${escapeHtml(String(row.kept_date || ""))}</td>
          <td data-col="kept_amount" data-label="Kept Amount" class="num${amountClass(row.kept_amount)}">${escapeHtml(String(row.kept_amount || ""))}</td>
          <td data-col="kept_description" data-label="Kept Description">${escapeHtml(String(row.kept_description || ""))}<div><span class="${matchClass}">${matchText}</span></div></td>
          <td data-col="details" data-label="Details" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="dup-open-dropped secondary-btn" data-row-source="duplicates" data-row-local-index="${dupIdx}" data-row-id="${escapeHtml(String(row.id || ""))}" disabled>Dropped</button>
              <button type="button" class="dup-open-kept secondary-btn" data-row-source="merged" data-row-local-index="${keptIdx}" data-row-id="${escapeHtml(keptId)}" disabled>Kept</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  tcmDuplicates.applyToTable();
  dupBody.querySelectorAll(".dup-row-checkbox").forEach((cb) => {
    cb.addEventListener("change", (event) => {
      const idx = Number(event.target.dataset.dupRowIndex || 0);
      if (!idx) return;
      if (event.target.checked) {
        selectedDuplicateRows.add(idx);
      } else {
        selectedDuplicateRows.delete(idx);
      }
      updateDuplicateReviewSummary();
    });
  });
}

function updateDuplicateReviewSummary() {
  if (!dupSummary) {
    return;
  }
  const pending = Number(duplicateReviewStatus.pending_duplicates || 0);
  const initial = Number(duplicateReviewStatus.initial_duplicates || 0);
  const restored = Number(duplicateReviewStatus.restored_rows_total || 0);
  const confirmed = !!duplicateReviewStatus.confirmed;
  const required = !!duplicateReviewStatus.required;
  dupSummary.textContent =
    `Showing page ${dupPage}/${getDupTotalPages()} (${dupTotal} filtered, pending ${pending}, initial ${initial}, restored ${restored}). ` +
    `Review ${required ? "required" : "optional"} and ${confirmed ? "confirmed" : "not confirmed"}. ` +
    `Selected rows: ${selectedDuplicateRows.size}.`;
  if (dupPageSummaryEl) {
    dupPageSummaryEl.textContent = `Rows ${dupTotal ? (dupPage - 1) * dupPageSize + 1 : 0}-${Math.min(dupPage * dupPageSize, dupTotal)} of ${dupTotal}`;
  }
}

function updateDupPagination() {
  const totalPages = getDupTotalPages();
  const canPrev = dupPage > 1;
  const canNext = dupPage < totalPages;
  if (dupPageFirstBtn) dupPageFirstBtn.disabled = !canPrev;
  if (dupPagePrevBtn) dupPagePrevBtn.disabled = !canPrev;
  if (dupPageNextBtn) dupPageNextBtn.disabled = !canNext;
  if (dupPageLastBtn) dupPageLastBtn.disabled = !canNext;
  if (!dupPageButtons) {
    return;
  }
  dupPageButtons.innerHTML = renderPageButtonsHtml(dupPage, totalPages, "dup-page-btn");
  dupPageButtons.querySelectorAll(".dup-page-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const page = Number(btn.dataset.page || 1);
      if (page === dupPage) {
        return;
      }
      dupPage = page;
      try {
        await loadDuplicateReview(false);
      } catch (error) {
        window.alert(error.message);
      }
    });
  });
}

async function loadDuplicateReview(reset = false) {
  if (!jobId) {
    return;
  }
  if (reset) {
    dupPage = 1;
  }
  dupPageSize = Math.max(1, Number((dupPageSizeInput && dupPageSizeInput.value) || 20));
  const offset = (Math.max(1, dupPage) - 1) * dupPageSize;
  const payload = await fetchDuplicateReviewRows(jobId, offset, dupPageSize);
  duplicateReviewStatus = payload.review || duplicateReviewStatus;
  updateDuplicateReviewGateUI();
  populateDuplicateSourceFileFilter(payload.source_files || [], true);
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  dupTotal = Number(payload.total || 0);
  renderDuplicateReviewRows(rows);
  const totalPages = getDupTotalPages();
  if (dupPage > totalPages) {
    dupPage = totalPages;
    await loadDuplicateReview(false);
    return;
  }
  updateDuplicateReviewSummary();
  updateDupPagination();
}

async function refreshDuplicateReviewStatus() {
  if (!jobId) {
    return;
  }
  duplicateReviewStatus = await fetchDuplicateReviewStatus(jobId);
  updateDuplicateReviewGateUI();
}

// ── Event bindings, extracted from app.js:3394-3539. GLOBAL -> LOCAL:
// showToast() calls replaced with window.alert (established pattern, see
// pages/merge.js and pages/jobs.js); showConfirm() replaced with
// window.confirm (showConfirm() already fell back to window.confirm on
// pages without a #confirm-modal, which this page doesn't have); saveFormPreferences()
// (SPA localStorage session-restore bookkeeping) dropped; the restore
// handler's follow-up fetchJob()/renderJob()/loadJobHistory() calls (SPA
// cross-tab refresh) dropped -- stepper.js's mountStepper poll already keeps
// the pipeline rail (and thus job status) in sync independently.
if (toggleAllDupVisible) {
  toggleAllDupVisible.addEventListener("change", (event) => {
    const checked = !!event.target.checked;
    if (!dupBody) return;
    dupBody.querySelectorAll(".dup-row-checkbox").forEach((cb) => {
      cb.checked = checked;
      const idx = Number(cb.dataset.dupRowIndex || 0);
      if (!idx) return;
      if (checked) {
        selectedDuplicateRows.add(idx);
      } else {
        selectedDuplicateRows.delete(idx);
      }
    });
    updateDuplicateReviewSummary();
  });
}

if (applyDupFiltersBtn) {
  applyDupFiltersBtn.addEventListener("click", async () => {
    dupPage = 1;
    selectedDuplicateRows.clear();
    if (toggleAllDupVisible) toggleAllDupVisible.checked = false;
    try {
      await loadDuplicateReview(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (refreshDupReviewBtn) {
  refreshDupReviewBtn.addEventListener("click", async () => {
    try {
      await loadDuplicateReview(false);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (selectVisibleDupBtn) {
  selectVisibleDupBtn.addEventListener("click", () => {
    if (!dupBody) return;
    dupBody.querySelectorAll(".dup-row-checkbox").forEach((cb) => {
      cb.checked = true;
      const idx = Number(cb.dataset.dupRowIndex || 0);
      if (idx) selectedDuplicateRows.add(idx);
    });
    updateDuplicateReviewSummary();
  });
}

if (clearDupSelectionBtn) {
  clearDupSelectionBtn.addEventListener("click", () => {
    selectedDuplicateRows.clear();
    if (toggleAllDupVisible) toggleAllDupVisible.checked = false;
    if (!dupBody) return;
    dupBody.querySelectorAll(".dup-row-checkbox").forEach((cb) => {
      cb.checked = false;
    });
    updateDuplicateReviewSummary();
  });
}

if (restoreDupSelectedBtn) {
  restoreDupSelectedBtn.addEventListener("click", async () => {
    if (!jobId) {
      window.alert("No job selected.");
      return;
    }
    if (!selectedDuplicateRows.size) {
      window.alert("Select at least one suspected duplicate row to restore.");
      return;
    }
    const approved = window.confirm(
      `Restore ${selectedDuplicateRows.size} selected duplicate row(s) back to merged transactions?`
    );
    if (!approved) return;
    restoreDupSelectedBtn.disabled = true;
    try {
      const indices = Array.from(selectedDuplicateRows).sort((a, b) => a - b);
      const result = await restoreDuplicateRowsRequest(jobId, indices);
      duplicateReviewStatus = result.review || duplicateReviewStatus;
      selectedDuplicateRows.clear();
      if (toggleAllDupVisible) toggleAllDupVisible.checked = false;
      await loadDuplicateReview(false);
    } catch (error) {
      window.alert(error.message);
    } finally {
      restoreDupSelectedBtn.disabled = false;
    }
  });
}

if (confirmDupReviewBtn) {
  confirmDupReviewBtn.addEventListener("click", async () => {
    if (!jobId) {
      window.alert("No job selected.");
      return;
    }
    confirmDupReviewBtn.disabled = true;
    try {
      const payload = await confirmDuplicateReviewRequest(jobId);
      duplicateReviewStatus = payload.review || duplicateReviewStatus;
      updateDuplicateReviewGateUI();
      await loadDuplicateReview(false);
      window.alert("Duplicate review confirmed. Categorization and export are now unlocked.");
    } catch (error) {
      window.alert(error.message);
    } finally {
      confirmDupReviewBtn.disabled = false;
    }
  });
}

if (dupSearchInput) {
  dupSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (applyDupFiltersBtn) {
        applyDupFiltersBtn.click();
      }
    }
  });
}

if (dupPageSizeInput) {
  dupPageSizeInput.addEventListener("change", async () => {
    dupPage = 1;
    try {
      await loadDuplicateReview(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

[dupSourceFileFilter, dupSortBy, dupSortDir].filter(Boolean).forEach((el) => {
  el.addEventListener("change", async () => {
    if (el === dupSourceFileFilter) {
      preferredDupSourceFile = String(dupSourceFileFilter.value || "");
    }
    dupPage = 1;
    try {
      await loadDuplicateReview(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
});

if (dupPageFirstBtn) {
  dupPageFirstBtn.addEventListener("click", async () => {
    if (dupPage <= 1) return;
    dupPage = 1;
    try {
      await loadDuplicateReview(false);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (dupPagePrevBtn) {
  dupPagePrevBtn.addEventListener("click", async () => {
    if (dupPage <= 1) return;
    dupPage -= 1;
    try {
      await loadDuplicateReview(false);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (dupPageNextBtn) {
  dupPageNextBtn.addEventListener("click", async () => {
    const totalPages = getDupTotalPages();
    if (dupPage >= totalPages) return;
    dupPage += 1;
    try {
      await loadDuplicateReview(false);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (dupPageLastBtn) {
  dupPageLastBtn.addEventListener("click", async () => {
    const totalPages = getDupTotalPages();
    if (dupPage >= totalPages) return;
    dupPage = totalPages;
    try {
      await loadDuplicateReview(false);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

// Initial load: fetch the status banner first (fast, no row payload) so the
// gate text appears immediately, then load the (paginated) row table.
async function initDuplicateReviewPage() {
  if (!jobId) {
    return;
  }
  try {
    await refreshDuplicateReviewStatus();
  } catch (error) {
    window.alert(error.message);
  }
  try {
    await loadDuplicateReview(true);
  } catch (error) {
    if (dupSummary) {
      dupSummary.textContent = error.message;
    } else {
      window.alert(error.message);
    }
  }
}

initDuplicateReviewPage();
