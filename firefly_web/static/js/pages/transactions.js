import { apiGet, apiSend, jobIdFromShell } from "../api.js";
import { startPoll } from "../polling.js";
import { mountStepper } from "../stepper.js";
import {
  escapeHtml,
  amountClass,
  renderPageButtonsHtml,
  buildTransactionRowKey,
  renderTransactionRow,
  getTxTotalPages,
  updateTxPagination,
  TableColumnManager,
} from "../tables.js";

const jobId = jobIdFromShell();
mountStepper(jobId);

// ── DOM lookups ──────────────────────────────────────────────────────────
const txContent = document.getElementById("transactions-content");
const txBody = document.getElementById("transactions-body");
const txSummary = document.getElementById("transaction-summary");
const txPageSummaryEl = document.getElementById("tx-page-summary");
const toggleAllVisible = document.getElementById("toggle-all-visible");

const txSearchInput = document.getElementById("tx-search");
const applyTxFiltersBtn = document.getElementById("apply-tx-filters");
const selectVisibleBtn = document.getElementById("select-visible");
const clearSelectionBtn = document.getElementById("clear-selection");
const txColumnsBtn = document.getElementById("tx-columns-btn");
const txPageSizeInput = document.getElementById("tx-page-size");
const txDecisionFilter = document.getElementById("tx-decision-filter");
const txIncludeDroppedInput = document.getElementById("tx-include-dropped");
const txSourceFileFilter = document.getElementById("tx-source-file-filter");
const txSortBy = document.getElementById("tx-sort-by");
const txSortDir = document.getElementById("tx-sort-dir");

const txPageFirstBtn = document.getElementById("tx-page-first");
const txPagePrevBtn = document.getElementById("tx-page-prev");
const txPageButtons = document.getElementById("tx-page-buttons");
const txPageNextBtn = document.getElementById("tx-page-next");
const txPageLastBtn = document.getElementById("tx-page-last");

const overwriteCategoryCheckbox = document.getElementById("overwrite-category");
const categorizeOllamaBtn = document.getElementById("categorize-ollama");
const categorizeAllOllamaBtn = document.getElementById("categorize-all-ollama");
const autoExportAfterCategorizeInput = document.getElementById("auto-export-after-categorize");
const downloadCategorizedCsvBtn = document.getElementById("download-categorized-csv");

const catLogDetails = document.querySelector("details.cat-log");
const ollamaJobFilterInput = document.getElementById("ollama-job-filter");
const ollamaStatusGroupInput = document.getElementById("ollama-status-group");
const ollamaPageSizeInput = document.getElementById("ollama-page-size");
const ollamaSortByInput = document.getElementById("ollama-sort-by");
const ollamaSortDirInput = document.getElementById("ollama-sort-dir");
const refreshOllamaEventsBtn = document.getElementById("refresh-ollama-events");
const ollamaColumnsBtn = document.getElementById("ollama-columns-btn");
const stopOllamaQueueBtn = document.getElementById("stop-ollama-queue");
const deleteOllamaQueueBtn = document.getElementById("delete-ollama-queue");
const ollamaMetricsEl = document.getElementById("ollama-metrics");
const ollamaEventsSummaryEl = document.getElementById("ollama-events-summary");
const ollamaEventsBody = document.getElementById("ollama-events-body");
const ollamaPageFirstBtn = document.getElementById("ollama-page-first");
const ollamaPagePrevBtn = document.getElementById("ollama-page-prev");
const ollamaPageButtons = document.getElementById("ollama-page-buttons");
const ollamaPageNextBtn = document.getElementById("ollama-page-next");
const ollamaPageLastBtn = document.getElementById("ollama-page-last");

// ── Module-level state. Was scattered across SPA globals in app.js
// (selectedRows, txPage, txPageSize, txTotal, txOverallTotal, txDecisionCounts,
// categoryOptions, activeTransactionKey, preferredSourceFile,
// duplicateReviewStatus, ollamaPage, ollamaPageSize, ollamaTotalCount,
// ollamaCurrentFilter, ollamaEventsById); this page owns them directly since
// there is no cross-tab/session state to share them with. ────────────────
const selectedRows = new Set();
let txPage = 1;
let txPageSize = Math.max(1, Number((txPageSizeInput && txPageSizeInput.value) || 20));
let txTotal = 0;
let txOverallTotal = 0;
let txDecisionCounts = { merged: 0, dropped: 0 };
let categoryOptions = [];
let activeTransactionKey = "";
let preferredSourceFile = "";

let duplicateReviewStatus = {
  required: false,
  confirmed: true,
  can_proceed: true,
  pending_duplicates: 0,
  initial_duplicates: 0,
  restored_rows_total: 0,
};
let reviewGateBannerEl = null;

let ollamaConfigBannerEl = null;
let configErrorBannerEl = null;

let ollamaTotalCount = 0;
let ollamaPage = 1;
let ollamaPageSize = Math.max(1, Number((ollamaPageSizeInput && ollamaPageSizeInput.value) || 20));
const ollamaEventsById = new Map();
let ollamaEventsLoadedOnce = false;
let stopOllamaPoll = null;

// ── tables.js column managers ───────────────────────────────────────────
const tcmTransactions = new TableColumnManager({
  tableId: "transactions-table",
  columns: [
    { key: "select", label: "Select", alwaysVisible: true },
    { key: "id", label: "ID", sortKey: "id" },
    { key: "decision", label: "Decision", sortKey: "decision" },
    { key: "date", label: "Date", sortKey: "date" },
    { key: "amount", label: "Amount", sortKey: "amount" },
    { key: "category", label: "Category", sortKey: "category" },
    { key: "description", label: "Description", sortKey: "description" },
    { key: "source_account", label: "Source Account", sortKey: "source_account" },
    { key: "destination_account", label: "Destination Account", sortKey: "destination_account", defaultHidden: true },
    { key: "dropped_pairing", label: "Dropped Pairing" },
    { key: "details", label: "Details", alwaysVisible: true },
  ],
  sortByEl: txSortBy,
  sortDirEl: txSortDir,
  applyEl: applyTxFiltersBtn,
});
tcmTransactions.bindHeaderEvents();
if (txColumnsBtn) {
  txColumnsBtn.addEventListener("click", () => tcmTransactions.openPicker(txColumnsBtn));
}

const tcmOllama = new TableColumnManager({
  tableId: "ollama-events-table",
  columns: [
    { key: "id", label: "ID", sortKey: "id" },
    { key: "status", label: "Status", sortKey: "status" },
    { key: "date", label: "Date", sortKey: "date" },
    { key: "amount", label: "Amount", sortKey: "amount" },
    { key: "category", label: "Category", sortKey: "category" },
    { key: "description", label: "Description", sortKey: "description" },
    { key: "source_account", label: "Source Account", sortKey: "source_account", defaultHidden: true },
    { key: "destination_account", label: "Destination Account", sortKey: "destination_account", defaultHidden: true },
    { key: "actions", label: "Actions", alwaysVisible: true },
  ],
  sortByEl: ollamaSortByInput,
  sortDirEl: ollamaSortDirInput,
  onRedraw: () => loadOllamaEvents({ resetPage: false }).catch((error) => window.alert(error.message)),
});
tcmOllama.bindHeaderEvents();
if (ollamaColumnsBtn) {
  ollamaColumnsBtn.addEventListener("click", () => tcmOllama.openPicker(ollamaColumnsBtn));
}

// ── API layer, extracted from app.js (buildTransactionQuery ~1026,
// fetchTransactions ~1041, fetchTransactionDetail ~814, categorize ~1059,
// updateTransactionCategory ~1082, fetchDuplicateReviewStatus ~826,
// fetchOllamaEvents ~736, fetchOllamaEvent ~769, stopOllamaQueue ~778,
// deleteOllamaQueue ~791, deleteOllamaQueueItem ~805). Rewired onto
// api.js's apiGet/apiSend, which already extract `detail` from error
// responses, so the manual `response.ok`/`payload.detail` checks are dropped. ──
function buildTransactionQuery(offset, limit) {
  const params = new URLSearchParams();
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  params.set("include_details", "false");
  params.set("include_duplicates", "true");
  params.set("include_dropped", txIncludeDroppedInput && txIncludeDroppedInput.checked ? "true" : "false");
  params.set("decision", String((txDecisionFilter && txDecisionFilter.value) || "all"));
  params.set("search", String((txSearchInput && txSearchInput.value) || ""));
  params.set("source_file", String((txSourceFileFilter && txSourceFileFilter.value) || ""));
  params.set("sort_by", String((txSortBy && txSortBy.value) || "date"));
  params.set("sort_dir", String((txSortDir && txSortDir.value) || "asc"));
  return params;
}

async function fetchTransactions(id, offset, limit) {
  return apiGet(`/api/jobs/${id}/transactions?${buildTransactionQuery(offset, limit).toString()}`);
}

async function fetchTransactionDetail(id, rowSource, rowLocalIndex) {
  const params = new URLSearchParams();
  params.set("row_source", String(rowSource || ""));
  params.set("row_local_index", String(rowLocalIndex || 0));
  return apiGet(`/api/jobs/${id}/transactions/detail?${params.toString()}`);
}

async function fetchDuplicateReviewStatus(id) {
  return apiGet(`/api/jobs/${id}/duplicates/review/status`);
}

async function fetchSystemConfig() {
  return apiGet("/api/config");
}

async function categorize(id, mode, rowIndices, options = {}) {
  return apiSend(`/api/jobs/${id}/categorize/${mode}`, "POST", {
    row_indices: rowIndices,
    overwrite: !!(overwriteCategoryCheckbox && overwriteCategoryCheckbox.checked),
    auto_export: options.autoExport === true,
  });
}

function downloadCategorizedCsv(id) {
  const url = `/api/jobs/${encodeURIComponent(id)}/transactions/categorized.csv`;
  window.open(url, "_blank", "noopener");
}

async function updateTransactionCategory(id, mergeRowIndex, category) {
  return apiSend(`/api/jobs/${id}/transactions/category`, "POST", {
    merge_row_index: mergeRowIndex,
    category: category || "",
  });
}

async function fetchOllamaEvents({
  limit = 20,
  offset = 0,
  jobIdFilter = "",
  statusGroup = "all",
  sortBy = "id",
  sortDir = "asc",
} = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  params.set("include_payload", "false");
  params.set("status_group", String(statusGroup || "all"));
  params.set("sort_by", String(sortBy || "id"));
  params.set("sort_dir", String(sortDir || "asc"));
  if (jobIdFilter) {
    params.set("job_id", jobIdFilter);
  }
  return apiGet(`/api/ollama/events?${params.toString()}`);
}

async function fetchOllamaEvent(eventId) {
  return apiGet(`/api/ollama/events/${Number(eventId || 0)}`);
}

async function stopOllamaQueue(id) {
  return apiSend("/api/ollama/queues/stop", "POST", { job_id: String(id || "") });
}

async function deleteOllamaQueue(id, statusGroup = "all") {
  const params = new URLSearchParams();
  if (id) {
    params.set("job_id", String(id));
  }
  params.set("status_group", String(statusGroup || "all"));
  return apiSend(`/api/ollama/queues?${params.toString()}`, "DELETE");
}

async function deleteOllamaQueueItem(eventId) {
  return apiSend(`/api/ollama/events/${Number(eventId || 0)}`, "DELETE");
}

// ── Duplicate-review gate (plan step 12.2). Replaces
// applyDuplicateReviewGateToActions (app.js:1461) for this page: instead of
// painting the SPA's inline stepper/cross-tab buttons, it disables this
// page's own categorize buttons and inserts a `.banner.warn` before the
// table (the backend still 409s as a backstop via _ensure_duplicate_review_ready). ──
function renderReviewGateBanner() {
  const pending = Number(duplicateReviewStatus.pending_duplicates || 0);
  const blocked = !duplicateReviewStatus.can_proceed;

  if (categorizeOllamaBtn) categorizeOllamaBtn.disabled = blocked;
  if (categorizeAllOllamaBtn) categorizeAllOllamaBtn.disabled = blocked;

  if (!txContent) {
    return;
  }
  if (!blocked) {
    if (reviewGateBannerEl) {
      reviewGateBannerEl.remove();
      reviewGateBannerEl = null;
    }
    return;
  }
  if (!reviewGateBannerEl) {
    reviewGateBannerEl = document.createElement("div");
    reviewGateBannerEl.className = "banner warn";
    reviewGateBannerEl.id = "tx-review-gate-banner";
    const tableWrap = txContent.querySelector(".table-wrap");
    if (tableWrap) {
      tableWrap.before(reviewGateBannerEl);
    } else {
      txContent.prepend(reviewGateBannerEl);
    }
  }
  reviewGateBannerEl.innerHTML =
    `Review ${pending} flagged duplicates before categorizing. ` +
    `<a href="/jobs/${escapeHtml(jobId)}/review">Go to review</a>`;
}

async function refreshDuplicateReviewGate() {
  if (!jobId) {
    return;
  }
  duplicateReviewStatus = await fetchDuplicateReviewStatus(jobId);
  renderReviewGateBanner();
}

// ── Ollama config gate (usability fix): the Ollama categorize buttons
// used to 400 with no visible explanation when Ollama is disabled/
// unconfigured in Configuration. Mirrors renderReviewGateBanner's
// disable-buttons + insert-`.banner.warn`-before-`.table-wrap` mechanism,
// but fails open on a config fetch error (no banner, buttons stay enabled)
// since the backend 400 remains the backstop either way. ──
function applyOllamaConfigGate(config) {
  const ollamaCfg = (config && typeof config === "object" && config.ollama) || {};
  const enabled = !!ollamaCfg.enabled;
  const url = String(ollamaCfg.url || "").trim();
  const model = String(ollamaCfg.model || "").trim();
  const configured = enabled && !!url && !!model;

  if (categorizeOllamaBtn) {
    categorizeOllamaBtn.disabled = categorizeOllamaBtn.disabled || !configured;
    if (!configured) categorizeOllamaBtn.title = "Ollama is not enabled/configured. Enable it in Configuration.";
  }
  if (categorizeAllOllamaBtn) {
    categorizeAllOllamaBtn.disabled = categorizeAllOllamaBtn.disabled || !configured;
    if (!configured) categorizeAllOllamaBtn.title = "Ollama is not enabled/configured. Enable it in Configuration.";
  }

  if (!txContent) {
    return;
  }
  if (configured) {
    if (ollamaConfigBannerEl) {
      ollamaConfigBannerEl.remove();
      ollamaConfigBannerEl = null;
    }
    return;
  }
  if (!ollamaConfigBannerEl) {
    ollamaConfigBannerEl = document.createElement("div");
    ollamaConfigBannerEl.className = "banner warn";
    ollamaConfigBannerEl.id = "tx-ollama-config-banner";
    const tableWrap = txContent.querySelector(".table-wrap");
    if (tableWrap) {
      tableWrap.before(ollamaConfigBannerEl);
    } else {
      txContent.prepend(ollamaConfigBannerEl);
    }
  }
  ollamaConfigBannerEl.innerHTML =
    `AI categorization is off — <a href="/config#config-ollama">enable Ollama in Configuration</a>. ` +
    `You can still set categories manually below.`;
}

async function refreshOllamaConfigGate() {
  try {
    const config = await fetchSystemConfig();
    applyOllamaConfigGate(config);
  } catch {
    // Fail open: leave buttons/banner as-is, the backend 400 is the backstop.
  }
}

// ── Config-error banner (usability fix): surfaces config-dependent
// categorize failures (e.g. "Ollama categorization is disabled in
// configuration.") with a link to Configuration, in addition to the
// existing window.alert. ──
function isConfigError(message) {
  const text = String(message || "").toLowerCase();
  return (
    text.includes("disabled in configuration") ||
    text.includes("missing in configuration") ||
    text.includes("not configured")
  );
}

function showConfigErrorBanner(message) {
  if (!txContent) {
    return;
  }
  if (!configErrorBannerEl) {
    configErrorBannerEl = document.createElement("div");
    configErrorBannerEl.className = "banner error";
    configErrorBannerEl.id = "tx-config-error-banner";
    const tableWrap = txContent.querySelector(".table-wrap");
    if (tableWrap) {
      tableWrap.before(configErrorBannerEl);
    } else {
      txContent.prepend(configErrorBannerEl);
    }
  }
  configErrorBannerEl.innerHTML = `${escapeHtml(String(message || ""))} <a href="/config">Open Configuration</a>.`;
}

function clearConfigErrorBanner() {
  if (configErrorBannerEl) {
    configErrorBannerEl.remove();
    configErrorBannerEl = null;
  }
}

// Re-checked immediately before every categorize action (mirrors app.js's
// ensureDuplicateReviewReadyForProcessing ~2397); the backend also 409s as a
// backstop, but re-fetching here keeps the banner/button state in sync and
// gives the user a clear error instead of a raw HTTP failure.
async function ensureDuplicateReviewReady() {
  await refreshDuplicateReviewGate();
  if (duplicateReviewStatus.can_proceed) {
    return;
  }
  const pending = Number(duplicateReviewStatus.pending_duplicates || 0);
  throw new Error(
    `Duplicate review required before categorization. Pending suspected duplicates: ${pending}. ` +
    `Go to /jobs/${jobId}/review to resolve.`
  );
}

// ── Rendering / loading, extracted from app.js (clearTransactionState
// ~1153, populateSourceFileFilter ~1185, loadTransactions ~1201,
// updateTransactionSummary ~1338, wireRowCheckboxes ~1352,
// wireTransactionDetailButtons ~1369, selectTransactionRow ~1408,
// openTransactionDetail ~1415). GLOBAL -> MODULE-LOCAL: all reads of
// txPage/txPageSize/txTotal/txOverallTotal/txDecisionCounts/categoryOptions/
// selectedRows/activeTransactionKey/preferredSourceFile now hit the
// module-level state declared above instead of SPA globals shared with
// other tabs. ──
function populateSourceFileFilter(files, keepCurrent = true) {
  if (!txSourceFileFilter) {
    return;
  }
  const sourceFiles = Array.isArray(files) ? files : [];
  const current = keepCurrent ? String(txSourceFileFilter.value || "") : "";
  txSourceFileFilter.innerHTML = [
    `<option value="">All source files</option>`,
    ...sourceFiles.map((f) => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`),
  ].join("");

  if (current && sourceFiles.includes(current)) {
    txSourceFileFilter.value = current;
    preferredSourceFile = current;
    return;
  }
  if (preferredSourceFile && sourceFiles.includes(preferredSourceFile)) {
    txSourceFileFilter.value = preferredSourceFile;
    return;
  }
  txSourceFileFilter.value = "";
}

function clearTransactionState() {
  selectedRows.clear();
  txPage = 1;
  txTotal = 0;
  txOverallTotal = 0;
  txDecisionCounts = { merged: 0, dropped: 0 };
  activeTransactionKey = "";
  if (txBody) txBody.innerHTML = "";
  if (toggleAllVisible) toggleAllVisible.checked = false;
  if (txSummary) {
    txSummary.textContent = "No transactions loaded.";
  }
  if (txPageSummaryEl) {
    txPageSummaryEl.textContent = "Rows 0-0 of 0";
  }
  updateTxPagination(txPage, getTxTotalPages(txTotal, txPageSize), txPaginationEls(), onTxPageChange);
}

function updateTransactionSummary() {
  if (!txSummary) {
    return;
  }
  const mergedCount = Number(txDecisionCounts.merged || 0);
  const droppedCount = Number(txDecisionCounts.dropped || 0);
  const droppedMode = txIncludeDroppedInput && txIncludeDroppedInput.checked ? "including" : "excluding";
  txSummary.textContent =
    `Showing page ${txPage}/${getTxTotalPages(txTotal, txPageSize)} (${txTotal} filtered, ${txOverallTotal} overall, ${droppedMode} dropped rows). ` +
    `Merged: ${mergedCount}, Dropped: ${droppedCount}. Selected merged rows: ${selectedRows.size}.`;
  if (txPageSummaryEl) {
    txPageSummaryEl.textContent = `Rows ${txTotal ? ((txPage - 1) * txPageSize) + 1 : 0}-${Math.min(txPage * txPageSize, txTotal)} of ${txTotal}`;
  }
}

function wireRowCheckboxes() {
  if (!txBody) return;
  txBody.querySelectorAll(".row-checkbox").forEach((cb) => {
    cb.addEventListener("change", (event) => {
      const idx = Number(event.target.dataset.mergeRowIndex || 0);
      if (!idx) {
        return;
      }
      if (event.target.checked) {
        selectedRows.add(idx);
      } else {
        selectedRows.delete(idx);
      }
      updateTransactionSummary();
    });
  });
  txBody.querySelectorAll(".tx-category-select").forEach((select) => {
    select.addEventListener("change", async (event) => {
      const mergeRowIndex = Number(event.target.dataset.mergeRowIndex || 0);
      if (!mergeRowIndex || !jobId) {
        return;
      }
      const category = String(event.target.value || "");
      select.disabled = true;
      try {
        await updateTransactionCategory(jobId, mergeRowIndex, category);
      } catch (error) {
        window.alert(error.message);
      } finally {
        select.disabled = false;
      }
    });
  });
}

// Detail view, degraded from app.js's openTransactionDetail/openDetailModal
// (app.js:1415/2220): the MPA templates carry no detail-modal element (see
// task-11-report.md for the same gap on the review page), so the fetched
// detail is rendered as a plain-text window.alert instead of HTML in a
// modal. Row/"Open" button selection highlighting is kept (selectTransactionRow)
// since it's a harmless, still-functional visual affordance.
function buildDetailAlertText(title, detail) {
  const keys = Object.keys(detail || {}).sort((a, b) => a.localeCompare(b));
  const lines = keys.map((key) => {
    const raw = detail[key];
    const value = raw && typeof raw === "object" ? JSON.stringify(raw) : String(raw ?? "");
    return `${key}: ${value}`;
  });
  return [title, ...lines].join("\n");
}

function selectTransactionRow(rowSource, rowLocalIndex) {
  activeTransactionKey = buildTransactionRowKey(rowSource, rowLocalIndex);
  if (!txBody) return;
  txBody.querySelectorAll("tr[data-row-key]").forEach((row) => {
    row.classList.toggle("selected", String(row.dataset.rowKey || "") === activeTransactionKey);
  });
}

async function openTransactionDetail(rowSource, rowLocalIndex, rowId = "") {
  if (!rowSource || !rowLocalIndex || !jobId) {
    return;
  }
  selectTransactionRow(rowSource, rowLocalIndex);
  const detail = await fetchTransactionDetail(jobId, rowSource, rowLocalIndex);
  const displayId = String(rowId || detail.id || `${rowSource}:${rowLocalIndex}`);
  window.alert(buildDetailAlertText(`Transaction ${displayId}`, detail));
}

function wireTransactionDetailButtons() {
  if (!txBody) return;
  txBody.querySelectorAll("tr[data-row-source][data-row-local-index]").forEach((row) => {
    row.addEventListener("click", async (event) => {
      const target = event.target;
      if (target && target.closest && target.closest("button, input, select, a, label")) {
        return;
      }
      const rowSource = String(row.dataset.rowSource || "");
      const rowLocalIndex = Number(row.dataset.rowLocalIndex || 0);
      const rowId = String(row.dataset.rowId || "");
      try {
        await openTransactionDetail(rowSource, rowLocalIndex, rowId);
      } catch (error) {
        window.alert(error.message);
      }
    });
  });

  txBody.querySelectorAll(".tx-open-detail").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const rowSource = String(btn.dataset.rowSource || "");
      const rowLocalIndex = Number(btn.dataset.rowLocalIndex || 0);
      const rowId = String(btn.dataset.rowId || "");
      try {
        await openTransactionDetail(rowSource, rowLocalIndex, rowId);
      } catch (error) {
        window.alert(error.message);
      }
    });
  });
}

function txPaginationEls() {
  return {
    firstBtn: txPageFirstBtn,
    prevBtn: txPagePrevBtn,
    nextBtn: txPageNextBtn,
    lastBtn: txPageLastBtn,
    pageButtons: txPageButtons,
  };
}

function onTxPageChange(page) {
  txPage = page;
  loadTransactions(false).catch((error) => window.alert(error.message));
}

async function loadTransactions(reset = false) {
  if (!jobId) {
    clearTransactionState();
    if (txSummary) {
      txSummary.textContent = "No job selected.";
    }
    return;
  }
  if (reset) {
    txPage = 1;
  }

  txPageSize = Math.max(1, Number((txPageSizeInput && txPageSizeInput.value) || 20));
  const limit = txPageSize;
  const offset = (Math.max(1, txPage) - 1) * limit;
  const payload = await fetchTransactions(jobId, offset, limit);

  txOverallTotal = Number(payload.overall_total || 0);
  txTotal = Number(payload.total || 0);
  txDecisionCounts = payload.decision_counts || { merged: 0, dropped: 0 };
  categoryOptions = Array.isArray(payload.categories) ? payload.categories : categoryOptions;
  populateSourceFileFilter(payload.source_files || [], true);

  const rows = payload.rows || [];
  if (txBody) {
    txBody.innerHTML = rows.length
      ? rows.map((row) => renderTransactionRow(row, selectedRows, activeTransactionKey, categoryOptions)).join("")
      : `<tr><td colspan="11">No transactions for current filters.</td></tr>`;
  }
  tcmTransactions.applyToTable();

  const totalPages = getTxTotalPages(txTotal, txPageSize);
  if (txPage > totalPages) {
    txPage = totalPages;
    await loadTransactions(false);
    return;
  }

  wireRowCheckboxes();
  wireTransactionDetailButtons();
  updateTransactionSummary();
  updateTxPagination(txPage, totalPages, txPaginationEls(), onTxPageChange);
}

// ── Categorization actions, extracted from app.js's runCategorization
// (~2415). GLOBAL -> LOCAL: showToast() -> window.alert(); the tab-switch
// (activateMainTab/activateSubTab into the Ollama tab) is dropped since the
// audit log lives in a <details> on this same page, not a separate tab --
// it's opened programmatically instead (see catLogDetails handling below).
// Note: this template only exposes Ollama-mode categorize buttons
// (categorize-ollama / categorize-all-ollama); the backend's `default` mode
// (POST /api/jobs/{id}/categorize/default, keyword-rule based, no Ollama
// server required) has no corresponding button in transactions.html or in
// the pre-migration index.html/app.js either -- this is a pre-existing gap
// in the legacy UI, not something dropped by this task. `categorize()` above
// is mode-agnostic so a future task can wire a default-categorize button
// without any API-layer changes. ──
async function runCategorization(mode, allRows) {
  if (!jobId) {
    window.alert("No job selected.");
    return;
  }
  let selection = null;
  if (!allRows) {
    if (!selectedRows.size) {
      window.alert("Select at least one merged transaction.");
      return;
    }
    selection = Array.from(selectedRows).sort((a, b) => a - b);
  }

  try {
    await ensureDuplicateReviewReady();
    const isOllama = mode === "ollama";
    const autoExport = !!(autoExportAfterCategorizeInput && autoExportAfterCategorizeInput.checked && isOllama);

    const result = await categorize(jobId, mode, selection, { autoExport });
    clearConfigErrorBanner();
    if (mode === "ollama") {
      const exportInfo = result.auto_export
        ? (result.export_id ? ` Auto export job: ${result.export_id}.` : " Auto export is enabled; categorized batches will be queued to export.")
        : "";
      window.alert(`Ollama categorization queued. Queued: ${result.queued ?? 0}, skipped: ${result.skipped ?? 0}.${exportInfo}`);
      if (catLogDetails) catLogDetails.open = true;
      await loadOllamaEvents({ resetPage: true });
    } else {
      window.alert(`Categorization done. Updated ${result.updated}, skipped ${result.skipped}.`);
    }
    selectedRows.clear();
    await loadTransactions(true);
  } catch (error) {
    if (isConfigError(error.message)) {
      showConfigErrorBanner(error.message);
    }
    window.alert(error.message);
  }
}

// ── Ollama queue / audit log, extracted from app.js (fetchOllamaEvents
// ~736, fetchOllamaEvent ~769, stopOllamaQueue ~778, deleteOllamaQueue ~791,
// deleteOllamaQueueItem ~805, renderOllamaEvents ~2552, loadOllamaEvents
// ~2631, getOllamaTotalPages ~2665, updateOllamaPagination ~2669,
// updateOllamaMetrics ~2385, selectOllamaEvent ~1804, startOllamaPolling/
// stopOllamaPolling ~309-329). GLOBAL -> LOCAL: showToast -> window.alert,
// showConfirm -> window.confirm; startOllamaPolling/stopOllamaPolling (which
// gated on the SPA's active-tab bookkeeping) reworked onto polling.js's
// startPoll, gated instead on the <details class="cat-log"> element's `open`
// state so the collapsed audit log doesn't poll while hidden. selectOllamaEvent's
// openDetailModal() call degrades to window.alert for the same reason as
// openTransactionDetail above (no detail-modal element on this page). ──
function humanDurationFromMinutes(minutes) {
  const m = Number(minutes || 0);
  if (!Number.isFinite(m) || m <= 0) {
    return "-";
  }
  if (m < 1) {
    return `${Math.max(1, Math.round(m * 60))} sec`;
  }
  if (m < 60) {
    return `${m.toFixed(1)} min`;
  }
  const hours = Math.floor(m / 60);
  const rem = Math.round(m % 60);
  return `${hours}h ${rem}m`;
}

function parseIsoTs(value) {
  const ts = Date.parse(String(value || "").trim());
  return Number.isFinite(ts) ? ts : null;
}

function buildQueueProgressModel(metrics) {
  const safe = metrics && typeof metrics === "object" ? metrics : {};
  const totals = {
    queued: Number(safe.queued || 0),
    running: Number(safe.running || 0),
    completed: Number(safe.completed || 0),
    failed: Number(safe.failed || 0),
  };
  const total = Number(safe.total || 0);
  const processed = totals.completed + totals.failed;
  const remaining = Math.max(0, total - processed);

  let speedPerMinute = 0;
  let etaMinutes = 0;
  const firstStarted = parseIsoTs(safe.first_started_at);
  if (firstStarted !== null && processed > 0) {
    const elapsedMinutes = Math.max((Date.now() - firstStarted) / 60000, 1 / 60);
    speedPerMinute = processed / elapsedMinutes;
    if (speedPerMinute > 0) {
      etaMinutes = remaining / speedPerMinute;
    }
  }

  return {
    total,
    queued: totals.queued,
    running: totals.running,
    completed: totals.completed,
    failed: totals.failed,
    processed,
    remaining,
    progressPct: total > 0 ? (processed / total) * 100 : 0,
    speedPerMinute,
    etaMinutes,
  };
}

function queueSpeedText(model) {
  return model.speedPerMinute > 0 ? `${model.speedPerMinute.toFixed(2)} tx/min` : "-";
}

function queueEtaText(model) {
  if (!(model.speedPerMinute > 0) || model.remaining <= 0) {
    return "ETA: -";
  }
  const etaAt = new Date(Date.now() + model.etaMinutes * 60000);
  return `ETA: ${humanDurationFromMinutes(model.etaMinutes)} (around ${etaAt.toLocaleTimeString()})`;
}

function queueProgressLine(model) {
  return (
    `Queue progress: ${model.processed}/${model.total} (${model.progressPct.toFixed(1)}%). ` +
    `Queued: ${model.queued}, Running: ${model.running}, Completed: ${model.completed}, Failed: ${model.failed}. ` +
    `Speed: ${queueSpeedText(model)}. ${queueEtaText(model)}`
  );
}

function updateOllamaMetrics(metrics) {
  if (!ollamaMetricsEl) {
    return;
  }
  const model = buildQueueProgressModel(metrics);
  if (model.total <= 0) {
    ollamaMetricsEl.textContent = "No Ollama queue metrics yet.";
    return;
  }
  ollamaMetricsEl.textContent = queueProgressLine(model);
}

function renderStatusChip(status) {
  const s = String(status || "unknown").toLowerCase();
  return `<span class="status-chip ${escapeHtml(s)}">${escapeHtml(s)}</span>`;
}

async function selectOllamaEvent(eventId) {
  const event = ollamaEventsById.get(Number(eventId || 0));
  if (!event) {
    return;
  }
  if (!ollamaEventsBody) return;
  ollamaEventsBody.querySelectorAll("tr").forEach((row) => {
    row.classList.toggle("selected", Number(row.dataset.eventId || 0) === Number(eventId));
  });
  try {
    const detail = await fetchOllamaEvent(eventId);
    ollamaEventsById.set(Number(eventId), detail);
    const lines = [
      `Ollama Event ${eventId}`,
      `status: ${detail.status || ""}`,
      `job_id: ${detail.job_id || ""}`,
      `merge_row_index: ${detail.merge_row_index || ""}`,
      `model: ${detail.model || ""}`,
      `date: ${detail.date || ""}`,
      `amount: ${detail.amount || ""}`,
      `category: ${detail.category || ""}`,
      `description: ${detail.description || ""}`,
      `error: ${detail.error || ""}`,
      "",
      "Prompt:",
      String(detail.prompt || ""),
      "",
      "Response:",
      String(detail.response || ""),
    ];
    window.alert(lines.join("\n"));
  } catch (error) {
    window.alert(error.message);
  }
}

function renderOllamaEventRow(event) {
  const id = Number(event.id || 0);
  if (id) {
    ollamaEventsById.set(id, event);
  }
  return `
    <tr data-event-id="${id}">
      <td data-col="id" data-label="ID"><code>${escapeHtml(String(id))}</code></td>
      <td data-col="status" data-label="Status">${renderStatusChip(event.status)}</td>
      <td data-col="date" data-label="Date">${escapeHtml(event.date || "")}</td>
      <td data-col="amount" data-label="Amount" class="num${amountClass(event.amount)}">${escapeHtml(event.amount || "")}</td>
      <td data-col="category" data-label="Category">${escapeHtml(event.category || "")}</td>
      <td data-col="description" data-label="Description">${escapeHtml(event.description || "")}</td>
      <td data-col="source_account" data-label="Source Account">${escapeHtml(event.source_account || "")}</td>
      <td data-col="destination_account" data-label="Destination Account">${escapeHtml(event.destination_account || "")}</td>
      <td data-col="actions" data-label="Actions" class="actions-cell">
        <div class="small-controls">
          <button type="button" class="ollama-event-open secondary-btn" data-event-id="${id}">Open</button>
          <button type="button" class="ollama-event-delete danger-btn" data-event-id="${id}" ${String(event.status || "") === "running" ? "disabled" : ""}>Delete</button>
        </div>
      </td>
    </tr>
  `;
}

function renderOllamaEvents(events) {
  ollamaEventsById.clear();
  if (!ollamaEventsBody) return;

  if (!events.length) {
    ollamaEventsBody.innerHTML = `<tr><td colspan="9">No Ollama events yet.</td></tr>`;
    return;
  }

  ollamaEventsBody.innerHTML = events.map((event) => renderOllamaEventRow(event)).join("");
  tcmOllama.applyToTable();

  ollamaEventsBody.querySelectorAll(".ollama-event-open").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      selectOllamaEvent(Number(btn.dataset.eventId || 0));
    });
  });
  ollamaEventsBody.querySelectorAll(".ollama-event-delete").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const eventId = Number(btn.dataset.eventId || 0);
      if (!eventId) return;
      if (!window.confirm(`Delete Ollama queue item ${eventId}?`)) return;
      try {
        await deleteOllamaQueueItem(eventId);
        await loadOllamaEvents({ resetPage: false });
      } catch (error) {
        window.alert(error.message);
      }
    });
  });
  ollamaEventsBody.querySelectorAll("tr[data-event-id]").forEach((row) => {
    row.addEventListener("click", () => selectOllamaEvent(Number(row.dataset.eventId || 0)));
  });
}

function getOllamaTotalPages() {
  return Math.max(1, Math.ceil(ollamaTotalCount / Math.max(1, ollamaPageSize)));
}

function updateOllamaPagination() {
  const totalPages = getOllamaTotalPages();
  const canPrev = ollamaPage > 1;
  const canNext = ollamaPage < totalPages;
  if (ollamaPageFirstBtn) ollamaPageFirstBtn.disabled = !canPrev;
  if (ollamaPagePrevBtn) ollamaPagePrevBtn.disabled = !canPrev;
  if (ollamaPageNextBtn) ollamaPageNextBtn.disabled = !canNext;
  if (ollamaPageLastBtn) ollamaPageLastBtn.disabled = !canNext;
  if (!ollamaPageButtons) {
    return;
  }
  ollamaPageButtons.innerHTML = renderPageButtonsHtml(ollamaPage, totalPages, "ollama-page-btn");
  ollamaPageButtons.querySelectorAll(".ollama-page-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const page = Number(btn.dataset.page || 1);
      if (page === ollamaPage) {
        return;
      }
      ollamaPage = page;
      try {
        await loadOllamaEvents({ resetPage: false });
      } catch (error) {
        window.alert(error.message);
      }
    });
  });
}

function updateOllamaEventListMeta() {
  if (ollamaEventsSummaryEl) {
    const totalPages = getOllamaTotalPages();
    const jobFilter = String((ollamaJobFilterInput && ollamaJobFilterInput.value) || "").trim();
    const filterText = jobFilter ? ` for job ${jobFilter}` : "";
    const start = ollamaTotalCount ? (ollamaPage - 1) * ollamaPageSize + 1 : 0;
    const end = Math.min(ollamaPage * ollamaPageSize, ollamaTotalCount);
    ollamaEventsSummaryEl.textContent = `Rows ${start}-${end} of ${ollamaTotalCount}. Page ${ollamaPage}/${totalPages}${filterText}.`;
  }
  updateOllamaPagination();
}

async function loadOllamaEvents(options = {}) {
  const resetPage = options.resetPage === true;
  if (resetPage) {
    ollamaPage = 1;
  }
  ollamaPageSize = Math.max(1, Number((ollamaPageSizeInput && ollamaPageSizeInput.value) || 20));
  const jobFilter = String((ollamaJobFilterInput && ollamaJobFilterInput.value) || "").trim();
  const statusGroup = String((ollamaStatusGroupInput && ollamaStatusGroupInput.value) || "all");
  const sortBy = String((ollamaSortByInput && ollamaSortByInput.value) || "id");
  const sortDir = String((ollamaSortDirInput && ollamaSortDirInput.value) || "asc");

  const offset = (Math.max(1, ollamaPage) - 1) * ollamaPageSize;
  const payload = await fetchOllamaEvents({
    limit: ollamaPageSize,
    offset,
    jobIdFilter: jobFilter,
    statusGroup,
    sortBy,
    sortDir,
  });
  const events = Array.isArray(payload.events) ? payload.events : [];
  ollamaTotalCount = Number(payload.total || 0);
  updateOllamaMetrics(payload.metrics || {});
  const totalPages = getOllamaTotalPages();
  if (ollamaPage > totalPages) {
    ollamaPage = totalPages;
    await loadOllamaEvents({ resetPage: false });
    return;
  }
  ollamaEventsLoadedOnce = true;
  renderOllamaEvents(events);
  updateOllamaEventListMeta();
}

// ── Event bindings ───────────────────────────────────────────────────────
if (toggleAllVisible) {
  toggleAllVisible.addEventListener("change", (event) => {
    const checked = !!event.target.checked;
    if (!txBody) return;
    txBody.querySelectorAll(".row-checkbox:not(:disabled)").forEach((cb) => {
      cb.checked = checked;
      const idx = Number(cb.dataset.mergeRowIndex || 0);
      if (!idx) return;
      if (checked) {
        selectedRows.add(idx);
      } else {
        selectedRows.delete(idx);
      }
    });
    updateTransactionSummary();
  });
}

if (applyTxFiltersBtn) {
  applyTxFiltersBtn.addEventListener("click", async () => {
    try {
      await loadTransactions(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (txSearchInput) {
  txSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (applyTxFiltersBtn) applyTxFiltersBtn.click();
    }
  });
}

if (selectVisibleBtn) {
  selectVisibleBtn.addEventListener("click", () => {
    if (!txBody) return;
    txBody.querySelectorAll(".row-checkbox:not(:disabled)").forEach((cb) => {
      cb.checked = true;
      const idx = Number(cb.dataset.mergeRowIndex || 0);
      if (idx) selectedRows.add(idx);
    });
    updateTransactionSummary();
  });
}

if (clearSelectionBtn) {
  clearSelectionBtn.addEventListener("click", () => {
    selectedRows.clear();
    if (toggleAllVisible) toggleAllVisible.checked = false;
    if (!txBody) return;
    txBody.querySelectorAll(".row-checkbox").forEach((cb) => {
      cb.checked = false;
    });
    updateTransactionSummary();
  });
}

if (txPageSizeInput) {
  txPageSizeInput.addEventListener("change", async () => {
    try {
      await loadTransactions(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

[txDecisionFilter, txIncludeDroppedInput, txSourceFileFilter, txSortBy, txSortDir].filter(Boolean).forEach((el) => {
  el.addEventListener("change", async () => {
    if (el === txSourceFileFilter) {
      preferredSourceFile = String(txSourceFileFilter.value || "");
    }
    try {
      await loadTransactions(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
});

if (categorizeOllamaBtn) {
  categorizeOllamaBtn.addEventListener("click", () => runCategorization("ollama", false));
}
if (categorizeAllOllamaBtn) {
  categorizeAllOllamaBtn.addEventListener("click", () => runCategorization("ollama", true));
}
if (downloadCategorizedCsvBtn) {
  downloadCategorizedCsvBtn.addEventListener("click", () => {
    if (!jobId) {
      window.alert("No job selected.");
      return;
    }
    downloadCategorizedCsv(jobId);
  });
}

if (refreshOllamaEventsBtn) {
  refreshOllamaEventsBtn.addEventListener("click", async () => {
    try {
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (stopOllamaQueueBtn) {
  stopOllamaQueueBtn.addEventListener("click", async () => {
    const jobFilter = String((ollamaJobFilterInput && ollamaJobFilterInput.value) || jobId || "");
    try {
      await stopOllamaQueue(jobFilter);
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      window.alert(error.message);
    }
  });
}

if (deleteOllamaQueueBtn) {
  deleteOllamaQueueBtn.addEventListener("click", async () => {
    const jobFilter = String((ollamaJobFilterInput && ollamaJobFilterInput.value) || jobId || "");
    const statusGroup = String((ollamaStatusGroupInput && ollamaStatusGroupInput.value) || "all");
    if (!window.confirm(`Delete Ollama queue items${jobFilter ? ` for job ${jobFilter}` : ""} (${statusGroup})?`)) {
      return;
    }
    try {
      await deleteOllamaQueue(jobFilter, statusGroup);
      await loadOllamaEvents({ resetPage: true });
    } catch (error) {
      window.alert(error.message);
    }
  });
}

[ollamaJobFilterInput, ollamaStatusGroupInput, ollamaPageSizeInput, ollamaSortByInput, ollamaSortDirInput]
  .filter(Boolean)
  .forEach((el) => {
    const evt = el === ollamaJobFilterInput ? "keydown" : "change";
    el.addEventListener(evt, async (event) => {
      if (evt === "keydown" && event.key !== "Enter") return;
      try {
        await loadOllamaEvents({ resetPage: true });
      } catch (error) {
        window.alert(error.message);
      }
    });
  });

if (txPageFirstBtn) {
  txPageFirstBtn.addEventListener("click", () => {
    if (txPage <= 1) return;
    onTxPageChange(1);
  });
}
if (txPagePrevBtn) {
  txPagePrevBtn.addEventListener("click", () => {
    if (txPage <= 1) return;
    onTxPageChange(txPage - 1);
  });
}
if (txPageNextBtn) {
  txPageNextBtn.addEventListener("click", () => {
    const totalPages = getTxTotalPages(txTotal, txPageSize);
    if (txPage >= totalPages) return;
    onTxPageChange(txPage + 1);
  });
}
if (txPageLastBtn) {
  txPageLastBtn.addEventListener("click", () => {
    const totalPages = getTxTotalPages(txTotal, txPageSize);
    if (txPage >= totalPages) return;
    onTxPageChange(totalPages);
  });
}

if (ollamaPageFirstBtn) {
  ollamaPageFirstBtn.addEventListener("click", async () => {
    if (ollamaPage <= 1) return;
    ollamaPage = 1;
    try {
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      window.alert(error.message);
    }
  });
}
if (ollamaPagePrevBtn) {
  ollamaPagePrevBtn.addEventListener("click", async () => {
    if (ollamaPage <= 1) return;
    ollamaPage -= 1;
    try {
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      window.alert(error.message);
    }
  });
}
if (ollamaPageNextBtn) {
  ollamaPageNextBtn.addEventListener("click", async () => {
    const totalPages = getOllamaTotalPages();
    if (ollamaPage >= totalPages) return;
    ollamaPage += 1;
    try {
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      window.alert(error.message);
    }
  });
}
if (ollamaPageLastBtn) {
  ollamaPageLastBtn.addEventListener("click", async () => {
    const totalPages = getOllamaTotalPages();
    if (ollamaPage >= totalPages) return;
    ollamaPage = totalPages;
    try {
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      window.alert(error.message);
    }
  });
}

// The audit log is collapsed by default (<details class="cat-log">).
// Load it lazily on first expand, and only poll (every 2.5s, matching
// app.js's startOllamaPolling cadence) while it's open -- replaces
// startOllamaPolling/stopOllamaPolling's active-tab gating from the SPA.
if (catLogDetails) {
  catLogDetails.addEventListener("toggle", async () => {
    if (catLogDetails.open && !ollamaEventsLoadedOnce) {
      try {
        await loadOllamaEvents({ resetPage: true });
      } catch (error) {
        if (ollamaEventsSummaryEl) {
          ollamaEventsSummaryEl.textContent = error.message;
        } else {
          window.alert(error.message);
        }
      }
    }
  });
  stopOllamaPoll = startPoll(async () => {
    if (!catLogDetails.open) return;
    await loadOllamaEvents({ resetPage: false });
  }, 2500);
}

// ── Initial load ─────────────────────────────────────────────────────────
async function initTransactionsPage() {
  if (!jobId) {
    return;
  }
  if (ollamaJobFilterInput && !ollamaJobFilterInput.value) {
    ollamaJobFilterInput.value = jobId;
  }
  try {
    await refreshDuplicateReviewGate();
  } catch (error) {
    window.alert(error.message);
  }
  await refreshOllamaConfigGate();
  try {
    await loadTransactions(true);
  } catch (error) {
    if (txSummary) {
      txSummary.textContent = error.message;
    } else {
      window.alert(error.message);
    }
  }
}

initTransactionsPage();
