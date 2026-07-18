import { apiGet, jobIdFromShell } from "../api.js";
import { startPoll } from "../polling.js";
import { mountStepper } from "../stepper.js";
import { escapeHtml } from "../tables.js";

const jobIdEl = document.getElementById("job-id");
const jobStatusEl = document.getElementById("job-status");
const jobCreatedEl = document.getElementById("job-created");
const jobUpdatedEl = document.getElementById("job-updated");
const statsEl = document.getElementById("stats");
const artifactsEl = document.getElementById("artifacts");
const logsEl = document.getElementById("logs");
const jobMissingEl = document.getElementById("job-missing");

// Local port of app.js:1882 (renderStatusBadge), matching the ".status-chip"
// convention already used by pages/jobs.js's renderStatusChip -- the legacy
// ".status-badge" class it used has no rule in styles.css.
function renderStatusChip(status) {
  const s = String(status || "unknown").toLowerCase();
  return `<span class="status-chip ${escapeHtml(s)}">${escapeHtml(s)}</span>`;
}

/**
 * Extracted from app.js:611 (renderJob). GLOBAL -> LOCAL: `activeJobId`
 * tracking, `saveSessionState()`, `refreshActiveJobControls()`,
 * `updateWorkflowStepper()` (superseded by stepper.js's mountStepper),
 * `applyDuplicateReviewGateToActions()`, `duplicateReviewStatus` bookkeeping,
 * and the `exportSummaryEl` write are all dropped -- they belong to the SPA's
 * cross-tab session state and duplicate-review gate, none of which exists on
 * this page. The stats block keeps only the two counters (`merged_rows`,
 * `duplicate_rows`) that don't depend on the dropped `duplicateReviewStatus`
 * global; the duplicate-review/global-duplicates/fingerprint lines are
 * dropped since their source values no longer exist here.
 */
function renderJob(job) {
  if (!job) {
    return;
  }

  if (jobIdEl) jobIdEl.textContent = job.id || "";
  if (jobStatusEl) jobStatusEl.innerHTML = renderStatusChip(job.status);
  if (jobCreatedEl) jobCreatedEl.textContent = job.created_at || "-";
  if (jobUpdatedEl) jobUpdatedEl.textContent = job.updated_at || "-";

  const stats = job.stats || {};
  if (statsEl) {
    statsEl.innerHTML = `
      <h3>Stats</h3>
      <ul>
        <li>Merged rows: ${escapeHtml(String(stats.merged_rows ?? 0))}</li>
        <li>Duplicate rows: ${escapeHtml(String(stats.duplicate_rows ?? 0))}</li>
      </ul>
    `;
  }

  const urls = job.artifact_urls || {};
  const links = Object.entries(urls)
    .map(([key, url]) => `<li><a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(key)}</a></li>`)
    .join("");
  if (artifactsEl) artifactsEl.innerHTML = `<h3>Artifacts</h3><ul>${links || "<li>None</li>"}</ul>`;

  if (logsEl) {
    logsEl.textContent = job.logs || "";
    logsEl.scrollTop = logsEl.scrollHeight;
  }
}

const jobId = jobIdFromShell();
mountStepper(jobId);

// `stop` is referenced inside the poll callback (to halt polling on 404 or
// terminal status) before `startPoll` has returned it. startPoll's first
// tick only synchronously reaches the point of calling `fn`, and `fn` itself
// suspends at its first `await` (the `apiGet` fetch) before ever reaching a
// `stop()` call -- so by the time `stop()` can actually run, `startPoll` has
// long since returned and the `let stop` below has been assigned. Declaring
// it with `let` up front (rather than `const stop = startPoll(...)`) makes
// that ordering explicit instead of relying on it silently.
let stop;
stop = startPoll(async () => {
  let job;
  try {
    job = await apiGet(`/api/jobs/${jobId}`);
  } catch {
    if (jobMissingEl) jobMissingEl.hidden = false;
    stop();
    return;
  }
  renderJob(job);
  if (job.status === "completed" || job.status === "failed") stop();
}, 3000);
