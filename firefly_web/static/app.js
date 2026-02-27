const form = document.getElementById("job-form");
const submitButton = document.getElementById("submit");

const filesInput = document.getElementById("files");
const csvDropZone = document.getElementById("csv-drop-zone");
const filesSelectedHint = document.getElementById("files-selected-hint");
const mergedImportFileInput = document.getElementById("merged-import-file");
const duplicatesImportFileInput = document.getElementById("duplicates-import-file");
const importMergedBtn = document.getElementById("import-merged-btn");

const mainTopTabs = Array.from(document.querySelectorAll(".main-top-tab"));
const mainWorkspaces = {
  "merge-workspace": document.getElementById("merge-workspace"),
  "history-workspace": document.getElementById("history-workspace"),
};

const refreshHistoryTabBtn = document.getElementById("refresh-history-tab");
const historyBodyTab = document.getElementById("history-body-tab");
const activeJobSelect = document.getElementById("active-job-select");
const activeJobMeta = document.getElementById("active-job-meta");
const openLatestJobBtn = document.getElementById("open-latest-job");
const clearActiveJobBtn = document.getElementById("clear-active-job");
const jumpHistoryBtn = document.getElementById("jump-history-btn");

const jobEmptyState = document.getElementById("job-empty-state");
const jobContent = document.getElementById("job-content");
const balancesEmptyState = document.getElementById("balances-empty-state");
const balancesContent = document.getElementById("balances-content");
const transactionsEmptyState = document.getElementById("transactions-empty-state");
const transactionsContent = document.getElementById("transactions-content");
const duplicatesEmptyState = document.getElementById("duplicates-empty-state");
const duplicatesContent = document.getElementById("duplicates-content");
const exportEmptyState = document.getElementById("export-empty-state");
const exportContent = document.getElementById("export-content");
const emptyOpenLatestButtons = Array.from(document.querySelectorAll(".empty-open-latest"));
const emptyGoHistoryButtons = Array.from(document.querySelectorAll(".empty-go-history"));

const ollamaJobFilterInput = document.getElementById("ollama-job-filter");
const ollamaStatusGroupInput = document.getElementById("ollama-status-group");
const ollamaPageSizeInput = document.getElementById("ollama-page-size");
const ollamaSortByInput = document.getElementById("ollama-sort-by");
const ollamaSortDirInput = document.getElementById("ollama-sort-dir");
const refreshOllamaEventsBtn = document.getElementById("refresh-ollama-events");
const ollamaPageFirstBtn = document.getElementById("ollama-page-first");
const ollamaPagePrevBtn = document.getElementById("ollama-page-prev");
const ollamaPageButtons = document.getElementById("ollama-page-buttons");
const ollamaPageNextBtn = document.getElementById("ollama-page-next");
const ollamaPageLastBtn = document.getElementById("ollama-page-last");
const ollamaMetricsEl = document.getElementById("ollama-metrics");
const ollamaEventsSummaryEl = document.getElementById("ollama-events-summary");
const ollamaEventsBody = document.getElementById("ollama-events-body");
const stopOllamaQueueBtn = document.getElementById("stop-ollama-queue");
const deleteOllamaQueueBtn = document.getElementById("delete-ollama-queue");

const subTabButtons = Array.from(document.querySelectorAll(".subtab-btn"));
const subPanels = {
  "merge-form-panel": document.getElementById("merge-form-panel"),
  "job-panel": document.getElementById("job-panel"),
  "duplicates-panel": document.getElementById("duplicates-panel"),
  "analytics-panel": document.getElementById("analytics-panel"),
  "transactions-panel": document.getElementById("transactions-panel"),
  "ollama-panel": document.getElementById("ollama-panel"),
  "export-panel": document.getElementById("export-panel"),
};

const jobIdEl = document.getElementById("job-id");
const jobStatusEl = document.getElementById("job-status");
const jobCreatedEl = document.getElementById("job-created");
const jobUpdatedEl = document.getElementById("job-updated");
const statsEl = document.getElementById("stats");
const artifactsEl = document.getElementById("artifacts");
const logsEl = document.getElementById("logs");

const txBody = document.getElementById("transactions-body");
const txSummary = document.getElementById("transaction-summary");
const toggleAllVisible = document.getElementById("toggle-all-visible");
const dupBody = document.getElementById("duplicates-body");
const dupSummary = document.getElementById("dup-summary");
const dupGateSummary = document.getElementById("duplicate-review-gate");
const dupPageSummaryEl = document.getElementById("dup-page-summary");
const toggleAllDupVisible = document.getElementById("toggle-all-dup-visible");
const chartEl = document.getElementById("balance-chart");
const legendEl = document.getElementById("balance-legend");
const startFireflyExportBtn = document.getElementById("start-firefly-export");
const stopFireflyExportBtn = document.getElementById("stop-firefly-export");
const deleteFireflyExportBtn = document.getElementById("delete-firefly-export");
const refreshExportStatusBtn = document.getElementById("refresh-export-status");
const exportSummaryEl = document.getElementById("export-summary");
const exportBody = document.getElementById("exports-body");
const exportLogsEl = document.getElementById("export-logs");
const refreshExportEventsBtn = document.getElementById("refresh-export-events");
const exportEventsStatusGroupInput = document.getElementById("export-events-status-group");
const exportEventsPageSizeInput = document.getElementById("export-events-page-size");
const exportEventsSortByInput = document.getElementById("export-events-sort-by");
const exportEventsSortDirInput = document.getElementById("export-events-sort-dir");
const exportEventsMetricsEl = document.getElementById("export-events-metrics");
const exportEventsSummaryEl = document.getElementById("export-events-summary");
const exportEventsBody = document.getElementById("export-events-body");
const exportEventsPageFirstBtn = document.getElementById("export-events-page-first");
const exportEventsPagePrevBtn = document.getElementById("export-events-page-prev");
const exportEventsPageButtons = document.getElementById("export-events-page-buttons");
const exportEventsPageNextBtn = document.getElementById("export-events-page-next");
const exportEventsPageLastBtn = document.getElementById("export-events-page-last");

const selectVisibleBtn = document.getElementById("select-visible");
const clearSelectionBtn = document.getElementById("clear-selection");
const txPageSizeInput = document.getElementById("tx-page-size");
const txPageSummaryEl = document.getElementById("tx-page-summary");
const txPageFirstBtn = document.getElementById("tx-page-first");
const txPagePrevBtn = document.getElementById("tx-page-prev");
const txPageButtons = document.getElementById("tx-page-buttons");
const txPageNextBtn = document.getElementById("tx-page-next");
const txPageLastBtn = document.getElementById("tx-page-last");
const dupSearchInput = document.getElementById("dup-search");
const applyDupFiltersBtn = document.getElementById("apply-dup-filters");
const refreshDupReviewBtn = document.getElementById("refresh-dup-review");
const selectVisibleDupBtn = document.getElementById("select-visible-dup");
const clearDupSelectionBtn = document.getElementById("clear-dup-selection");
const restoreDupSelectedBtn = document.getElementById("restore-dup-selected");
const confirmDupReviewBtn = document.getElementById("confirm-dup-review");
const dupPageSizeInput = document.getElementById("dup-page-size");
const dupSourceFileFilter = document.getElementById("dup-source-file-filter");
const dupSortBy = document.getElementById("dup-sort-by");
const dupSortDir = document.getElementById("dup-sort-dir");
const dupPageFirstBtn = document.getElementById("dup-page-first");
const dupPagePrevBtn = document.getElementById("dup-page-prev");
const dupPageButtons = document.getElementById("dup-page-buttons");
const dupPageNextBtn = document.getElementById("dup-page-next");
const dupPageLastBtn = document.getElementById("dup-page-last");

const categorizeOllamaBtn = document.getElementById("categorize-ollama");
const categorizeAllOllamaBtn = document.getElementById("categorize-all-ollama");
const autoExportAfterCategorizeInput = document.getElementById("auto-export-after-categorize");
const downloadCategorizedCsvBtn = document.getElementById("download-categorized-csv");
const overwriteCategoryCheckbox = document.getElementById("overwrite-category");

const dedupeScopeInput = document.getElementById("dedupe_scope");
const noDedupInput = document.getElementById("no_dedup");
const dedupeFirstOnlyInput = document.getElementById("dedupe_first_only");
const pushFireflyInput = document.getElementById("push_firefly");

const txSearchInput = document.getElementById("tx-search");
const txDecisionFilter = document.getElementById("tx-decision-filter");
const txIncludeDroppedInput = document.getElementById("tx-include-dropped");
const txSourceFileFilter = document.getElementById("tx-source-file-filter");
const txSortBy = document.getElementById("tx-sort-by");
const txSortDir = document.getElementById("tx-sort-dir");
const applyTxFiltersBtn = document.getElementById("apply-tx-filters");
const detailModalEl = document.getElementById("detail-modal");
const detailModalCloseBtn = document.getElementById("detail-modal-close");
const detailModalTitleEl = document.getElementById("detail-modal-title");
const detailModalContentEl = document.getElementById("detail-modal-content");
const globalOllamaBarEl = document.getElementById("global-ollama-bar");
const globalOllamaTextEl = document.getElementById("global-ollama-text");
const globalOllamaMetaEl = document.getElementById("global-ollama-meta");
const globalExportBarEl = document.getElementById("global-export-bar");
const globalExportTextEl = document.getElementById("global-export-text");
const globalExportMetaEl = document.getElementById("global-export-meta");

let pollTimer = null;
let ollamaPollTimer = null;
let exportPollTimer = null;
let queueSummaryPollTimer = null;
let activeJobId = "";
let activeJobStatus = "";
let txPage = 1;
let txPageSize = 20;
let txTotal = 0;
let txOverallTotal = 0;
const selectedRows = new Set();
const selectedDuplicateRows = new Set();
let dupPage = 1;
let dupPageSize = 20;
let dupTotal = 0;
let duplicateReviewStatus = {
  required: false,
  confirmed: true,
  can_proceed: true,
  pending_duplicates: 0,
  initial_duplicates: 0,
  restored_rows_total: 0,
};
let preferredSourceFile = "";
let preferredDupSourceFile = "";
let txDecisionCounts = { merged: 0, dropped: 0 };
let categoryOptions = [];
let knownJobs = [];
let ollamaTotalCount = 0;
let ollamaPage = 1;
let ollamaPageSize = 20;
let ollamaCurrentFilter = "";

const ollamaEventsById = new Map();
let activeOllamaEventId = 0;
let activeTransactionKey = "";
let activeExportId = "";
let exportEventsTotal = 0;
let exportEventsPage = 1;
let exportEventsPageSize = 20;
const exportEventsById = new Map();
let activeExportEventId = 0;

const SESSION_STORAGE_KEY = "firefly_merge_session_v4";
const FORM_STORAGE_KEY = "firefly_merge_form_v3";

if (startFireflyExportBtn) {
  startFireflyExportBtn.disabled = true;
}
if (stopFireflyExportBtn) {
  stopFireflyExportBtn.disabled = true;
}
if (deleteFireflyExportBtn) {
  deleteFireflyExportBtn.disabled = true;
}
if (categorizeOllamaBtn) {
  categorizeOllamaBtn.disabled = true;
}
if (categorizeAllOllamaBtn) {
  categorizeAllOllamaBtn.disabled = true;
}

function normalizeDedupeScope() {
  return "within_job";
}

function readCheckbox(name) {
  const input = document.getElementById(name);
  return !!(input && input.checked);
}

function updateSelectedFilesHint() {
  if (!filesSelectedHint || !filesInput) {
    return;
  }
  const count = Number(filesInput.files && filesInput.files.length ? filesInput.files.length : 0);
  if (!count) {
    filesSelectedHint.textContent = "No files selected.";
    return;
  }
  const label = count === 1 ? "file" : "files";
  filesSelectedHint.textContent = `${count} ${label} selected.`;
}

function getActiveMainTab() {
  const btn = mainTopTabs.find((b) => b.classList.contains("active"));
  return btn ? String(btn.dataset.mainTab || "merge-workspace") : "merge-workspace";
}

function hashToken(rawHash) {
  return String(rawHash || "").replace(/^#/, "").trim().toLowerCase();
}

function mainTabFromHash(rawHash) {
  const token = hashToken(rawHash);
  if (token === "history" || token === "history-workspace") {
    return "history-workspace";
  }
  if (
    token === "merge" ||
    token === "merge-workspace" ||
    token === "job" ||
    token === "job-status" ||
    token === "duplicates" ||
    token === "duplicate-review" ||
    token === "balances" ||
    token === "analytics" ||
    token === "transactions" ||
    token === "ollama" ||
    token === "export"
  ) {
    return "merge-workspace";
  }
  return "";
}

function subTabFromHash(rawHash) {
  const token = hashToken(rawHash);
  if (token === "merge" || token === "merge-workspace") {
    return "merge-form-panel";
  }
  if (token === "job" || token === "job-status") {
    return "job-panel";
  }
  if (token === "duplicates" || token === "duplicate-review") {
    return "duplicates-panel";
  }
  if (token === "balances" || token === "analytics") {
    return "analytics-panel";
  }
  if (token === "transactions") {
    return "transactions-panel";
  }
  if (token === "ollama") {
    return "ollama-panel";
  }
  if (token === "export") {
    return "export-panel";
  }
  return "";
}

function mainTabToHash(name) {
  if (name === "history-workspace") {
    return "#history";
  }
  return "";
}

function stopOllamaPolling() {
  if (ollamaPollTimer) {
    clearInterval(ollamaPollTimer);
    ollamaPollTimer = null;
  }
}

function startOllamaPolling() {
  stopOllamaPolling();
  ollamaPollTimer = setInterval(async () => {
    if (getActiveMainTab() !== "merge-workspace" || getActiveSubTab() !== "ollama-panel") {
      stopOllamaPolling();
      return;
    }
    try {
      await loadOllamaEvents();
    } catch (error) {
      // ignore polling errors; user can refresh manually
    }
  }, 2500);
}

function getActiveSubTab() {
  const btn = subTabButtons.find((b) => b.classList.contains("active"));
  return btn ? String(btn.dataset.subTab || "merge-form-panel") : "merge-form-panel";
}

function activateMainTab(name, options = {}) {
  const syncHash = options.syncHash !== false;
  mainTopTabs.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mainTab === name);
  });

  Object.entries(mainWorkspaces).forEach(([key, workspace]) => {
    if (!workspace) return;
    workspace.hidden = key !== name;
  });

  if (syncHash && window.location.pathname === "/") {
    const hash = mainTabToHash(name);
    if (hash) {
      window.location.hash = hash;
    } else if (window.location.hash) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }

  if (name !== "merge-workspace" || getActiveSubTab() !== "ollama-panel") {
    stopOllamaPolling();
  }
  saveSessionState();
}

function activateSubTab(name) {
  subTabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.subTab === name);
  });

  Object.entries(subPanels).forEach(([key, panel]) => {
    if (!panel) return;
    panel.hidden = key !== name;
  });

  if (name === "export-panel") {
    loadFireflyExports(true).catch((error) => {
      if (exportSummaryEl) {
        exportSummaryEl.textContent = error.message;
      }
    });
  } else {
    stopExportPolling();
  }

  if (name === "duplicates-panel") {
    loadDuplicateReview(false).catch((error) => {
      if (dupSummary) {
        dupSummary.textContent = error.message;
      }
    });
  }

  if (name === "ollama-panel") {
    startOllamaPolling();
    loadOllamaEvents({ resetPage: false }).catch((error) => {
      if (ollamaEventsSummaryEl) {
        ollamaEventsSummaryEl.textContent = error.message;
      }
    });
  } else {
    stopOllamaPolling();
  }

  saveSessionState();
}

function saveSessionState() {
  try {
    localStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({
        activeJobId,
        mainTab: getActiveMainTab(),
        subTab: getActiveSubTab(),
      })
    );
  } catch (error) {
    // ignore
  }
}

function loadSessionState() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    return JSON.parse(raw);
  } catch (error) {
    return {};
  }
}

function saveFormPreferences() {
  try {
    localStorage.setItem(
      FORM_STORAGE_KEY,
      JSON.stringify({
        no_dedup: !!(noDedupInput && noDedupInput.checked),
        dedupe_first_only: !!(dedupeFirstOnlyInput && dedupeFirstOnlyInput.checked),
        push_firefly: !!(pushFireflyInput && pushFireflyInput.checked),
        overwrite_category: !!(overwriteCategoryCheckbox && overwriteCategoryCheckbox.checked),
        tx_decision: txDecisionFilter ? txDecisionFilter.value : "all",
        tx_include_dropped: !!(txIncludeDroppedInput && txIncludeDroppedInput.checked),
        tx_source_file: txSourceFileFilter ? txSourceFileFilter.value : "",
        tx_sort_by: txSortBy ? txSortBy.value : "date",
        tx_sort_dir: txSortDir ? txSortDir.value : "asc",
        tx_search: txSearchInput ? txSearchInput.value : "",
        auto_export_after_categorize: !!(autoExportAfterCategorizeInput && autoExportAfterCategorizeInput.checked),
        tx_page_size: txPageSizeInput ? txPageSizeInput.value : "20",
        ollama_status_group: ollamaStatusGroupInput ? ollamaStatusGroupInput.value : "queue",
        ollama_page_size: ollamaPageSizeInput ? ollamaPageSizeInput.value : "20",
        ollama_sort_by: ollamaSortByInput ? ollamaSortByInput.value : "id",
        ollama_sort_dir: ollamaSortDirInput ? ollamaSortDirInput.value : "asc",
        export_events_status_group: exportEventsStatusGroupInput ? exportEventsStatusGroupInput.value : "queue",
        export_events_page_size: exportEventsPageSizeInput ? exportEventsPageSizeInput.value : "20",
        export_events_sort_by: exportEventsSortByInput ? exportEventsSortByInput.value : "id",
        export_events_sort_dir: exportEventsSortDirInput ? exportEventsSortDirInput.value : "asc",
        dup_search: dupSearchInput ? dupSearchInput.value : "",
        dup_source_file: dupSourceFileFilter ? dupSourceFileFilter.value : "",
        dup_page_size: dupPageSizeInput ? dupPageSizeInput.value : "20",
        dup_sort_by: dupSortBy ? dupSortBy.value : "date",
        dup_sort_dir: dupSortDir ? dupSortDir.value : "asc",
      })
    );
  } catch (error) {
    // ignore
  }
}

function restoreFormPreferences() {
  if (dedupeScopeInput) {
    dedupeScopeInput.value = "within_job";
  }
  if (txIncludeDroppedInput) {
    txIncludeDroppedInput.checked = true;
  }
  try {
    const raw = localStorage.getItem(FORM_STORAGE_KEY);
    if (!raw) {
      return;
    }
    const parsed = JSON.parse(raw);
    if (noDedupInput) noDedupInput.checked = !!parsed.no_dedup;
    if (dedupeFirstOnlyInput) dedupeFirstOnlyInput.checked = !!parsed.dedupe_first_only;
    if (pushFireflyInput) pushFireflyInput.checked = !!parsed.push_firefly;
    if (overwriteCategoryCheckbox) overwriteCategoryCheckbox.checked = !!parsed.overwrite_category;
    if (txDecisionFilter && parsed.tx_decision) txDecisionFilter.value = parsed.tx_decision;
    if (txIncludeDroppedInput && Object.prototype.hasOwnProperty.call(parsed, "tx_include_dropped")) {
      txIncludeDroppedInput.checked = !!parsed.tx_include_dropped;
    }
    if (txSortBy && parsed.tx_sort_by) txSortBy.value = parsed.tx_sort_by;
    if (txSortDir && parsed.tx_sort_dir) txSortDir.value = parsed.tx_sort_dir;
    if (txSearchInput && parsed.tx_search) txSearchInput.value = parsed.tx_search;
    if (autoExportAfterCategorizeInput) autoExportAfterCategorizeInput.checked = !!parsed.auto_export_after_categorize;
    if (txPageSizeInput && parsed.tx_page_size) txPageSizeInput.value = parsed.tx_page_size;
    if (ollamaStatusGroupInput && parsed.ollama_status_group) ollamaStatusGroupInput.value = parsed.ollama_status_group;
    if (ollamaPageSizeInput && parsed.ollama_page_size) ollamaPageSizeInput.value = parsed.ollama_page_size;
    if (ollamaSortByInput && parsed.ollama_sort_by) ollamaSortByInput.value = parsed.ollama_sort_by;
    if (ollamaSortDirInput && parsed.ollama_sort_dir) ollamaSortDirInput.value = parsed.ollama_sort_dir;
    if (exportEventsStatusGroupInput && parsed.export_events_status_group) exportEventsStatusGroupInput.value = parsed.export_events_status_group;
    if (exportEventsPageSizeInput && parsed.export_events_page_size) exportEventsPageSizeInput.value = parsed.export_events_page_size;
    if (exportEventsSortByInput && parsed.export_events_sort_by) exportEventsSortByInput.value = parsed.export_events_sort_by;
    if (exportEventsSortDirInput && parsed.export_events_sort_dir) exportEventsSortDirInput.value = parsed.export_events_sort_dir;
    if (dupSearchInput && parsed.dup_search) dupSearchInput.value = parsed.dup_search;
    if (dupSourceFileFilter && parsed.dup_source_file) dupSourceFileFilter.value = parsed.dup_source_file;
    if (dupPageSizeInput && parsed.dup_page_size) dupPageSizeInput.value = parsed.dup_page_size;
    if (dupSortBy && parsed.dup_sort_by) dupSortBy.value = parsed.dup_sort_by;
    if (dupSortDir && parsed.dup_sort_dir) dupSortDir.value = parsed.dup_sort_dir;
    preferredSourceFile = String(parsed.tx_source_file || "");
    preferredDupSourceFile = String(parsed.dup_source_file || "");
  } catch (error) {
    // ignore
  }
}

function formatJobOptionLabel(job) {
  const id = String(job.id || "");
  const status = String(job.status || "unknown");
  const stats = job.stats || {};
  const merged = Number(stats.merged_rows || 0);
  const dropped = Number(stats.duplicate_rows || 0);
  const shortId = id.length > 10 ? `${id.slice(0, 10)}...` : id;
  return `${shortId} | ${status} | merged ${merged} | dropped ${dropped}`;
}

function getLatestJobCandidate() {
  if (!knownJobs.length) {
    return null;
  }
  const preferred = knownJobs.find((job) => {
    const status = String(job.status || "");
    return status === "completed" || status === "running" || status === "queued";
  });
  return preferred || knownJobs[0];
}

function setMergePanelDataVisibility(isVisible) {
  const hasActiveJob = !!isVisible;
  if (jobEmptyState) jobEmptyState.hidden = hasActiveJob;
  if (jobContent) jobContent.hidden = !hasActiveJob;
  if (balancesEmptyState) balancesEmptyState.hidden = hasActiveJob;
  if (balancesContent) balancesContent.hidden = !hasActiveJob;
  if (duplicatesEmptyState) duplicatesEmptyState.hidden = hasActiveJob;
  if (duplicatesContent) duplicatesContent.hidden = !hasActiveJob;
  if (transactionsEmptyState) transactionsEmptyState.hidden = hasActiveJob;
  if (transactionsContent) transactionsContent.hidden = !hasActiveJob;
  if (exportEmptyState) exportEmptyState.hidden = hasActiveJob;
  if (exportContent) exportContent.hidden = !hasActiveJob;
}

function refreshActiveJobControls() {
  if (!activeJobSelect) {
    return;
  }
  const current = String(activeJobId || "");
  const options = [`<option value=\"\">No job selected</option>`];

  knownJobs.forEach((job) => {
    const id = String(job.id || "");
    if (!id) {
      return;
    }
    const selected = current && current === id ? " selected" : "";
    options.push(`<option value=\"${escapeHtml(id)}\"${selected}>${escapeHtml(formatJobOptionLabel(job))}</option>`);
  });

  if (current && !knownJobs.some((job) => String(job.id || "") === current)) {
    options.push(`<option value=\"${escapeHtml(current)}\" selected>${escapeHtml(current)} | not in history list</option>`);
  }

  activeJobSelect.innerHTML = options.join("");

  const active = knownJobs.find((job) => String(job.id || "") === current);
  if (activeJobMeta) {
    if (!current) {
      activeJobMeta.textContent = "No active job selected.";
    } else if (active) {
      const stats = active.stats || {};
      activeJobMeta.textContent =
        `Active job ${current}. Status: ${active.status || "unknown"}. ` +
        `Merged: ${stats.merged_rows ?? 0}, duplicates: ${stats.duplicate_rows ?? 0}.`;
    } else {
      activeJobMeta.textContent = `Active job ${current}.`;
    }
  }

  if (openLatestJobBtn) {
    openLatestJobBtn.disabled = !getLatestJobCandidate();
  }
  if (clearActiveJobBtn) {
    clearActiveJobBtn.disabled = !current;
  }

  setMergePanelDataVisibility(!!current);
}

function setProvisionalDuplicateReviewFromJob(job) {
  const stats = (job && job.stats) || {};
  const duplicateCount = Number(stats.duplicate_rows || 0);
  const completed = String((job && job.status) || "") === "completed";
  duplicateReviewStatus = {
    required: completed && duplicateCount > 0,
    confirmed: completed ? duplicateCount <= 0 : true,
    can_proceed: completed ? duplicateCount <= 0 : true,
    pending_duplicates: completed ? duplicateCount : 0,
    initial_duplicates: duplicateCount,
    restored_rows_total: Number((duplicateReviewStatus && duplicateReviewStatus.restored_rows_total) || 0),
  };
  updateDuplicateReviewGateUI();
}

function renderJob(job) {
  if (!job) {
    return;
  }
  if (job.id) {
    activeJobId = String(job.id);
  }
  saveSessionState();
  refreshActiveJobControls();

  jobIdEl.textContent = job.id || "";
  jobStatusEl.textContent = job.status || "";
  activeJobStatus = String(job.status || "");
  jobCreatedEl.textContent = job.created_at || "-";
  jobUpdatedEl.textContent = job.updated_at || "-";

  const stats = job.stats || {};
  const pendingDup = Number(duplicateReviewStatus.pending_duplicates || stats.duplicate_rows || 0);
  const reviewLabel = duplicateReviewStatus.can_proceed ? "ready" : "action required";
  statsEl.innerHTML = `
    <h3>Stats</h3>
    <ul>
      <li>Merged rows: ${stats.merged_rows ?? 0}</li>
      <li>Duplicate rows: ${stats.duplicate_rows ?? 0}</li>
      <li>Duplicate review: ${reviewLabel} (pending: ${pendingDup}, restored: ${duplicateReviewStatus.restored_rows_total ?? 0})</li>
      <li>Global duplicates added: ${stats.global_duplicates_added ?? 0}</li>
      <li>Fingerprints inserted: ${stats.global_rows_inserted ?? 0}</li>
    </ul>
  `;

  const urls = job.artifact_urls || {};
  const links = Object.entries(urls)
    .map(([key, url]) => `<li><a href="${url}" target="_blank" rel="noopener">${key}</a></li>`)
    .join("");
  artifactsEl.innerHTML = `<h3>Artifacts</h3><ul>${links || "<li>None</li>"}</ul>`;

  logsEl.textContent = job.logs || "";
  logsEl.scrollTop = logsEl.scrollHeight;

  applyDuplicateReviewGateToActions();
  if (exportSummaryEl && String(job.status || "") !== "completed") {
    exportSummaryEl.textContent = "Merge job must be completed before export.";
  }
}

function resetActiveJobView() {
  stopPolling();
  stopExportPolling();
  activeJobId = "";
  activeJobStatus = "";
  activeExportId = "";
  activeExportEventId = 0;
  exportEventsTotal = 0;
  exportEventsPage = 1;
  selectedRows.clear();
  saveSessionState();
  refreshActiveJobControls();

  if (jobIdEl) jobIdEl.textContent = "";
  if (jobStatusEl) jobStatusEl.textContent = "-";
  if (jobCreatedEl) jobCreatedEl.textContent = "-";
  if (jobUpdatedEl) jobUpdatedEl.textContent = "-";
  if (statsEl) statsEl.innerHTML = "";
  if (artifactsEl) artifactsEl.innerHTML = "";
  if (logsEl) logsEl.textContent = "";
  if (txSummary) txSummary.textContent = "No job selected.";
  if (dupBody) dupBody.innerHTML = `<tr><td colspan="13">No job selected.</td></tr>`;
  if (dupSummary) dupSummary.textContent = "Select a completed merge job to review duplicates.";
  if (dupPageSummaryEl) dupPageSummaryEl.textContent = "Rows 0-0 of 0";
  if (toggleAllDupVisible) toggleAllDupVisible.checked = false;
  selectedDuplicateRows.clear();
  dupPage = 1;
  dupTotal = 0;
  duplicateReviewStatus = {
    required: false,
    confirmed: true,
    can_proceed: true,
    pending_duplicates: 0,
    initial_duplicates: 0,
    restored_rows_total: 0,
  };
  if (chartEl) chartEl.innerHTML = "<text x='20' y='40'>No balance data available.</text>";
  if (legendEl) legendEl.innerHTML = "";
  if (exportSummaryEl) exportSummaryEl.textContent = "Select a completed merge job first.";
  if (exportLogsEl) exportLogsEl.textContent = "";
  if (exportBody) exportBody.innerHTML = `<tr><td colspan="8">No job selected.</td></tr>`;
  if (exportEventsBody) exportEventsBody.innerHTML = `<tr><td colspan="10">No export selected.</td></tr>`;
  if (exportEventsSummaryEl) exportEventsSummaryEl.textContent = "Select an export to inspect queue details.";
  if (exportEventsMetricsEl) exportEventsMetricsEl.textContent = "No export queue metrics yet.";
  updateExportEventsPagination();
  if (startFireflyExportBtn) startFireflyExportBtn.disabled = true;
  if (stopFireflyExportBtn) stopFireflyExportBtn.disabled = true;
  if (deleteFireflyExportBtn) deleteFireflyExportBtn.disabled = true;
  clearTransactionState();
  updateDupPagination();
  updateDuplicateReviewGateUI();
  applyDuplicateReviewGateToActions();
}

async function fetchJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch job ${jobId}`);
  }
  return response.json();
}

async function fetchJobs(limit = 200) {
  const response = await fetch(`/api/jobs?limit=${limit}`);
  if (!response.ok) {
    throw new Error("Failed to fetch job history.");
  }
  return response.json();
}

async function deleteJobRequest(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to delete job.");
  }
  return response.json();
}

async function fetchOllamaEvents({
  limit = 20,
  offset = 0,
  jobId = "",
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
  if (jobId) {
    params.set("job_id", jobId);
  }
  const response = await fetch(`/api/ollama/events?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to fetch Ollama events.");
  }
  return response.json();
}

async function fetchQueueSummary() {
  const response = await fetch("/api/queues/summary");
  if (!response.ok) {
    throw new Error("Failed to fetch queue summary.");
  }
  return response.json();
}

async function fetchOllamaEvent(eventId) {
  const response = await fetch(`/api/ollama/events/${Number(eventId || 0)}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to fetch Ollama event.");
  }
  return response.json();
}

async function stopOllamaQueue(jobId) {
  const response = await fetch("/api/ollama/queues/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: String(jobId || "") }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to stop Ollama queue.");
  }
  return payload;
}

async function deleteOllamaQueue(jobId, statusGroup = "all") {
  const params = new URLSearchParams();
  if (jobId) {
    params.set("job_id", String(jobId));
  }
  params.set("status_group", String(statusGroup || "all"));
  const response = await fetch(`/api/ollama/queues?${params.toString()}`, { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to delete Ollama queue.");
  }
  return payload;
}

async function deleteOllamaQueueItem(eventId) {
  const response = await fetch(`/api/ollama/events/${Number(eventId || 0)}`, { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to delete Ollama queue item.");
  }
  return payload;
}

async function fetchTransactionDetail(jobId, rowSource, rowLocalIndex) {
  const params = new URLSearchParams();
  params.set("row_source", String(rowSource || ""));
  params.set("row_local_index", String(rowLocalIndex || 0));
  const response = await fetch(`/api/jobs/${jobId}/transactions/detail?${params.toString()}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to load transaction detail.");
  }
  return response.json();
}

async function fetchDuplicateReviewStatus(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/duplicates/review/status`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to load duplicate review status.");
  }
  return payload;
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

async function fetchDuplicateReviewRows(jobId, offset, limit) {
  const response = await fetch(`/api/jobs/${jobId}/duplicates/review?${buildDuplicateReviewQuery(offset, limit).toString()}`);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to load duplicate review rows.");
  }
  return payload;
}

async function restoreDuplicateRowsRequest(jobId, duplicateRowIndices) {
  const response = await fetch(`/api/jobs/${jobId}/duplicates/review/restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ duplicate_row_indices: duplicateRowIndices }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to restore duplicate rows.");
  }
  return payload;
}

async function confirmDuplicateReviewRequest(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/duplicates/review/confirm`, {
    method: "POST",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to confirm duplicate review.");
  }
  return payload;
}

async function startFireflyExport(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force: false }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to start Firefly export.");
  }
  return payload;
}

async function retryFailedFireflyExport(jobId, exportId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/${exportId}/retry-failed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force: false }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to queue retry export.");
  }
  return payload;
}

async function stopFireflyExport(jobId, exportId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/${exportId}/stop`, {
    method: "POST",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to stop Firefly export queue.");
  }
  return payload;
}

async function deleteFireflyExport(jobId, exportId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/${exportId}`, { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to delete Firefly export queue.");
  }
  return payload;
}

async function deleteFireflyExports(jobId, statusGroup = "all") {
  const params = new URLSearchParams();
  params.set("status_group", String(statusGroup || "all"));
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly?${params.toString()}`, { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to delete Firefly export queues.");
  }
  return payload;
}

async function deleteFireflyExportEvents(jobId, exportId, statusGroup = "all") {
  const params = new URLSearchParams();
  params.set("status_group", String(statusGroup || "all"));
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/${exportId}/events?${params.toString()}`, {
    method: "DELETE",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to delete Firefly export queue items.");
  }
  return payload;
}

async function fetchFireflyExports(jobId, limit = 50) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly?limit=${limit}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to fetch Firefly exports.");
  }
  return response.json();
}

async function fetchFireflyExport(jobId, exportId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/${exportId}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to fetch Firefly export details.");
  }
  return response.json();
}

async function fetchFireflyExportEvents(jobId, exportId, {
  limit = 20,
  offset = 0,
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
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/${exportId}/events?${params.toString()}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to fetch export queue events.");
  }
  return response.json();
}

async function fetchFireflyExportEvent(jobId, eventId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/events/${Number(eventId || 0)}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to fetch export queue event.");
  }
  return response.json();
}

async function deleteFireflyExportEvent(jobId, eventId) {
  const response = await fetch(`/api/jobs/${jobId}/exports/firefly/events/${Number(eventId || 0)}`, {
    method: "DELETE",
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to delete export queue item.");
  }
  return payload;
}

async function importMergedJob(mergedFile, duplicatesFile) {
  const formData = new FormData();
  formData.append("merged_file", mergedFile);
  if (duplicatesFile) {
    formData.append("duplicates_file", duplicatesFile);
  }
  const response = await fetch("/api/jobs/import", {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Failed to import merged CSV.");
  }
  return payload;
}

function buildTransactionQuery(offset, limit) {
  const params = new URLSearchParams();
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  params.set("include_details", "false");
  params.set("include_duplicates", "true");
  params.set("include_dropped", txIncludeDroppedInput && txIncludeDroppedInput.checked ? "true" : "false");
  params.set("decision", String(txDecisionFilter.value || "all"));
  params.set("search", String(txSearchInput.value || ""));
  params.set("source_file", String(txSourceFileFilter.value || ""));
  params.set("sort_by", String(txSortBy.value || "date"));
  params.set("sort_dir", String(txSortDir.value || "asc"));
  return params;
}

async function fetchTransactions(jobId, offset, limit) {
  const response = await fetch(`/api/jobs/${jobId}/transactions?${buildTransactionQuery(offset, limit).toString()}`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to load transactions.");
  }
  return response.json();
}

async function fetchBalances(jobId) {
  const response = await fetch(`/api/jobs/${jobId}/balances`);
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to load balances.");
  }
  return response.json();
}

async function categorize(jobId, mode, rowIndices, options = {}) {
  const autoExport = options.autoExport === true;
  const response = await fetch(`/api/jobs/${jobId}/categorize/${mode}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      row_indices: rowIndices,
      overwrite: !!overwriteCategoryCheckbox.checked,
      auto_export: autoExport,
    }),
  });
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Categorization failed.");
  }
  return response.json();
}

function downloadCategorizedCsv(jobId) {
  const url = `/api/jobs/${encodeURIComponent(jobId)}/transactions/categorized.csv`;
  window.open(url, "_blank", "noopener");
}

async function updateTransactionCategory(jobId, mergeRowIndex, category) {
  const response = await fetch(`/api/jobs/${jobId}/transactions/category`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ merge_row_index: mergeRowIndex, category: category || "" }),
  });
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload.detail || "Failed to update category.");
  }
  return response.json();
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function stopQueueSummaryPolling() {
  if (queueSummaryPollTimer) {
    clearInterval(queueSummaryPollTimer);
    queueSummaryPollTimer = null;
  }
}

function startQueueSummaryPolling() {
  stopQueueSummaryPolling();
  queueSummaryPollTimer = setInterval(async () => {
    try {
      await loadQueueSummary();
    } catch (error) {
      // ignore polling errors; regular page actions continue to work
    }
  }, 2500);
}

function stopExportPolling() {
  if (exportPollTimer) {
    clearInterval(exportPollTimer);
    exportPollTimer = null;
  }
}

function startPolling(jobId) {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const job = await fetchJob(jobId);
      renderJob(job);
      if (job.status === "completed") {
        stopPolling();
        submitButton.disabled = false;
        await loadAnalytics(jobId, true);
        await loadFireflyExports(true);
        await loadJobHistory();
      } else if (job.status === "failed") {
        stopPolling();
        submitButton.disabled = false;
        await loadFireflyExports(true);
        await loadJobHistory();
      }
    } catch (error) {
      stopPolling();
      submitButton.disabled = false;
      alert(error.message);
    }
  }, 2000);
}

function clearTransactionState() {
  selectedRows.clear();
  txPage = 1;
  txTotal = 0;
  txOverallTotal = 0;
  txDecisionCounts = { merged: 0, dropped: 0 };
  activeTransactionKey = "";
  txBody.innerHTML = "";
  toggleAllVisible.checked = false;
  if (txSummary) {
    txSummary.textContent = "No transactions loaded.";
  }
  if (txPageSummaryEl) {
    txPageSummaryEl.textContent = "Rows 0-0 of 0";
  }
  updateTxPagination();
}

async function loadAnalytics(jobId, reset = true) {
  if (!jobId) {
    return;
  }
  if (reset) {
    clearTransactionState();
  }
  try {
    await Promise.all([loadTransactions(reset), loadBalanceChart(), loadDuplicateReview(reset)]);
  } catch (error) {
    txSummary.textContent = error.message;
  }
}

function populateSourceFileFilter(files, keepCurrent = true) {
  const current = keepCurrent ? String(txSourceFileFilter.value || "") : "";
  txSourceFileFilter.innerHTML = [
    `<option value="">All source files</option>`,
    ...(files || []).map((f) => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`),
  ].join("");

  if (current && (files || []).includes(current)) {
    txSourceFileFilter.value = current;
    return;
  }
  if (preferredSourceFile && (files || []).includes(preferredSourceFile)) {
    txSourceFileFilter.value = preferredSourceFile;
  }
}

async function loadTransactions(reset = false) {
  if (!activeJobId) {
    clearTransactionState();
    if (txSummary) {
      txSummary.textContent = "Select a merge job to load transactions.";
    }
    return;
  }
  if (reset) {
    txPage = 1;
  }

  txPageSize = Math.max(1, Number((txPageSizeInput && txPageSizeInput.value) || 20));
  const limit = txPageSize;
  const offset = (Math.max(1, txPage) - 1) * limit;
  const payload = await fetchTransactions(activeJobId, offset, limit);

  txOverallTotal = Number(payload.overall_total || 0);
  txTotal = Number(payload.total || 0);
  txDecisionCounts = payload.decision_counts || { merged: 0, dropped: 0 };
  categoryOptions = Array.isArray(payload.categories) ? payload.categories : categoryOptions;
  populateSourceFileFilter(payload.source_files || [], true);

  const rows = payload.rows || [];
  txBody.innerHTML = rows.length
    ? rows.map((row) => renderTransactionRow(row)).join("")
    : `<tr><td colspan="11">No transactions for current filters.</td></tr>`;

  const totalPages = getTxTotalPages();
  if (txPage > totalPages) {
    txPage = totalPages;
    await loadTransactions(false);
    return;
  }

  wireRowCheckboxes();
  wireTransactionDetailButtons();
  updateTransactionSummary();
  updateTxPagination();
}

function renderTransactionRow(row) {
  const decision = String(row._decision || "merged");
  const rowSource = String(row._row_source || "");
  const rowLocalIndex = Number(row._row_local_index || 0);
  const rowKey = buildTransactionRowKey(rowSource, rowLocalIndex);
  const rowId = String(row.id || "");
  const mergeRowIndex = Number(row._merge_row_index || 0);
  const selectable = decision === "merged" && mergeRowIndex > 0;
  const checked = selectable && selectedRows.has(mergeRowIndex) ? "checked" : "";
  const disabled = selectable ? "" : "disabled";
  const rowClass = decision === "dropped" ? "row-dropped" : "row-merged";
  const selectedClass = activeTransactionKey && activeTransactionKey === rowKey ? " selected" : "";
  const categoryCell = decision === "merged" ? renderCategorySelect(mergeRowIndex, String(row.category || "")) : escapeHtml(row.category || "");
  const droppedPairingCell = renderDroppedPairingCell(row);
  const decisionLabel =
    decision === "merged" && Number(row._dropped_count || 0) > 0
      ? `merged + ${Number(row._dropped_count || 0)} dropped`
      : decision;

  return `
    <tr class="${rowClass}${selectedClass}" data-row-source="${escapeHtml(rowSource)}" data-row-local-index="${rowLocalIndex}" data-row-id="${escapeHtml(rowId)}" data-row-key="${escapeHtml(rowKey)}">
      <td data-label="Select"><input type="checkbox" class="row-checkbox" data-merge-row-index="${mergeRowIndex}" ${checked} ${disabled}></td>
      <td data-label="ID"><code>${escapeHtml(rowId)}</code></td>
      <td data-label="Decision"><span class="decision-badge ${decision}">${escapeHtml(decisionLabel)}</span></td>
      <td data-label="Date">${escapeHtml(row.date || "")}</td>
      <td data-label="Amount" class="num">${escapeHtml(row.amount || "")}</td>
      <td data-label="Category">${categoryCell}</td>
      <td data-label="Description">${escapeHtml(row.description || "")}</td>
      <td data-label="Source Account">${escapeHtml(row.source_account || "")}</td>
      <td data-label="Destination Account">${escapeHtml(row.destination_account || "")}</td>
      <td data-label="Dropped Pairing">${droppedPairingCell}</td>
      <td data-label="Details"><button type="button" class="tx-open-detail secondary-btn" data-row-source="${escapeHtml(rowSource)}" data-row-local-index="${rowLocalIndex}" data-row-id="${escapeHtml(rowId)}">Open</button></td>
    </tr>
  `;
}

function renderDroppedPairingCell(row) {
  const decision = String(row._decision || "merged");
  if (decision === "dropped") {
    const reason = String(row._decision_reason || "duplicate");
    const reasoning = String(row._decision_reasoning || row.duplicate_reasoning || "");
    const duplicateOf = String(row.duplicate_of_external_id || "");
    const paired = duplicateOf ? `Duplicate of ${escapeHtml(duplicateOf)}` : "No merged match found";
    const reasoningLine = reasoning ? `<div class="hint">${escapeHtml(reasoning)}</div>` : "";
    return `<div>${paired}</div><div class="hint">${escapeHtml(reason)}</div>${reasoningLine}`;
  }

  const matches = Array.isArray(row._dropped_matches) ? row._dropped_matches : [];
  if (!matches.length) {
    return `<span class="hint">No dropped duplicates</span>`;
  }
  const lines = matches
    .slice(0, 3)
    .map((item) => {
      const dt = escapeHtml(String(item.date || ""));
      const amt = escapeHtml(String(item.amount || ""));
      const ext = escapeHtml(String(item.external_id || ""));
      return `<div><code>${ext}</code> | ${dt} | ${amt}</div>`;
    })
    .join("");
  const more = matches.length > 3 ? `<div class="hint">+${matches.length - 3} more</div>` : "";
  return `<div>${lines}</div>${more}`;
}

function renderCategorySelect(mergeRowIndex, currentCategory) {
  const normalizedCurrent = String(currentCategory || "").trim();
  const seen = new Set();
  const values = ["", "Other", normalizedCurrent, ...categoryOptions]
    .map((item) => String(item || "").trim())
    .filter((item, idx, arr) => idx === arr.indexOf(item));

  const options = values
    .map((token) => {
      if (seen.has(token)) {
        return "";
      }
      seen.add(token);
      const selected = token === normalizedCurrent ? " selected" : "";
      const label = token || "(empty)";
      return `<option value="${escapeHtml(token)}"${selected}>${escapeHtml(label)}</option>`;
    })
    .filter(Boolean);

  return [`<select class="tx-category-select" data-merge-row-index="${mergeRowIndex}">`, ...options, `</select>`].join("");
}

async function loadBalanceChart() {
  if (!activeJobId) {
    drawBalanceChart([]);
    return;
  }
  const payload = await fetchBalances(activeJobId);
  drawBalanceChart(payload.series || []);
}

function updateTransactionSummary() {
  if (!activeJobId) {
    txSummary.textContent = "No merge job selected.";
    return;
  }
  const mergedCount = Number(txDecisionCounts.merged || 0);
  const droppedCount = Number(txDecisionCounts.dropped || 0);
  const droppedMode = txIncludeDroppedInput && txIncludeDroppedInput.checked ? "including" : "excluding";
  txSummary.textContent = `Showing page ${txPage}/${getTxTotalPages()} (${txTotal} filtered, ${txOverallTotal} overall, ${droppedMode} dropped rows). Merged: ${mergedCount}, Dropped: ${droppedCount}. Selected merged rows: ${selectedRows.size}.`;
  if (txPageSummaryEl) {
    txPageSummaryEl.textContent = `Rows ${txTotal ? ((txPage - 1) * txPageSize) + 1 : 0}-${Math.min(txPage * txPageSize, txTotal)} of ${txTotal}`;
  }
}

function wireRowCheckboxes() {
  document.querySelectorAll(".row-checkbox").forEach((cb) => {
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
}

function wireTransactionDetailButtons() {
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
        alert(error.message);
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
        alert(error.message);
      }
    });
  });
}

function buildTransactionRowKey(rowSource, rowLocalIndex) {
  const source = String(rowSource || "").trim().toLowerCase();
  const idx = Number(rowLocalIndex || 0);
  return `${source}:${idx}`;
}

function selectTransactionRow(rowSource, rowLocalIndex) {
  activeTransactionKey = buildTransactionRowKey(rowSource, rowLocalIndex);
  txBody.querySelectorAll("tr[data-row-key]").forEach((row) => {
    row.classList.toggle("selected", String(row.dataset.rowKey || "") === activeTransactionKey);
  });
}

async function openTransactionDetail(rowSource, rowLocalIndex, rowId = "") {
  if (!rowSource || !rowLocalIndex || !activeJobId) {
    return;
  }
  selectTransactionRow(rowSource, rowLocalIndex);
  const detail = await fetchTransactionDetail(activeJobId, rowSource, rowLocalIndex);
  const displayId = String(rowId || detail.id || `${rowSource}:${rowLocalIndex}`);
  openDetailModal(`Transaction ${displayId}`, renderObjectDetails(detail));
}

function getTxTotalPages() {
  return Math.max(1, Math.ceil(txTotal / Math.max(1, txPageSize)));
}

function updateTxPagination() {
  const totalPages = getTxTotalPages();
  const canPrev = txPage > 1;
  const canNext = txPage < totalPages;
  if (txPageFirstBtn) txPageFirstBtn.disabled = !canPrev;
  if (txPagePrevBtn) txPagePrevBtn.disabled = !canPrev;
  if (txPageNextBtn) txPageNextBtn.disabled = !canNext;
  if (txPageLastBtn) txPageLastBtn.disabled = !canNext;
  if (!txPageButtons) {
    return;
  }
  txPageButtons.innerHTML = renderPageButtonsHtml(txPage, totalPages, "tx-page-btn");
  txPageButtons.querySelectorAll(".tx-page-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const page = Number(btn.dataset.page || 1);
      if (page === txPage) {
        return;
      }
      txPage = page;
      try {
        await loadTransactions(false);
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

function getDupTotalPages() {
  return Math.max(1, Math.ceil(dupTotal / Math.max(1, dupPageSize)));
}

function applyDuplicateReviewGateToActions() {
  const completed = String(activeJobStatus || "") === "completed";
  const canProceed = !!(duplicateReviewStatus && duplicateReviewStatus.can_proceed);
  const allowed = completed && canProceed;
  if (categorizeOllamaBtn) categorizeOllamaBtn.disabled = !allowed;
  if (categorizeAllOllamaBtn) categorizeAllOllamaBtn.disabled = !allowed;
  if (startFireflyExportBtn) startFireflyExportBtn.disabled = !allowed;
}

function updateDuplicateReviewGateUI() {
  if (!dupGateSummary) {
    applyDuplicateReviewGateToActions();
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
    applyDuplicateReviewGateToActions();
    return;
  }
  if (confirmed) {
    dupGateSummary.textContent = `Duplicate review confirmed. Remaining suspected duplicates: ${pending}. Restored: ${restored}.`;
    applyDuplicateReviewGateToActions();
    return;
  }
  dupGateSummary.textContent =
    `Duplicate review required before categorization/export. Remaining suspected duplicates: ${pending}. ` +
    `Review rows below, restore any false positives, then click Confirm Review.`;
  applyDuplicateReviewGateToActions();
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

function setDuplicateSourcePreference() {
  if (!dupSourceFileFilter) {
    return;
  }
  preferredDupSourceFile = String(dupSourceFileFilter.value || "");
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
        <tr data-dup-row-index="${dupIdx}">
          <td data-label="Select"><input type="checkbox" class="dup-row-checkbox" data-dup-row-index="${dupIdx}" ${selected}></td>
          <td data-label="Dropped ID"><code>${escapeHtml(String(row.id || ""))}</code></td>
          <td data-label="Reason">${escapeHtml(String(row.duplicate_reason || ""))}</td>
          <td data-label="Reasoning">${escapeHtml(String(row.duplicate_reasoning || ""))}</td>
          <td data-label="Dropped Date">${escapeHtml(String(row.duplicate_date || ""))}</td>
          <td data-label="Dropped Amount" class="num">${escapeHtml(String(row.duplicate_amount || ""))}</td>
          <td data-label="Dropped Description">${escapeHtml(String(row.duplicate_description || ""))}</td>
          <td data-label="Dropped Source">${escapeHtml(String(row.source_file || ""))}</td>
          <td data-label="Kept ID"><code>${escapeHtml(keptId)}</code></td>
          <td data-label="Kept Date">${escapeHtml(String(row.kept_date || ""))}</td>
          <td data-label="Kept Amount" class="num">${escapeHtml(String(row.kept_amount || ""))}</td>
          <td data-label="Kept Description">${escapeHtml(String(row.kept_description || ""))}<div><span class="${matchClass}">${matchText}</span></div></td>
          <td data-label="Details" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="dup-open-dropped secondary-btn" data-row-source="duplicates" data-row-local-index="${dupIdx}" data-row-id="${escapeHtml(String(row.id || ""))}">Dropped</button>
              <button type="button" class="dup-open-kept secondary-btn" data-row-source="merged" data-row-local-index="${keptIdx}" data-row-id="${escapeHtml(keptId)}" ${keptIdx > 0 ? "" : "disabled"}>Kept</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

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

  dupBody.querySelectorAll(".dup-open-dropped, .dup-open-kept").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const rowSource = String(btn.dataset.rowSource || "");
      const rowLocalIndex = Number(btn.dataset.rowLocalIndex || 0);
      const rowId = String(btn.dataset.rowId || "");
      if (!rowSource || !rowLocalIndex || !activeJobId) {
        return;
      }
      try {
        await openTransactionDetail(rowSource, rowLocalIndex, rowId);
      } catch (error) {
        alert(error.message);
      }
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
    dupPageSummaryEl.textContent = `Rows ${dupTotal ? ((dupPage - 1) * dupPageSize) + 1 : 0}-${Math.min(dupPage * dupPageSize, dupTotal)} of ${dupTotal}`;
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
        alert(error.message);
      }
    });
  });
}

async function loadDuplicateReview(reset = false) {
  if (!activeJobId) {
    dupTotal = 0;
    selectedDuplicateRows.clear();
    duplicateReviewStatus = {
      required: false,
      confirmed: true,
      can_proceed: true,
      pending_duplicates: 0,
      initial_duplicates: 0,
      restored_rows_total: 0,
    };
    updateDuplicateReviewGateUI();
    if (dupBody) dupBody.innerHTML = `<tr><td colspan="13">No job selected.</td></tr>`;
    if (dupSummary) dupSummary.textContent = "Select a completed merge job to review duplicates.";
    if (dupPageSummaryEl) dupPageSummaryEl.textContent = "Rows 0-0 of 0";
    updateDupPagination();
    return;
  }
  if (reset) {
    dupPage = 1;
  }
  dupPageSize = Math.max(1, Number((dupPageSizeInput && dupPageSizeInput.value) || 20));
  const offset = (Math.max(1, dupPage) - 1) * dupPageSize;
  const payload = await fetchDuplicateReviewRows(activeJobId, offset, dupPageSize);
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
  if (!activeJobId) {
    return;
  }
  duplicateReviewStatus = await fetchDuplicateReviewStatus(activeJobId);
  updateDuplicateReviewGateUI();
}

function drawBalanceChart(series) {
  chartEl.innerHTML = "";
  legendEl.innerHTML = "";
  if (!series.length) {
    chartEl.innerHTML = "<text x='20' y='40'>No balance data available.</text>";
    return;
  }

  const palette = ["#1f6f5f", "#b83b5e", "#2b65d9", "#b67c00", "#006a8e", "#6a4c93", "#008a43", "#ba4a00"];
  let allPoints = [];
  series.forEach((s) => {
    allPoints = allPoints.concat(s.points || []);
  });
  const values = allPoints.map((p) => Number(p.balance || 0));
  const minY = Math.min(...values);
  const maxY = Math.max(...values);
  const span = Math.max(1, maxY - minY);

  const dateSet = new Set(allPoints.map((p) => p.date));
  const dates = Array.from(dateSet).sort();
  const dateIndex = new Map(dates.map((d, i) => [d, i]));

  const width = 980;
  const height = 320;
  const pad = 34;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;

  chartEl.insertAdjacentHTML("beforeend", `<rect x="${pad}" y="${pad}" width="${plotW}" height="${plotH}" class="chart-frame"></rect>`);

  series.forEach((accountSeries, i) => {
    const color = palette[i % palette.length];
    const points = (accountSeries.points || []).map((p) => {
      const xIdx = dateIndex.get(p.date) || 0;
      const x = pad + (dates.length <= 1 ? 0 : (xIdx / (dates.length - 1)) * plotW);
      const y = pad + plotH - ((Number(p.balance || 0) - minY) / span) * plotH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    if (points.length >= 2) {
      chartEl.insertAdjacentHTML("beforeend", `<polyline points="${points.join(" ")}" fill="none" stroke="${color}" stroke-width="2"></polyline>`);
    }
    legendEl.insertAdjacentHTML("beforeend", `<span class="legend-item"><i style="background:${color}"></i>${escapeHtml(accountSeries.account || "Unknown")}</span>`);
  });

  chartEl.insertAdjacentHTML("beforeend", `<text x="10" y="${pad + 8}" class="chart-label">${maxY.toFixed(2)}</text>`);
  chartEl.insertAdjacentHTML("beforeend", `<text x="10" y="${height - pad}" class="chart-label">${minY.toFixed(2)}</text>`);
}

async function selectOllamaEvent(eventId) {
  const event = ollamaEventsById.get(Number(eventId || 0));
  if (!event) {
    return;
  }
  activeOllamaEventId = Number(event.id || 0);
  ollamaEventsBody.querySelectorAll("tr").forEach((row) => {
    row.classList.toggle("selected", Number(row.dataset.eventId || 0) === activeOllamaEventId);
  });
  try {
    const detail = await fetchOllamaEvent(activeOllamaEventId);
    ollamaEventsById.set(activeOllamaEventId, detail);
    openDetailModal(`Ollama Event ${activeOllamaEventId}`, renderOllamaDetail(detail));
  } catch (error) {
    alert(String(error.message || error));
  }
}

function escapeHtml(raw) {
  const div = document.createElement("div");
  div.textContent = String(raw ?? "");
  return div.innerHTML;
}

function renderPageButtonsHtml(currentPage, totalPages, buttonClass) {
  if (totalPages <= 1) {
    return `<button type="button" class="secondary-btn ${buttonClass} page-btn-active" data-page="1">1</button>`;
  }
  const radius = 2;
  const start = Math.max(1, currentPage - radius);
  const end = Math.min(totalPages, currentPage + radius);
  const items = [];
  for (let page = start; page <= end; page += 1) {
    const active = page === currentPage ? " page-btn-active" : "";
    items.push(`<button type="button" class="secondary-btn ${buttonClass}${active}" data-page="${page}">${page}</button>`);
  }
  return items.join("");
}

function renderObjectDetails(detail) {
  const keys = Object.keys(detail || {}).sort((a, b) => a.localeCompare(b));
  const rows = keys.map((key) => {
    const rawValue = detail[key];
    const value = rawValue && typeof rawValue === "object" ? JSON.stringify(rawValue) : String(rawValue ?? "");
    return `<div class="detail-item"><strong>${escapeHtml(key)}</strong><span>${escapeHtml(value)}</span></div>`;
  });
  return `<div class="detail-grid">${rows.join("") || "<div class='detail-item'><span>No details.</span></div>"}</div>`;
}

function renderOllamaDetail(detail) {
  const summary = {
    id: detail.id || "",
    status: detail.status || "",
    job_id: detail.job_id || "",
    merge_row_index: detail.merge_row_index || "",
    model: detail.model || "",
    created_at: detail.created_at || "",
    started_at: detail.started_at || "",
    finished_at: detail.finished_at || "",
    external_id: detail.external_id || "",
    date: detail.date || "",
    amount: detail.amount || "",
    category: detail.category || "",
    description: detail.description || "",
    source_account: detail.source_account || "",
    destination_account: detail.destination_account || "",
    error: detail.error || "",
  };
  return [
    renderObjectDetails(summary),
    "<h4>Prompt</h4>",
    `<pre>${escapeHtml(detail.prompt || "")}</pre>`,
    "<h4>Response</h4>",
    `<pre>${escapeHtml(detail.response || "")}</pre>`,
  ].join("");
}

function openDetailModal(title, html) {
  if (!detailModalEl) {
    return;
  }
  if (detailModalTitleEl) {
    detailModalTitleEl.textContent = String(title || "Details");
  }
  if (detailModalContentEl) {
    detailModalContentEl.innerHTML = String(html || "");
  }
  detailModalEl.hidden = false;
}

function closeDetailModal() {
  if (!detailModalEl) {
    return;
  }
  detailModalEl.hidden = true;
  if (detailModalContentEl) {
    detailModalContentEl.innerHTML = "";
  }
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
    progressPct: total > 0 ? ((processed / total) * 100) : 0,
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

function updateGlobalQueueCard(kind, context, metrics) {
  const isOllama = kind === "ollama";
  const barEl = isOllama ? globalOllamaBarEl : globalExportBarEl;
  const textEl = isOllama ? globalOllamaTextEl : globalExportTextEl;
  const metaEl = isOllama ? globalOllamaMetaEl : globalExportMetaEl;
  if (!barEl || !textEl || !metaEl) {
    return;
  }

  const model = buildQueueProgressModel(metrics);
  const contextJobId = String((context && context.job_id) || "").trim();
  const contextExportId = String((context && context.export_id) || "").trim();
  const hasContext = isOllama ? !!contextJobId : !!contextExportId;
  const hasActiveQueue = hasContext && model.total > 0;
  if (!hasActiveQueue) {
    metaEl.textContent = "No active queue.";
    textEl.textContent = "Progress: 0.0% | Speed: - | ETA: -";
    barEl.style.width = "0%";
    barEl.classList.remove("is-warning", "is-danger");
    return;
  }

  let metaText = "";
  if (isOllama) {
    metaText = contextJobId ? `Job: ${contextJobId}` : "Active queue";
  } else {
    if (contextExportId && contextJobId) {
      metaText = `Export: ${contextExportId} | Job: ${contextJobId}`;
    } else if (contextExportId) {
      metaText = `Export: ${contextExportId}`;
    } else if (contextJobId) {
      metaText = `Job: ${contextJobId}`;
    } else {
      metaText = "Active queue";
    }
  }
  metaEl.textContent = metaText;
  textEl.textContent = `${model.processed}/${model.total} (${model.progressPct.toFixed(1)}%) | Speed: ${queueSpeedText(model)} | ${queueEtaText(model)}`;
  barEl.style.width = `${Math.max(0, Math.min(100, model.progressPct)).toFixed(1)}%`;
  barEl.classList.toggle("is-warning", model.failed > 0 && (model.queued > 0 || model.running > 0));
  barEl.classList.toggle("is-danger", model.failed > 0 && model.queued <= 0 && model.running <= 0);
}

async function loadQueueSummary() {
  const payload = await fetchQueueSummary();
  const ollama = payload && typeof payload === "object" ? payload.ollama || {} : {};
  const firefly = payload && typeof payload === "object" ? payload.firefly_export || {} : {};
  updateGlobalQueueCard(
    "ollama",
    {
      job_id: String(ollama.job_id || ""),
    },
    ollama.metrics || {}
  );
  updateGlobalQueueCard(
    "export",
    {
      export_id: String(firefly.export_id || ""),
      job_id: String(firefly.job_id || ""),
    },
    firefly.metrics || {}
  );
}

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

async function ensureDuplicateReviewReadyForProcessing() {
  if (!activeJobId) {
    return false;
  }
  const status = await fetchDuplicateReviewStatus(activeJobId);
  duplicateReviewStatus = status || duplicateReviewStatus;
  updateDuplicateReviewGateUI();
  if (status && status.can_proceed) {
    return true;
  }
  const pending = Number((status && status.pending_duplicates) || 0);
  activateMainTab("merge-workspace");
  activateSubTab("duplicates-panel");
  throw new Error(
    `Duplicate review required before categorization/export. Pending suspected duplicates: ${pending}.`
  );
}

async function runCategorization(mode, allRows = false) {
  if (!activeJobId) {
    alert("Run a merge job first.");
    return;
  }
  let selection = null;
  if (!allRows) {
    if (!selectedRows.size) {
      alert("Select at least one merged transaction.");
      return;
    }
    selection = Array.from(selectedRows).sort((a, b) => a - b);
  }

  try {
    await ensureDuplicateReviewReadyForProcessing();
    const isOllama = mode === "ollama";
    const autoExport = !!(autoExportAfterCategorizeInput && autoExportAfterCategorizeInput.checked && isOllama);
    if (isOllama) {
      if (ollamaJobFilterInput) {
        ollamaJobFilterInput.value = activeJobId;
      }
      if (ollamaStatusGroupInput) {
        ollamaStatusGroupInput.value = "queue";
      }
      if (ollamaSortByInput) {
        ollamaSortByInput.value = "id";
      }
      if (ollamaSortDirInput) {
        ollamaSortDirInput.value = "asc";
      }
      activateMainTab("merge-workspace");
      activateSubTab("ollama-panel");
      await loadOllamaEvents({ resetPage: true });
    }

    const result = await categorize(activeJobId, mode, selection, { autoExport });
    if (mode === "ollama") {
      const exportInfo =
        result.auto_export
          ? (result.export_id ? ` Auto export job: ${result.export_id}.` : " Auto export is enabled; categorized batches will be queued to export.")
          : "";
      alert(`Ollama categorization queued. Queued: ${result.queued ?? 0}, skipped: ${result.skipped ?? 0}.${exportInfo}`);
    } else {
      alert(`Categorization done. Updated ${result.updated}, skipped ${result.skipped}.`);
    }
    selectedRows.clear();
    await loadTransactions(true);
    await loadOllamaEvents({ resetPage: true });
    await loadQueueSummary().catch(() => {});
  } catch (error) {
    alert(error.message);
  }
}

function renderHistoryRows(targetBody, jobs) {
  if (!targetBody) {
    return;
  }
  if (!jobs.length) {
    targetBody.innerHTML = `<tr><td colspan="6">No jobs yet.</td></tr>`;
    return;
  }

  targetBody.innerHTML = jobs
    .map((job) => {
      const stats = job.stats || {};
      const isActive = activeJobId && String(activeJobId) === String(job.id);
      const message = job.error ? escapeHtml(job.error) : escapeHtml(job.message || "");
      return `
        <tr>
          <td data-label="Job ID"><code>${escapeHtml(job.id)}</code></td>
          <td data-label="Status">${escapeHtml(job.status || "")}</td>
          <td data-label="Created">${escapeHtml(job.created_at || "")}</td>
          <td data-label="Merged">${escapeHtml(String(stats.merged_rows ?? 0))}</td>
          <td data-label="Duplicates">${escapeHtml(String(stats.duplicate_rows ?? 0))}</td>
          <td data-label="Actions" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="open-job" data-job-id="${escapeHtml(job.id)}">${isActive ? "Opened" : "Open"}</button>
              <button type="button" class="delete-job" data-job-id="${escapeHtml(job.id)}">Delete</button>
              ${message ? `<span class="hint">${message}</span>` : ""}
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function bindHistoryOpenHandlers() {
  [historyBodyTab].forEach((body) => {
    if (!body) {
      return;
    }
    body.querySelectorAll(".open-job").forEach((btn) => {
      btn.addEventListener("click", async (event) => {
        const jobId = String(event.target.dataset.jobId || "");
        if (!jobId) {
          return;
        }
        await openExistingJob(jobId, "job-panel");
      });
    });
    body.querySelectorAll(".delete-job").forEach((btn) => {
      btn.addEventListener("click", async (event) => {
        const jobId = String(event.target.dataset.jobId || "");
        if (!jobId) {
          return;
        }
        const approved = window.confirm(`Delete job ${jobId}? This removes artifacts, logs and queue records.`);
        if (!approved) {
          return;
        }
        try {
          await deleteJobRequest(jobId);
          if (activeJobId && activeJobId === jobId) {
            resetActiveJobView();
          }
          await loadJobHistory();
        } catch (error) {
          alert(error.message);
        }
      });
    });
  });
}

async function loadJobHistory() {
  const payload = await fetchJobs(500);
  const jobs = payload.jobs || [];
  knownJobs = jobs;
  renderHistoryRows(historyBodyTab, jobs);
  refreshActiveJobControls();
  bindHistoryOpenHandlers();
}

function renderOllamaEvents(events) {
  ollamaEventsById.clear();

  if (!events.length) {
    ollamaEventsBody.innerHTML = `<tr><td colspan="9">No Ollama events yet.</td></tr>`;
    activeOllamaEventId = 0;
    return;
  }

  ollamaEventsBody.innerHTML = events
    .map((event) => {
      const id = Number(event.id || 0);
      if (id) {
        ollamaEventsById.set(id, event);
      }
      return `
        <tr data-event-id="${id}">
          <td data-label="ID"><code>${escapeHtml(String(id))}</code></td>
          <td data-label="Status">${escapeHtml(event.status || "")}</td>
          <td data-label="Date">${escapeHtml(event.date || "")}</td>
          <td data-label="Amount" class="num">${escapeHtml(event.amount || "")}</td>
          <td data-label="Category">${escapeHtml(event.category || "")}</td>
          <td data-label="Description">${escapeHtml(event.description || "")}</td>
          <td data-label="Source Account">${escapeHtml(event.source_account || "")}</td>
          <td data-label="Destination Account">${escapeHtml(event.destination_account || "")}</td>
          <td data-label="Actions" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="ollama-event-open secondary-btn" data-event-id="${id}">Open</button>
              <button type="button" class="ollama-event-delete danger-btn" data-event-id="${id}" ${String(event.status || "") === "running" ? "disabled" : ""}>Delete</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  ollamaEventsBody.querySelectorAll(".ollama-event-open").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const eventId = Number(btn.dataset.eventId || 0);
      selectOllamaEvent(eventId);
    });
  });
  ollamaEventsBody.querySelectorAll(".ollama-event-delete").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const eventId = Number(btn.dataset.eventId || 0);
      if (!eventId) return;
      const approved = window.confirm(`Delete Ollama queue item ${eventId}?`);
      if (!approved) return;
      try {
        await deleteOllamaQueueItem(eventId);
        await loadOllamaEvents({ resetPage: false });
        await loadQueueSummary().catch(() => {});
      } catch (error) {
        alert(error.message);
      }
    });
  });

  ollamaEventsBody.querySelectorAll("tr[data-event-id]").forEach((row) => {
    row.addEventListener("click", () => {
      selectOllamaEvent(Number(row.dataset.eventId || 0));
    });
  });
}

function updateOllamaEventListMeta() {
  if (ollamaEventsSummaryEl) {
    const totalPages = getOllamaTotalPages();
    const filterText = ollamaCurrentFilter ? ` for job ${ollamaCurrentFilter}` : "";
    const start = ollamaTotalCount ? ((ollamaPage - 1) * ollamaPageSize) + 1 : 0;
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
  ollamaCurrentFilter = jobFilter;

  const offset = (Math.max(1, ollamaPage) - 1) * ollamaPageSize;
  const payload = await fetchOllamaEvents({
    limit: ollamaPageSize,
    offset,
    jobId: jobFilter,
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
  renderOllamaEvents(events);
  updateOllamaEventListMeta();
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
        alert(error.message);
      }
    });
  });
}

function updateExportMetrics(metrics) {
  if (!exportEventsMetricsEl) {
    return;
  }
  const model = buildQueueProgressModel(metrics);
  if (model.total <= 0) {
    exportEventsMetricsEl.textContent = "No export queue metrics yet.";
    return;
  }
  exportEventsMetricsEl.textContent = queueProgressLine(model);
}

async function selectExportEvent(eventId) {
  const event = exportEventsById.get(Number(eventId || 0));
  if (!event || !activeJobId) {
    return;
  }
  activeExportEventId = Number(event.id || 0);
  exportEventsBody.querySelectorAll("tr[data-event-id]").forEach((row) => {
    row.classList.toggle("selected", Number(row.dataset.eventId || 0) === activeExportEventId);
  });
  try {
    const detail = await fetchFireflyExportEvent(activeJobId, activeExportEventId);
    exportEventsById.set(activeExportEventId, detail);
    openDetailModal(`Export Event ${activeExportEventId}`, renderObjectDetails(detail));
  } catch (error) {
    alert(String(error.message || error));
  }
}

function renderExportEvents(events) {
  exportEventsById.clear();
  if (!exportEventsBody) {
    return;
  }
  if (!events.length) {
    exportEventsBody.innerHTML = `<tr><td colspan="10">No export queue events yet.</td></tr>`;
    activeExportEventId = 0;
    return;
  }
  exportEventsBody.innerHTML = events
    .map((event) => {
      const id = Number(event.id || 0);
      if (id) {
        exportEventsById.set(id, event);
      }
      const selected = activeExportEventId && activeExportEventId === id ? "selected" : "";
      return `
        <tr class="${selected}" data-event-id="${id}">
          <td data-label="ID"><code>${escapeHtml(String(id))}</code></td>
          <td data-label="Status">${escapeHtml(event.status || "")}</td>
          <td data-label="Date">${escapeHtml(event.date || "")}</td>
          <td data-label="Amount" class="num">${escapeHtml(event.amount || "")}</td>
          <td data-label="Category">${escapeHtml(event.category || "")}</td>
          <td data-label="Description">${escapeHtml(event.description || "")}</td>
          <td data-label="Source Account">${escapeHtml(event.source_account || "")}</td>
          <td data-label="Destination Account">${escapeHtml(event.destination_account || "")}</td>
          <td data-label="Batch">${escapeHtml(String(event.batch_number || 0))}</td>
          <td data-label="Actions" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="export-event-open secondary-btn" data-event-id="${id}">Open</button>
              <button type="button" class="export-event-delete danger-btn" data-event-id="${id}" ${String(event.status || "") === "running" ? "disabled" : ""}>Delete</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  exportEventsBody.querySelectorAll(".export-event-open").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const eventId = Number(btn.dataset.eventId || 0);
      selectExportEvent(eventId);
    });
  });
  exportEventsBody.querySelectorAll(".export-event-delete").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const eventId = Number(btn.dataset.eventId || 0);
      if (!eventId || !activeJobId) return;
      const approved = window.confirm(`Delete export queue item ${eventId}?`);
      if (!approved) return;
      try {
        await deleteFireflyExportEvent(activeJobId, eventId);
        await loadFireflyExportEvents(false);
        await loadQueueSummary().catch(() => {});
      } catch (error) {
        alert(error.message);
      }
    });
  });

  exportEventsBody.querySelectorAll("tr[data-event-id]").forEach((row) => {
    row.addEventListener("click", () => {
      selectExportEvent(Number(row.dataset.eventId || 0));
    });
  });
}

function getExportEventsTotalPages() {
  return Math.max(1, Math.ceil(exportEventsTotal / Math.max(1, exportEventsPageSize)));
}

function updateExportEventsSummary() {
  if (exportEventsSummaryEl) {
    const totalPages = getExportEventsTotalPages();
    const start = exportEventsTotal ? ((exportEventsPage - 1) * exportEventsPageSize) + 1 : 0;
    const end = Math.min(exportEventsPage * exportEventsPageSize, exportEventsTotal);
    const exportText = activeExportId ? ` for export ${activeExportId}` : "";
    exportEventsSummaryEl.textContent = `Rows ${start}-${end} of ${exportEventsTotal}. Page ${exportEventsPage}/${totalPages}${exportText}.`;
  }
  updateExportEventsPagination();
}

function updateExportEventsPagination() {
  const totalPages = getExportEventsTotalPages();
  const canPrev = exportEventsPage > 1;
  const canNext = exportEventsPage < totalPages;
  if (exportEventsPageFirstBtn) exportEventsPageFirstBtn.disabled = !canPrev;
  if (exportEventsPagePrevBtn) exportEventsPagePrevBtn.disabled = !canPrev;
  if (exportEventsPageNextBtn) exportEventsPageNextBtn.disabled = !canNext;
  if (exportEventsPageLastBtn) exportEventsPageLastBtn.disabled = !canNext;
  if (!exportEventsPageButtons) {
    return;
  }
  exportEventsPageButtons.innerHTML = renderPageButtonsHtml(exportEventsPage, totalPages, "export-events-page-btn");
  exportEventsPageButtons.querySelectorAll(".export-events-page-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const page = Number(btn.dataset.page || 1);
      if (page === exportEventsPage) {
        return;
      }
      exportEventsPage = page;
      try {
        await loadFireflyExportEvents(false);
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

async function loadFireflyExportEvents(resetPage = false) {
  if (!activeJobId || !activeExportId) {
    exportEventsTotal = 0;
    if (exportEventsBody) exportEventsBody.innerHTML = `<tr><td colspan="10">No export selected.</td></tr>`;
    if (exportEventsSummaryEl) exportEventsSummaryEl.textContent = "Select an export to inspect queue details.";
    if (exportEventsMetricsEl) exportEventsMetricsEl.textContent = "No export queue metrics yet.";
    updateExportEventsPagination();
    return;
  }
  if (resetPage) {
    exportEventsPage = 1;
  }
  exportEventsPageSize = Math.max(1, Number((exportEventsPageSizeInput && exportEventsPageSizeInput.value) || 20));
  const statusGroup = String((exportEventsStatusGroupInput && exportEventsStatusGroupInput.value) || "all");
  const sortBy = String((exportEventsSortByInput && exportEventsSortByInput.value) || "id");
  const sortDir = String((exportEventsSortDirInput && exportEventsSortDirInput.value) || "asc");
  const offset = (Math.max(1, exportEventsPage) - 1) * exportEventsPageSize;
  const payload = await fetchFireflyExportEvents(activeJobId, activeExportId, {
    limit: exportEventsPageSize,
    offset,
    statusGroup,
    sortBy,
    sortDir,
  });
  exportEventsTotal = Number(payload.total || 0);
  updateExportMetrics(payload.metrics || {});
  const totalPages = getExportEventsTotalPages();
  if (exportEventsPage > totalPages) {
    exportEventsPage = totalPages;
    await loadFireflyExportEvents(false);
    return;
  }
  renderExportEvents(Array.isArray(payload.events) ? payload.events : []);
  updateExportEventsSummary();
}

function renderFireflyExportRows(items) {
  if (!exportBody) {
    return;
  }
  if (!items.length) {
    exportBody.innerHTML = `<tr><td colspan="8">No exports yet for this merge job.</td></tr>`;
    return;
  }
  exportBody.innerHTML = items
    .map((item) => {
      const stats = item.stats || {};
      const exportId = String(item.id || "");
      const selected = activeExportId && activeExportId === exportId ? "selected" : "";
      const message = item.error ? String(item.error) : String(item.message || "");
      const failedRows = Number(stats.failed_rows ?? 0);
      const status = String(item.status || "");
      const canRetry =
        status !== "queued" &&
        status !== "running" &&
        (failedRows > 0 || status === "failed");
      return `
        <tr class="${selected}" data-export-id="${escapeHtml(exportId)}">
          <td data-label="Export ID"><code>${escapeHtml(exportId)}</code></td>
          <td data-label="Status">${escapeHtml(item.status || "")}</td>
          <td data-label="Created">${escapeHtml(item.created_at || "")}</td>
          <td data-label="Updated">${escapeHtml(item.updated_at || "")}</td>
          <td data-label="Rows">${escapeHtml(String(stats.exported_rows ?? 0))}</td>
          <td data-label="Batches">${escapeHtml(String(stats.batches ?? 0))}</td>
          <td data-label="Message">${escapeHtml(message)}</td>
          <td data-label="Actions" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="open-export" data-export-id="${escapeHtml(exportId)}">${selected ? "Opened" : "Open"}</button>
              <button type="button" class="retry-failed-export secondary-btn" data-export-id="${escapeHtml(exportId)}" ${canRetry ? "" : "disabled"}>Retry Failed</button>
              <button type="button" class="delete-export danger-btn" data-export-id="${escapeHtml(exportId)}">Delete</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  exportBody.querySelectorAll(".open-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const exportId = String(btn.dataset.exportId || "");
      if (!exportId) return;
      try {
        await openFireflyExport(exportId);
      } catch (error) {
        alert(error.message);
      }
    });
  });
  exportBody.querySelectorAll(".retry-failed-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sourceExportId = String(btn.dataset.exportId || "");
      if (!sourceExportId || !activeJobId) {
        return;
      }
      btn.disabled = true;
      try {
        const payload = await retryFailedFireflyExport(activeJobId, sourceExportId);
        const newExportId = String(payload.export_id || "");
        await loadFireflyExports(true);
        if (newExportId) {
          await openFireflyExport(newExportId);
        }
      } catch (error) {
        alert(error.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
  exportBody.querySelectorAll(".delete-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const targetExportId = String(btn.dataset.exportId || "");
      if (!targetExportId || !activeJobId) {
        return;
      }
      const approved = window.confirm(`Delete export queue ${targetExportId}?`);
      if (!approved) {
        return;
      }
      btn.disabled = true;
      try {
        await deleteFireflyExport(activeJobId, targetExportId);
        if (activeExportId === targetExportId) {
          activeExportId = "";
          activeExportEventId = 0;
        }
        await loadFireflyExports(true);
        await loadQueueSummary().catch(() => {});
      } catch (error) {
        alert(error.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function renderFireflyExportDetail(item) {
  if (!item) {
    if (exportLogsEl) {
      exportLogsEl.textContent = "";
    }
    return;
  }
  const stats = item.stats || {};
  const message = item.error ? String(item.error) : String(item.message || "");
  if (exportSummaryEl) {
    exportSummaryEl.textContent =
      `Export ${item.id || ""} is ${item.status || "unknown"}. ` +
      `Rows exported: ${stats.exported_rows ?? 0}, failed: ${stats.failed_rows ?? 0}, queued: ${stats.queued_rows ?? 0}, batches: ${stats.batches ?? 0}. ` +
      `${message || ""}`.trim();
  }
  if (exportLogsEl) {
    exportLogsEl.textContent = item.logs || "";
    exportLogsEl.scrollTop = exportLogsEl.scrollHeight;
  }
}

function startExportPolling(exportId) {
  stopExportPolling();
  if (!activeJobId || !exportId) {
    return;
  }
  exportPollTimer = setInterval(async () => {
    try {
      const item = await fetchFireflyExport(activeJobId, exportId);
      renderFireflyExportDetail(item);
      await loadFireflyExportEvents(false);
      if (item.status === "completed" || item.status === "failed") {
        stopExportPolling();
        await loadFireflyExports(false);
      }
    } catch (error) {
      stopExportPolling();
    }
  }, 2000);
}

async function openFireflyExport(exportId) {
  if (!activeJobId || !exportId) {
    return;
  }
  activeExportId = String(exportId);
  if (stopFireflyExportBtn) stopFireflyExportBtn.disabled = false;
  if (deleteFireflyExportBtn) deleteFireflyExportBtn.disabled = false;
  activeExportEventId = 0;
  exportEventsPage = 1;
  const item = await fetchFireflyExport(activeJobId, activeExportId);
  renderFireflyExportDetail(item);
  if (exportBody) {
    exportBody.querySelectorAll("tr[data-export-id]").forEach((row) => {
      row.classList.toggle("selected", String(row.dataset.exportId || "") === activeExportId);
    });
    exportBody.querySelectorAll(".open-export").forEach((btn) => {
      btn.textContent = String(btn.dataset.exportId || "") === activeExportId ? "Opened" : "Open";
    });
  }
  if (item.status === "running" || item.status === "queued") {
    startExportPolling(activeExportId);
  } else {
    stopExportPolling();
  }
  await loadFireflyExportEvents(true);
}

async function loadFireflyExports(selectLatest = false) {
  if (!activeJobId) {
    if (startFireflyExportBtn) {
      startFireflyExportBtn.disabled = true;
    }
    if (exportSummaryEl) {
      exportSummaryEl.textContent = "Select a completed merge job first.";
    }
    if (exportBody) {
      exportBody.innerHTML = `<tr><td colspan="8">No job selected.</td></tr>`;
    }
    if (exportLogsEl) {
      exportLogsEl.textContent = "";
    }
    activeExportId = "";
    activeExportEventId = 0;
    exportEventsTotal = 0;
    if (exportEventsBody) {
      exportEventsBody.innerHTML = `<tr><td colspan="10">No export selected.</td></tr>`;
    }
    if (exportEventsSummaryEl) {
      exportEventsSummaryEl.textContent = "Select an export to inspect queue details.";
    }
    if (exportEventsMetricsEl) {
      exportEventsMetricsEl.textContent = "No export queue metrics yet.";
    }
    updateExportEventsPagination();
    stopExportPolling();
    if (stopFireflyExportBtn) stopFireflyExportBtn.disabled = true;
    if (deleteFireflyExportBtn) deleteFireflyExportBtn.disabled = true;
    return;
  }
  const payload = await fetchFireflyExports(activeJobId, 100);
  const items = payload.exports || [];
  if (selectLatest && items.length) {
    activeExportId = String(items[0].id || "");
  } else if (activeExportId && !items.some((item) => String(item.id || "") === activeExportId)) {
    activeExportId = items.length ? String(items[0].id || "") : "";
  }

  renderFireflyExportRows(items);

  if (!items.length) {
    activeExportId = "";
    activeExportEventId = 0;
    exportEventsTotal = 0;
    if (exportEventsBody) exportEventsBody.innerHTML = `<tr><td colspan="10">No export selected.</td></tr>`;
    if (exportEventsSummaryEl) exportEventsSummaryEl.textContent = "No exports yet for this merge job.";
    if (exportEventsMetricsEl) exportEventsMetricsEl.textContent = "No export queue metrics yet.";
    updateExportEventsPagination();
    renderFireflyExportDetail(null);
    if (stopFireflyExportBtn) stopFireflyExportBtn.disabled = true;
    if (deleteFireflyExportBtn) deleteFireflyExportBtn.disabled = true;
    return;
  }
  const currentId = activeExportId || String(items[0].id || "");
  if (currentId) {
    await openFireflyExport(currentId);
  }
}

async function openExistingJob(jobId, subTabName = "job-panel") {
  stopPolling();
  stopExportPolling();
  const targetJobId = String(jobId || "");
  if (!targetJobId) {
    throw new Error("Invalid job ID.");
  }
  activeExportId = "";

  if (txDecisionFilter) txDecisionFilter.value = "all";
  if (txSourceFileFilter) txSourceFileFilter.value = "";
  txPage = 1;
  selectedDuplicateRows.clear();
  dupPage = 1;
  if (dupSourceFileFilter) dupSourceFileFilter.value = "";
  if (toggleAllDupVisible) toggleAllDupVisible.checked = false;

  const job = await fetchJob(targetJobId);
  setProvisionalDuplicateReviewFromJob(job);
  activeJobId = targetJobId;
  renderJob(job);
  activateMainTab("merge-workspace");
  activateSubTab(subTabName);

  if (job.status === "completed") {
    submitButton.disabled = false;
    await loadAnalytics(activeJobId, true);
    await loadFireflyExports(true);
  } else if (job.status === "running" || job.status === "queued") {
    submitButton.disabled = true;
    startPolling(activeJobId);
    await loadFireflyExports(true);
  } else {
    submitButton.disabled = false;
    await loadFireflyExports(true);
  }

  await loadJobHistory();
}

if (filesInput) {
  filesInput.addEventListener("change", () => {
    updateSelectedFilesHint();
  });
}

if (csvDropZone && filesInput) {
  ["dragenter", "dragover"].forEach((eventName) => {
    csvDropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      csvDropZone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    csvDropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      csvDropZone.classList.remove("dragover");
    });
  });
  csvDropZone.addEventListener("drop", (event) => {
    const files = event.dataTransfer && event.dataTransfer.files ? event.dataTransfer.files : null;
    if (!files || !files.length) {
      return;
    }
    try {
      filesInput.files = files;
      updateSelectedFilesHint();
    } catch (error) {
      // fallback: user can still use file picker
    }
  });
  csvDropZone.addEventListener("click", () => {
    filesInput.click();
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  stopPolling();
  stopExportPolling();
  activeExportId = "";

  const formData = new FormData();
  if (!filesInput || !filesInput.files.length) {
    alert("Select at least one bank statement file (CSV or MT940).");
    submitButton.disabled = false;
    return;
  }

  for (const file of filesInput.files) {
    formData.append("files", file);
  }
  formData.append("dedupe_scope", normalizeDedupeScope());
  formData.append("no_dedup", String(readCheckbox("no_dedup")));
  formData.append("dedupe_first_only", String(readCheckbox("dedupe_first_only")));
  formData.append("push_firefly", String(readCheckbox("push_firefly")));
  saveFormPreferences();

  try {
    const response = await fetch("/api/jobs", { method: "POST", body: formData });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.detail || "Failed to create job.");
    }

    const data = await response.json();
    activeJobId = data.job_id;
    saveSessionState();

    if (txDecisionFilter) txDecisionFilter.value = "all";
    if (txSourceFileFilter) txSourceFileFilter.value = "";
    txPage = 1;

    activateMainTab("merge-workspace");
    activateSubTab("job-panel");

    const job = await fetchJob(activeJobId);
    setProvisionalDuplicateReviewFromJob(job);
    renderJob(job);
    await loadJobHistory();

    if (job.status === "completed") {
      submitButton.disabled = false;
      await loadAnalytics(activeJobId, true);
      await loadFireflyExports(true);
    } else {
      startPolling(activeJobId);
      await loadFireflyExports(true);
    }
  } catch (error) {
    alert(error.message);
    submitButton.disabled = false;
  }
});

if (importMergedBtn) {
  importMergedBtn.addEventListener("click", async () => {
    const mergedFile = mergedImportFileInput && mergedImportFileInput.files ? mergedImportFileInput.files[0] : null;
    const duplicatesFile = duplicatesImportFileInput && duplicatesImportFileInput.files ? duplicatesImportFileInput.files[0] : null;
    if (!mergedFile) {
      alert("Select a merged/categorized CSV to import.");
      return;
    }
    importMergedBtn.disabled = true;
    try {
      const data = await importMergedJob(mergedFile, duplicatesFile || null);
      const importedJobId = String(data.job_id || "");
      if (!importedJobId) {
        throw new Error("Import succeeded but no job ID returned.");
      }
      if (mergedImportFileInput) mergedImportFileInput.value = "";
      if (duplicatesImportFileInput) duplicatesImportFileInput.value = "";
      await openExistingJob(importedJobId, "job-panel");
      alert(`Imported as job ${importedJobId}.`);
    } catch (error) {
      alert(error.message);
    } finally {
      importMergedBtn.disabled = false;
    }
  });
}

toggleAllVisible.addEventListener("change", (event) => {
  const checked = !!event.target.checked;
  document.querySelectorAll(".row-checkbox").forEach((cb) => {
    if (cb.disabled) {
      return;
    }
    cb.checked = checked;
    const idx = Number(cb.dataset.mergeRowIndex || 0);
    if (!idx) {
      return;
    }
    if (checked) {
      selectedRows.add(idx);
    } else {
      selectedRows.delete(idx);
    }
  });
  updateTransactionSummary();
});

selectVisibleBtn.addEventListener("click", () => {
  document.querySelectorAll(".row-checkbox").forEach((cb) => {
    if (cb.disabled) return;
    cb.checked = true;
    const idx = Number(cb.dataset.mergeRowIndex || 0);
    if (idx) selectedRows.add(idx);
  });
  updateTransactionSummary();
});

clearSelectionBtn.addEventListener("click", () => {
  selectedRows.clear();
  document.querySelectorAll(".row-checkbox").forEach((cb) => {
    cb.checked = false;
  });
  toggleAllVisible.checked = false;
  updateTransactionSummary();
});

applyTxFiltersBtn.addEventListener("click", async () => {
  txPage = 1;
  selectedRows.clear();
  saveFormPreferences();
  try {
    await loadTransactions(true);
  } catch (error) {
    alert(error.message);
  }
});

if (txSearchInput) {
  txSearchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyTxFiltersBtn.click();
    }
  });
}

if (txPageSizeInput) {
  txPageSizeInput.addEventListener("change", async () => {
    txPage = 1;
    saveFormPreferences();
    try {
      await loadTransactions(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (txPageFirstBtn) {
  txPageFirstBtn.addEventListener("click", async () => {
    if (txPage <= 1) return;
    txPage = 1;
    try {
      await loadTransactions(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (txPagePrevBtn) {
  txPagePrevBtn.addEventListener("click", async () => {
    if (txPage <= 1) return;
    txPage -= 1;
    try {
      await loadTransactions(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (txPageNextBtn) {
  txPageNextBtn.addEventListener("click", async () => {
    const totalPages = getTxTotalPages();
    if (txPage >= totalPages) return;
    txPage += 1;
    try {
      await loadTransactions(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (txPageLastBtn) {
  txPageLastBtn.addEventListener("click", async () => {
    const totalPages = getTxTotalPages();
    if (txPage >= totalPages) return;
    txPage = totalPages;
    try {
      await loadTransactions(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

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
    saveFormPreferences();
    try {
      await loadDuplicateReview(true);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (refreshDupReviewBtn) {
  refreshDupReviewBtn.addEventListener("click", async () => {
    try {
      await loadDuplicateReview(false);
      await loadTransactions(false);
    } catch (error) {
      alert(error.message);
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
    if (!activeJobId) {
      alert("Select a completed merge job first.");
      return;
    }
    if (!selectedDuplicateRows.size) {
      alert("Select at least one suspected duplicate row to restore.");
      return;
    }
    const approved = window.confirm(
      `Restore ${selectedDuplicateRows.size} selected duplicate row(s) back to merged transactions?`
    );
    if (!approved) return;
    restoreDupSelectedBtn.disabled = true;
    try {
      const indices = Array.from(selectedDuplicateRows).sort((a, b) => a - b);
      const result = await restoreDuplicateRowsRequest(activeJobId, indices);
      duplicateReviewStatus = result.review || duplicateReviewStatus;
      selectedDuplicateRows.clear();
      if (toggleAllDupVisible) toggleAllDupVisible.checked = false;
      await loadDuplicateReview(false);
      await loadTransactions(false);
      const updatedJob = await fetchJob(activeJobId);
      renderJob(updatedJob);
      await loadJobHistory();
    } catch (error) {
      alert(error.message);
    } finally {
      restoreDupSelectedBtn.disabled = false;
    }
  });
}

if (confirmDupReviewBtn) {
  confirmDupReviewBtn.addEventListener("click", async () => {
    if (!activeJobId) {
      alert("Select a completed merge job first.");
      return;
    }
    confirmDupReviewBtn.disabled = true;
    try {
      const payload = await confirmDuplicateReviewRequest(activeJobId);
      duplicateReviewStatus = payload.review || duplicateReviewStatus;
      updateDuplicateReviewGateUI();
      const updatedJob = await fetchJob(activeJobId);
      renderJob(updatedJob);
      await loadJobHistory();
      alert("Duplicate review confirmed. Categorization and export are now unlocked.");
    } catch (error) {
      alert(error.message);
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
    saveFormPreferences();
    try {
      await loadDuplicateReview(true);
    } catch (error) {
      alert(error.message);
    }
  });
}

[dupSourceFileFilter, dupSortBy, dupSortDir]
  .filter(Boolean)
  .forEach((el) => {
    el.addEventListener("change", async () => {
      if (el === dupSourceFileFilter) {
        setDuplicateSourcePreference();
      }
      dupPage = 1;
      saveFormPreferences();
      try {
        await loadDuplicateReview(true);
      } catch (error) {
        alert(error.message);
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
      alert(error.message);
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
      alert(error.message);
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
      alert(error.message);
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
      alert(error.message);
    }
  });
}

if (categorizeOllamaBtn) {
  categorizeOllamaBtn.addEventListener("click", () => runCategorization("ollama", false));
}
if (categorizeAllOllamaBtn) {
  categorizeAllOllamaBtn.addEventListener("click", () => runCategorization("ollama", true));
}
if (downloadCategorizedCsvBtn) {
  downloadCategorizedCsvBtn.addEventListener("click", () => {
    if (!activeJobId) {
      alert("Select a merge job first.");
      return;
    }
    downloadCategorizedCsv(activeJobId);
  });
}

if (refreshHistoryTabBtn) {
  refreshHistoryTabBtn.addEventListener("click", async () => {
    try {
      await loadJobHistory();
    } catch (error) {
      alert(error.message);
    }
  });
}

if (activeJobSelect) {
  activeJobSelect.addEventListener("change", async () => {
    const selected = String(activeJobSelect.value || "");
    if (!selected) {
      resetActiveJobView();
      return;
    }
    try {
      const targetSubTab = getActiveSubTab() === "merge-form-panel" ? "job-panel" : getActiveSubTab();
      await openExistingJob(selected, targetSubTab);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (openLatestJobBtn) {
  openLatestJobBtn.addEventListener("click", async () => {
    const latest = getLatestJobCandidate();
    if (!latest || !latest.id) {
      return;
    }
    try {
      await openExistingJob(String(latest.id), "job-panel");
    } catch (error) {
      alert(error.message);
    }
  });
}

if (clearActiveJobBtn) {
  clearActiveJobBtn.addEventListener("click", () => {
    resetActiveJobView();
  });
}

if (jumpHistoryBtn) {
  jumpHistoryBtn.addEventListener("click", () => {
    activateMainTab("history-workspace");
  });
}

emptyOpenLatestButtons.forEach((btn) => {
  btn.addEventListener("click", async () => {
    const latest = getLatestJobCandidate();
    if (!latest || !latest.id) {
      activateMainTab("history-workspace");
      return;
    }
    try {
      await openExistingJob(String(latest.id), "job-panel");
    } catch (error) {
      alert(error.message);
    }
  });
});

emptyGoHistoryButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    activateMainTab("history-workspace");
  });
});

if (refreshOllamaEventsBtn) {
  refreshOllamaEventsBtn.addEventListener("click", async () => {
    try {
      await loadOllamaEvents({ resetPage: true });
    } catch (error) {
      alert(error.message);
    }
  });
}

if (stopOllamaQueueBtn) {
  stopOllamaQueueBtn.addEventListener("click", async () => {
    const jobFilter = String((ollamaJobFilterInput && ollamaJobFilterInput.value) || "").trim() || activeJobId;
    if (!jobFilter) {
      alert("Enter a job id filter or select an active job.");
      return;
    }
    stopOllamaQueueBtn.disabled = true;
    try {
      await stopOllamaQueue(jobFilter);
      await loadOllamaEvents({ resetPage: false });
      await loadQueueSummary().catch(() => {});
    } catch (error) {
      alert(error.message);
    } finally {
      stopOllamaQueueBtn.disabled = false;
    }
  });
}

if (deleteOllamaQueueBtn) {
  deleteOllamaQueueBtn.addEventListener("click", async () => {
    const jobFilter = String((ollamaJobFilterInput && ollamaJobFilterInput.value) || "").trim() || activeJobId;
    const statusGroup = String((ollamaStatusGroupInput && ollamaStatusGroupInput.value) || "all");
    if (!jobFilter) {
      alert("Enter a job id filter or select an active job.");
      return;
    }
    const approved = window.confirm(`Delete Ollama queue items (${statusGroup}) for job ${jobFilter}?`);
    if (!approved) return;
    deleteOllamaQueueBtn.disabled = true;
    try {
      await deleteOllamaQueue(jobFilter, statusGroup);
      await loadOllamaEvents({ resetPage: true });
      await loadQueueSummary().catch(() => {});
    } catch (error) {
      alert(error.message);
    } finally {
      deleteOllamaQueueBtn.disabled = false;
    }
  });
}

if (ollamaPageFirstBtn) {
  ollamaPageFirstBtn.addEventListener("click", async () => {
    if (ollamaPage <= 1) return;
    ollamaPage = 1;
    try {
      await loadOllamaEvents({ resetPage: false });
    } catch (error) {
      alert(error.message);
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
      alert(error.message);
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
      alert(error.message);
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
      alert(error.message);
    }
  });
}

if (startFireflyExportBtn) {
  startFireflyExportBtn.addEventListener("click", async () => {
    if (!activeJobId) {
      alert("Select a completed merge job first.");
      return;
    }
    startFireflyExportBtn.disabled = true;
    try {
      await ensureDuplicateReviewReadyForProcessing();
      const payload = await startFireflyExport(activeJobId);
      activeExportId = String(payload.export_id || "");
      if (exportEventsStatusGroupInput) {
        exportEventsStatusGroupInput.value = "queue";
      }
      if (exportEventsSortByInput) {
        exportEventsSortByInput.value = "id";
      }
      if (exportEventsSortDirInput) {
        exportEventsSortDirInput.value = "asc";
      }
      await loadFireflyExports(true);
      if (activeExportId) {
        await openFireflyExport(activeExportId);
      }
      await loadQueueSummary().catch(() => {});
    } catch (error) {
      alert(error.message);
    } finally {
      startFireflyExportBtn.disabled = false;
    }
  });
}

if (stopFireflyExportBtn) {
  stopFireflyExportBtn.addEventListener("click", async () => {
    if (!activeJobId || !activeExportId) {
      alert("Select an export first.");
      return;
    }
    stopFireflyExportBtn.disabled = true;
    try {
      await stopFireflyExport(activeJobId, activeExportId);
      await loadFireflyExports(false);
      await loadFireflyExportEvents(false);
      await loadQueueSummary().catch(() => {});
    } catch (error) {
      alert(error.message);
    } finally {
      stopFireflyExportBtn.disabled = false;
    }
  });
}

if (deleteFireflyExportBtn) {
  deleteFireflyExportBtn.addEventListener("click", async () => {
    if (!activeJobId) {
      alert("Select a merge job first.");
      return;
    }
    const statusGroup = String((exportEventsStatusGroupInput && exportEventsStatusGroupInput.value) || "all");
    const label =
      statusGroup === "queue"
        ? "queued/running"
        : statusGroup === "completed"
          ? "completed/failed"
          : "all";
    const approved = window.confirm(`Delete ${label} export queue(s) for job ${activeJobId}?`);
    if (!approved) return;
    deleteFireflyExportBtn.disabled = true;
    try {
      const result = await deleteFireflyExports(activeJobId, statusGroup);
      activeExportId = "";
      activeExportEventId = 0;
      await loadFireflyExports(true);
      await loadQueueSummary().catch(() => {});
      const deletedExports = Number(result.deleted_exports || 0);
      const deletedEvents = Number(result.deleted_events || 0);
      alert(`Deleted exports: ${deletedExports}. Deleted queue items: ${deletedEvents}.`);
    } catch (error) {
      alert(error.message);
    } finally {
      deleteFireflyExportBtn.disabled = false;
    }
  });
}

if (refreshExportStatusBtn) {
  refreshExportStatusBtn.addEventListener("click", async () => {
    try {
      await loadFireflyExports(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (refreshExportEventsBtn) {
  refreshExportEventsBtn.addEventListener("click", async () => {
    try {
      await loadFireflyExportEvents(true);
    } catch (error) {
      alert(error.message);
    }
  });
}

[exportEventsStatusGroupInput, exportEventsPageSizeInput, exportEventsSortByInput, exportEventsSortDirInput]
  .filter(Boolean)
  .forEach((el) => {
    el.addEventListener("change", async () => {
      exportEventsPage = 1;
      saveFormPreferences();
      try {
        await loadFireflyExportEvents(true);
      } catch (error) {
        alert(error.message);
      }
    });
  });

if (exportEventsPageFirstBtn) {
  exportEventsPageFirstBtn.addEventListener("click", async () => {
    if (exportEventsPage <= 1) return;
    exportEventsPage = 1;
    try {
      await loadFireflyExportEvents(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (exportEventsPagePrevBtn) {
  exportEventsPagePrevBtn.addEventListener("click", async () => {
    if (exportEventsPage <= 1) return;
    exportEventsPage -= 1;
    try {
      await loadFireflyExportEvents(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (exportEventsPageNextBtn) {
  exportEventsPageNextBtn.addEventListener("click", async () => {
    const totalPages = getExportEventsTotalPages();
    if (exportEventsPage >= totalPages) return;
    exportEventsPage += 1;
    try {
      await loadFireflyExportEvents(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (exportEventsPageLastBtn) {
  exportEventsPageLastBtn.addEventListener("click", async () => {
    const totalPages = getExportEventsTotalPages();
    if (exportEventsPage >= totalPages) return;
    exportEventsPage = totalPages;
    try {
      await loadFireflyExportEvents(false);
    } catch (error) {
      alert(error.message);
    }
  });
}

if (ollamaJobFilterInput) {
  ollamaJobFilterInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      refreshOllamaEventsBtn.click();
    }
  });
  ollamaJobFilterInput.addEventListener("change", () => {
    if (refreshOllamaEventsBtn) {
      refreshOllamaEventsBtn.click();
    }
  });
}

[ollamaStatusGroupInput, ollamaPageSizeInput, ollamaSortByInput, ollamaSortDirInput]
  .filter(Boolean)
  .forEach((el) => {
    el.addEventListener("change", async () => {
      if (el === ollamaStatusGroupInput && ollamaSortByInput && ollamaSortDirInput) {
        const token = String(ollamaStatusGroupInput.value || "all");
        if (token === "queue") {
          ollamaSortByInput.value = "id";
          ollamaSortDirInput.value = "asc";
        } else if (token === "completed") {
          ollamaSortByInput.value = "id";
          ollamaSortDirInput.value = "desc";
        }
      }
      ollamaPage = 1;
      saveFormPreferences();
      try {
        await loadOllamaEvents({ resetPage: true });
      } catch (error) {
        alert(error.message);
      }
    });
  });

txBody.addEventListener("change", async (event) => {
  const target = event.target;
  if (!target || !target.classList || !target.classList.contains("tx-category-select")) {
    return;
  }
  const rowIndex = Number(target.dataset.mergeRowIndex || 0);
  if (!activeJobId || !rowIndex) {
    return;
  }
  const value = String(target.value || "");
  try {
    await updateTransactionCategory(activeJobId, rowIndex, value);
  } catch (error) {
    alert(error.message);
  }
});

if (detailModalCloseBtn) {
  detailModalCloseBtn.addEventListener("click", () => {
    closeDetailModal();
  });
}

if (detailModalEl) {
  detailModalEl.addEventListener("click", (event) => {
    const target = event.target;
    if (target && target.dataset && target.dataset.closeModal === "1") {
      closeDetailModal();
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && detailModalEl && !detailModalEl.hidden) {
    closeDetailModal();
  }
});

mainTopTabs.forEach((btn) => {
  btn.addEventListener("click", () => activateMainTab(String(btn.dataset.mainTab || "merge-workspace")));
});

subTabButtons.forEach((btn) => {
  btn.addEventListener("click", () => activateSubTab(String(btn.dataset.subTab || "merge-form-panel")));
});

[dedupeScopeInput, noDedupInput, dedupeFirstOnlyInput, pushFireflyInput, overwriteCategoryCheckbox, autoExportAfterCategorizeInput, txDecisionFilter, txIncludeDroppedInput, txSortBy, txSortDir, dupSourceFileFilter, dupSortBy, dupSortDir, dupPageSizeInput, exportEventsStatusGroupInput, exportEventsPageSizeInput, exportEventsSortByInput, exportEventsSortDirInput]
  .filter(Boolean)
  .forEach((el) => {
    el.addEventListener("change", saveFormPreferences);
  });

async function restorePreviousSession() {
  restoreFormPreferences();
  startQueueSummaryPolling();
  await loadQueueSummary().catch(() => {});
  try {
    await loadJobHistory();
  } catch (error) {
    knownJobs = [];
    refreshActiveJobControls();
    if (activeJobMeta) {
      activeJobMeta.textContent = `Job history unavailable: ${String((error && error.message) || error || "unknown error")}`;
    }
  }

  const session = loadSessionState();
  const hashTab = mainTabFromHash(window.location.hash);
  const hashSubTab = subTabFromHash(window.location.hash);
  const mainTab = String(hashTab || session.mainTab || "merge-workspace");
  const subTab = String(hashSubTab || session.subTab || "merge-form-panel");
  activateMainTab(mainTab in mainWorkspaces ? mainTab : "merge-workspace", { syncHash: false });
  activateSubTab(subTab in subPanels ? subTab : "merge-form-panel");

  const previousJobId = String(session.activeJobId || "");
  if (!previousJobId) {
    if (getActiveMainTab() === "merge-workspace" && getActiveSubTab() === "ollama-panel") {
      await loadOllamaEvents();
    }
    return;
  }

  try {
    await openExistingJob(previousJobId, subTab in subPanels ? subTab : "job-panel");
  } catch (error) {
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch (storageError) {
      // ignore
    }
    resetActiveJobView();
  }

  if (getActiveMainTab() === "merge-workspace" && getActiveSubTab() === "ollama-panel") {
    await loadOllamaEvents();
  }
}

updateSelectedFilesHint();
restorePreviousSession().catch((error) => {
  console.error("Failed to restore previous session:", error);
  if (activeJobMeta) {
    activeJobMeta.textContent = `Initialization warning: ${String((error && error.message) || error || "unknown error")}`;
  }
});
