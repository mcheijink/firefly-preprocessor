import { apiGet, apiSend, jobIdFromShell } from "../api.js";
import { startPoll } from "../polling.js";
import { mountStepper } from "../stepper.js";
import { escapeHtml, amountClass, renderPageButtonsHtml, TableColumnManager } from "../tables.js";

const jobId = jobIdFromShell();
mountStepper(jobId);

// ── DOM lookups ──────────────────────────────────────────────────────────
const exportContent = document.getElementById("export-content");
const startFireflyExportBtn = document.getElementById("start-firefly-export");
const stopFireflyExportBtn = document.getElementById("stop-firefly-export");
const deleteFireflyExportBtn = document.getElementById("delete-firefly-export");
const refreshExportStatusBtn = document.getElementById("refresh-export-status");
const exportsColumnsBtn = document.getElementById("exports-columns-btn");
const exportSummaryEl = document.getElementById("export-summary");
const exportBody = document.getElementById("exports-body");
const exportLogsEl = document.getElementById("export-logs");

const refreshExportEventsBtn = document.getElementById("refresh-export-events");
const exportEventsColumnsBtn = document.getElementById("export-events-columns-btn");
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

// ── Module-level state. Was scattered across SPA globals in app.js
// (activeExportId, activeExportEventId, exportEventsById, exportEventsTotal,
// exportEventsPage, exportEventsPageSize, exportPollTimer, _knownExports,
// _exportsSortKey/_exportsSortDir, duplicateReviewStatus); this page owns
// them directly since there is no cross-tab/session state to share them
// with. ────────────────────────────────────────────────────────────────
let activeExportId = "";
let activeExportEventId = 0;
const exportEventsById = new Map();
let exportEventsTotal = 0;
let exportEventsPage = 1;
let exportEventsPageSize = Math.max(1, Number((exportEventsPageSizeInput && exportEventsPageSizeInput.value) || 20));
let stopExportPoll = null;

let knownExports = [];
let exportsSortKey = "created";
let exportsSortDir = "desc";

let duplicateReviewStatus = {
  required: false,
  confirmed: true,
  can_proceed: true,
  pending_duplicates: 0,
  initial_duplicates: 0,
  restored_rows_total: 0,
};
let reviewGateBannerEl = null;

// ── tables.js column managers ───────────────────────────────────────────
function sortExports(items, key, dir) {
  return [...items].sort((a, b) => {
    let av;
    let bv;
    const sa = a.stats || {};
    const sb = b.stats || {};
    if (key === "id") { av = String(a.id || ""); bv = String(b.id || ""); }
    else if (key === "status") { av = String(a.status || ""); bv = String(b.status || ""); }
    else if (key === "created") { av = String(a.created_at || ""); bv = String(b.created_at || ""); }
    else if (key === "updated") { av = String(a.updated_at || ""); bv = String(b.updated_at || ""); }
    else if (key === "rows") { av = Number(sa.exported_rows ?? 0); bv = Number(sb.exported_rows ?? 0); }
    else if (key === "batches") { av = Number(sa.batches ?? 0); bv = Number(sb.batches ?? 0); }
    else { av = String(a.id || ""); bv = String(b.id || ""); }
    const cmp = typeof av === "number" ? av - bv : av.localeCompare(bv);
    return dir === "asc" ? cmp : -cmp;
  });
}

const tcmExports = new TableColumnManager({
  tableId: "exports-table",
  columns: [
    { key: "export_id", label: "Export ID", sortKey: "id" },
    { key: "status", label: "Status", sortKey: "status" },
    { key: "created", label: "Created", sortKey: "created" },
    { key: "updated", label: "Updated", sortKey: "updated" },
    { key: "rows", label: "Rows", sortKey: "rows" },
    { key: "batches", label: "Batches", sortKey: "batches" },
    { key: "message", label: "Message" },
    { key: "actions", label: "Actions", alwaysVisible: true },
  ],
  onClientSort: (sortKey, dir) => {
    exportsSortKey = sortKey;
    exportsSortDir = dir;
    const sorted = sortExports(knownExports, sortKey, dir);
    renderFireflyExportRows(sorted);
    tcmExports.applyToTable();
  },
});
tcmExports.bindHeaderEvents();
tcmExports._clientSortKey = exportsSortKey;
tcmExports._clientSortDir = exportsSortDir;
if (exportsColumnsBtn) {
  exportsColumnsBtn.addEventListener("click", () => tcmExports.openPicker(exportsColumnsBtn));
}

const tcmExportEvents = new TableColumnManager({
  tableId: "export-events-table",
  columns: [
    { key: "id", label: "ID", sortKey: "id" },
    { key: "status", label: "Status", sortKey: "status" },
    { key: "date", label: "Date", sortKey: "date" },
    { key: "amount", label: "Amount", sortKey: "amount" },
    { key: "category", label: "Category", sortKey: "category" },
    { key: "description", label: "Description", sortKey: "description" },
    { key: "source_account", label: "Source Account", sortKey: "source_account", defaultHidden: true },
    { key: "destination_account", label: "Destination Account", sortKey: "destination_account", defaultHidden: true },
    { key: "batch", label: "Batch", sortKey: "batch_number" },
    { key: "actions", label: "Actions", alwaysVisible: true },
  ],
  sortByEl: exportEventsSortByInput,
  sortDirEl: exportEventsSortDirInput,
  onRedraw: () => loadFireflyExportEvents(false).catch((error) => window.alert(error.message)),
});
tcmExportEvents.bindHeaderEvents();
if (exportEventsColumnsBtn) {
  exportEventsColumnsBtn.addEventListener("click", () => tcmExportEvents.openPicker(exportEventsColumnsBtn));
}

// ── API layer, extracted from app.js (fetchDuplicateReviewStatus ~826,
// startFireflyExport ~879, retryFailedFireflyExport ~892,
// stopFireflyExport ~905, deleteFireflyExport ~916, deleteFireflyExports
// ~925, deleteFireflyExportEvents ~936, fetchFireflyExports ~949,
// fetchFireflyExport ~958, fetchFireflyExportEvents ~967,
// fetchFireflyExportEvent ~989, deleteFireflyExportEvent ~998). Rewired
// onto api.js's apiGet/apiSend, which already extract `detail` from error
// responses, so the manual `response.ok`/`payload.detail` checks are
// dropped. ──
async function fetchDuplicateReviewStatus(id) {
  return apiGet(`/api/jobs/${id}/duplicates/review/status`);
}

async function startFireflyExport(id) {
  return apiSend(`/api/jobs/${id}/exports/firefly`, "POST", { force: false });
}

async function retryFailedFireflyExport(id, exportId) {
  return apiSend(`/api/jobs/${id}/exports/firefly/${exportId}/retry-failed`, "POST", { force: false });
}

async function stopFireflyExport(id, exportId) {
  return apiSend(`/api/jobs/${id}/exports/firefly/${exportId}/stop`, "POST");
}

async function deleteFireflyExport(id, exportId) {
  return apiSend(`/api/jobs/${id}/exports/firefly/${exportId}`, "DELETE");
}

async function deleteFireflyExports(id, statusGroup = "all") {
  const params = new URLSearchParams();
  params.set("status_group", String(statusGroup || "all"));
  return apiSend(`/api/jobs/${id}/exports/firefly?${params.toString()}`, "DELETE");
}

async function fetchFireflyExports(id, limit = 100) {
  return apiGet(`/api/jobs/${id}/exports/firefly?limit=${limit}`);
}

async function fetchFireflyExport(id, exportId) {
  return apiGet(`/api/jobs/${id}/exports/firefly/${exportId}`);
}

async function fetchFireflyExportEvents(id, exportId, {
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
  return apiGet(`/api/jobs/${id}/exports/firefly/${exportId}/events?${params.toString()}`);
}

async function fetchFireflyExportEvent(id, eventId) {
  return apiGet(`/api/jobs/${id}/exports/firefly/events/${Number(eventId || 0)}`);
}

async function deleteFireflyExportEvent(id, eventId) {
  return apiSend(`/api/jobs/${id}/exports/firefly/events/${Number(eventId || 0)}`, "DELETE");
}

// Ported for parity with app.js:936 (deleteFireflyExportEvents, bulk delete
// of an export's queue items by status_group). Not wired to any control in
// either the legacy app.js bindings or export.html -- it was already dead
// code pre-migration (deleteFireflyExportBtn calls deleteFireflyExports,
// the whole-job bulk delete, not this per-export one). Kept available for a
// future "clear queue for this export" control.
// eslint-disable-next-line no-unused-vars
async function deleteFireflyExportEvents(id, exportId, statusGroup = "all") {
  const params = new URLSearchParams();
  params.set("status_group", String(statusGroup || "all"));
  return apiSend(`/api/jobs/${id}/exports/firefly/${exportId}/events?${params.toString()}`, "DELETE");
}

// ── Duplicate-review gate (same pattern as pages/transactions.js's
// renderReviewGateBanner -- see task-12/task-9 reports). Instead of the
// SPA's applyDuplicateReviewGateToActions (app.js:1461, which also gated on
// activeJobStatus === "completed"), this page relies on the backend's own
// 400 ("Merge job must be completed before export.") for the job-status
// check, and only mirrors the duplicate-review portion here -- the backend
// still 409s as a backstop either way. ──
function renderReviewGateBanner() {
  const pending = Number(duplicateReviewStatus.pending_duplicates || 0);
  const blocked = !duplicateReviewStatus.can_proceed;

  if (startFireflyExportBtn) startFireflyExportBtn.disabled = blocked;

  if (!exportContent) {
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
    reviewGateBannerEl.id = "export-review-gate-banner";
    const tableWrap = exportContent.querySelector(".table-wrap");
    if (tableWrap) {
      tableWrap.before(reviewGateBannerEl);
    } else {
      exportContent.prepend(reviewGateBannerEl);
    }
  }
  reviewGateBannerEl.innerHTML =
    `Review ${pending} flagged duplicates before exporting. ` +
    `<a href="/jobs/${escapeHtml(jobId)}/review">Go to review</a>`;
}

async function refreshDuplicateReviewGate() {
  if (!jobId) {
    return;
  }
  duplicateReviewStatus = await fetchDuplicateReviewStatus(jobId);
  renderReviewGateBanner();
}

// Re-checked immediately before starting/retrying an export (mirrors
// app.js's ensureDuplicateReviewReadyForProcessing ~2397, and
// pages/transactions.js's ensureDuplicateReviewReady); the backend also
// 409s as a backstop, but re-fetching here keeps the banner/button state in
// sync and gives the user a clear error instead of a raw HTTP failure.
async function ensureDuplicateReviewReady() {
  await refreshDuplicateReviewGate();
  if (duplicateReviewStatus.can_proceed) {
    return;
  }
  const pending = Number(duplicateReviewStatus.pending_duplicates || 0);
  throw new Error(
    `Duplicate review required before export. Pending suspected duplicates: ${pending}. ` +
    `Go to /jobs/${jobId}/review to resolve.`
  );
}

// ── Queue progress metrics, extracted from app.js's buildQueueProgressModel
// (~2385 area helpers shared by Ollama + export queues) / updateExportMetrics
// (~2698). Not exported from tables.js (see pages/transactions.js, which
// carries its own private copy for the Ollama queue); duplicated here
// rather than introducing a new shared module for two call sites. ──
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

function renderStatusChip(status) {
  const s = String(status || "unknown").toLowerCase();
  return `<span class="status-chip ${escapeHtml(s)}">${escapeHtml(s)}</span>`;
}

// ── Export queue events (audit log) table, extracted from app.js
// (selectExportEvent ~2710, renderExportEvents ~2728, getExportEventsTotalPages
// ~2799, updateExportEventsSummary ~2803, updateExportEventsPagination
// ~2814, loadFireflyExportEvents ~2842). GLOBAL -> LOCAL: showToast ->
// window.alert, showConfirm -> window.confirm; selectExportEvent's
// openDetailModal() call degrades to window.alert (no detail-modal element
// on this page, same gap noted in task-9/11 reports for the transactions/
// review pages). ──
async function selectExportEvent(eventId) {
  const event = exportEventsById.get(Number(eventId || 0));
  if (!event || !jobId) {
    return;
  }
  activeExportEventId = Number(event.id || 0);
  if (exportEventsBody) {
    exportEventsBody.querySelectorAll("tr[data-event-id]").forEach((row) => {
      row.classList.toggle("selected", Number(row.dataset.eventId || 0) === activeExportEventId);
    });
  }
  try {
    const detail = await fetchFireflyExportEvent(jobId, activeExportEventId);
    exportEventsById.set(activeExportEventId, detail);
    const keys = Object.keys(detail || {}).sort((a, b) => a.localeCompare(b));
    const lines = keys.map((key) => {
      const raw = detail[key];
      const value = raw && typeof raw === "object" ? JSON.stringify(raw) : String(raw ?? "");
      return `${key}: ${value}`;
    });
    window.alert([`Export Event ${activeExportEventId}`, ...lines].join("\n"));
  } catch (error) {
    window.alert(error.message);
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
          <td data-col="id" data-label="ID"><code>${escapeHtml(String(id))}</code></td>
          <td data-col="status" data-label="Status">${renderStatusChip(event.status)}</td>
          <td data-col="date" data-label="Date">${escapeHtml(event.date || "")}</td>
          <td data-col="amount" data-label="Amount" class="num${amountClass(event.amount)}">${escapeHtml(event.amount || "")}</td>
          <td data-col="category" data-label="Category">${escapeHtml(event.category || "")}</td>
          <td data-col="description" data-label="Description">${escapeHtml(event.description || "")}</td>
          <td data-col="source_account" data-label="Source Account">${escapeHtml(event.source_account || "")}</td>
          <td data-col="destination_account" data-label="Destination Account">${escapeHtml(event.destination_account || "")}</td>
          <td data-col="batch" data-label="Batch">${escapeHtml(String(event.batch_number || 0))}</td>
          <td data-col="actions" data-label="Actions" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="export-event-open secondary-btn" data-event-id="${id}">Open</button>
              <button type="button" class="export-event-delete danger-btn" data-event-id="${id}" ${String(event.status || "") === "running" ? "disabled" : ""}>Delete</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  tcmExportEvents.applyToTable();
  exportEventsBody.querySelectorAll(".export-event-open").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      selectExportEvent(Number(btn.dataset.eventId || 0));
    });
  });
  exportEventsBody.querySelectorAll(".export-event-delete").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const eventId = Number(btn.dataset.eventId || 0);
      if (!eventId || !jobId) return;
      if (!window.confirm(`Delete export queue item ${eventId}?`)) return;
      try {
        await deleteFireflyExportEvent(jobId, eventId);
        await loadFireflyExportEvents(false);
      } catch (error) {
        window.alert(error.message);
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
        window.alert(error.message);
      }
    });
  });
}

function updateExportEventsSummary() {
  if (exportEventsSummaryEl) {
    const totalPages = getExportEventsTotalPages();
    const start = exportEventsTotal ? (exportEventsPage - 1) * exportEventsPageSize + 1 : 0;
    const end = Math.min(exportEventsPage * exportEventsPageSize, exportEventsTotal);
    const exportText = activeExportId ? ` for export ${activeExportId}` : "";
    exportEventsSummaryEl.textContent = `Rows ${start}-${end} of ${exportEventsTotal}. Page ${exportEventsPage}/${totalPages}${exportText}.`;
  }
  updateExportEventsPagination();
}

async function loadFireflyExportEvents(resetPage = false) {
  if (!jobId || !activeExportId) {
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
  const payload = await fetchFireflyExportEvents(jobId, activeExportId, {
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

// ── Exports table + detail + polling, extracted from app.js
// (renderFireflyExportRows ~2878, renderFireflyExportDetail ~2981,
// startExportPolling ~3002, openFireflyExport ~3022, loadFireflyExports
// ~3049). GLOBAL -> LOCAL: showToast -> window.alert, showConfirm ->
// window.confirm; startExportPolling/stopExportPolling reworked onto
// polling.js's startPoll (this page has no cross-tab visibility gating, so
// it just polls at the same 2s cadence while an export is active and stops
// once the export reaches a terminal state or a different export opens). ──
function renderFireflyExportRows(items) {
  knownExports = items;
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
          <td data-col="export_id" data-label="Export ID"><code>${escapeHtml(exportId)}</code></td>
          <td data-col="status" data-label="Status">${renderStatusChip(item.status)}</td>
          <td data-col="created" data-label="Created">${escapeHtml(item.created_at || "")}</td>
          <td data-col="updated" data-label="Updated">${escapeHtml(item.updated_at || "")}</td>
          <td data-col="rows" data-label="Rows">${escapeHtml(String(stats.exported_rows ?? 0))}</td>
          <td data-col="batches" data-label="Batches">${escapeHtml(String(stats.batches ?? 0))}</td>
          <td data-col="message" data-label="Message">${escapeHtml(message)}</td>
          <td data-col="actions" data-label="Actions" class="actions-cell">
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

  tcmExports.applyToTable();
  exportBody.querySelectorAll(".open-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const exportId = String(btn.dataset.exportId || "");
      if (!exportId) return;
      try {
        await openFireflyExport(exportId);
      } catch (error) {
        window.alert(error.message);
      }
    });
  });
  exportBody.querySelectorAll(".retry-failed-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const sourceExportId = String(btn.dataset.exportId || "");
      if (!sourceExportId || !jobId) {
        return;
      }
      btn.disabled = true;
      try {
        await ensureDuplicateReviewReady();
        const payload = await retryFailedFireflyExport(jobId, sourceExportId);
        const newExportId = String(payload.export_id || "");
        await loadFireflyExports(true);
        if (newExportId) {
          await openFireflyExport(newExportId);
        }
      } catch (error) {
        window.alert(error.message);
      } finally {
        btn.disabled = false;
      }
    });
  });
  exportBody.querySelectorAll(".delete-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const targetExportId = String(btn.dataset.exportId || "");
      if (!targetExportId || !jobId) {
        return;
      }
      if (!window.confirm(`Delete export queue ${targetExportId}?`)) {
        return;
      }
      btn.disabled = true;
      try {
        await deleteFireflyExport(jobId, targetExportId);
        if (activeExportId === targetExportId) {
          activeExportId = "";
          activeExportEventId = 0;
        }
        await loadFireflyExports(true);
      } catch (error) {
        window.alert(error.message);
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

function stopExportPolling() {
  if (stopExportPoll) {
    stopExportPoll();
    stopExportPoll = null;
  }
}

function startExportPolling(exportId) {
  stopExportPolling();
  if (!jobId || !exportId) {
    return;
  }
  stopExportPoll = startPoll(async () => {
    const item = await fetchFireflyExport(jobId, exportId);
    renderFireflyExportDetail(item);
    await loadFireflyExportEvents(false);
    if (item.status === "completed" || item.status === "failed") {
      stopExportPolling();
      await loadFireflyExports(false);
    }
  }, 2000);
}

async function openFireflyExport(exportId) {
  if (!jobId || !exportId) {
    return;
  }
  activeExportId = String(exportId);
  if (stopFireflyExportBtn) stopFireflyExportBtn.disabled = false;
  if (deleteFireflyExportBtn) deleteFireflyExportBtn.disabled = false;
  activeExportEventId = 0;
  exportEventsPage = 1;
  const item = await fetchFireflyExport(jobId, activeExportId);
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
  if (!jobId) {
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
  const payload = await fetchFireflyExports(jobId, 100);
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

// ── Event bindings, extracted from app.js:3800-3970. GLOBAL -> LOCAL:
// showToast -> window.alert, showConfirm -> window.confirm. The Start
// Export handler additionally calls ensureDuplicateReviewReady() first
// (mirrors pages/transactions.js's runCategorization), which the SPA
// handled via applyDuplicateReviewGateToActions disabling the button
// instead of an inline pre-flight check. ──
if (startFireflyExportBtn) {
  startFireflyExportBtn.addEventListener("click", async () => {
    if (!jobId) {
      window.alert("No job selected.");
      return;
    }
    startFireflyExportBtn.disabled = true;
    try {
      await ensureDuplicateReviewReady();
      const payload = await startFireflyExport(jobId);
      activeExportId = String(payload.export_id || "");
      await loadFireflyExports(true);
      if (activeExportId) {
        await openFireflyExport(activeExportId);
      }
    } catch (error) {
      window.alert(error.message);
    } finally {
      startFireflyExportBtn.disabled = !!(duplicateReviewStatus && !duplicateReviewStatus.can_proceed);
    }
  });
}

if (stopFireflyExportBtn) {
  stopFireflyExportBtn.addEventListener("click", async () => {
    if (!jobId || !activeExportId) {
      return;
    }
    stopFireflyExportBtn.disabled = true;
    try {
      await stopFireflyExport(jobId, activeExportId);
      await loadFireflyExports(false);
      await loadFireflyExportEvents(false);
    } catch (error) {
      window.alert(error.message);
    } finally {
      stopFireflyExportBtn.disabled = false;
    }
  });
}

if (deleteFireflyExportBtn) {
  deleteFireflyExportBtn.addEventListener("click", async () => {
    if (!jobId) {
      return;
    }
    if (!window.confirm("Delete all export queues for this job?")) {
      return;
    }
    deleteFireflyExportBtn.disabled = true;
    try {
      const result = await deleteFireflyExports(jobId, "all");
      activeExportId = "";
      activeExportEventId = 0;
      await loadFireflyExports(true);
      const deletedExports = Number(result.deleted_exports || 0);
      const deletedEvents = Number(result.deleted_events || 0);
      window.alert(`Deleted exports: ${deletedExports}. Deleted queue items: ${deletedEvents}.`);
    } catch (error) {
      window.alert(error.message);
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
      window.alert(error.message);
    }
  });
}

if (refreshExportEventsBtn) {
  refreshExportEventsBtn.addEventListener("click", async () => {
    try {
      await loadFireflyExportEvents(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

[exportEventsStatusGroupInput, exportEventsPageSizeInput, exportEventsSortByInput, exportEventsSortDirInput]
  .filter(Boolean)
  .forEach((el) => {
    el.addEventListener("change", async () => {
      try {
        await loadFireflyExportEvents(true);
      } catch (error) {
        window.alert(error.message);
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
      window.alert(error.message);
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
      window.alert(error.message);
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
      window.alert(error.message);
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
      window.alert(error.message);
    }
  });
}

// ── Initial load ─────────────────────────────────────────────────────────
async function initExportPage() {
  if (!jobId) {
    return;
  }
  try {
    await refreshDuplicateReviewGate();
  } catch (error) {
    window.alert(error.message);
  }
  try {
    await loadFireflyExports(true);
  } catch (error) {
    if (exportSummaryEl) {
      exportSummaryEl.textContent = error.message;
    } else {
      window.alert(error.message);
    }
  }
}

initExportPage();
