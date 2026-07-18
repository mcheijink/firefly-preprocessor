import { apiGet, apiSend } from "../api.js";
import { escapeHtml, TableColumnManager } from "../tables.js";

const historyBody = document.getElementById("history-body-tab");
const refreshBtn = document.getElementById("refresh-history-tab");
const columnsBtn = document.getElementById("history-columns-btn");

let knownJobs = [];
let historySortKey = "created";
let historySortDir = "desc";

function renderStatusChip(status) {
  const s = String(status || "unknown").toLowerCase();
  return `<span class="status-chip ${escapeHtml(s)}">${escapeHtml(s)}</span>`;
}

/**
 * Extracted from app.js:2470 (renderHistoryRows). GLOBAL -> PARAMETER: the
 * `activeJobId` comparison (SPA "active job" highlighting) is dropped along
 * with the rest of the SPA session state; the Open button now always reads
 * "Open" and simply navigates to /jobs/{id}. `targetBody` global param
 * dropped in favor of the module-level `historyBody` lookup.
 */
function renderHistoryRows(jobs) {
  if (!historyBody) {
    return;
  }
  if (!jobs.length) {
    historyBody.innerHTML = `<tr><td colspan="6">No jobs yet.</td></tr>`;
    return;
  }

  historyBody.innerHTML = jobs
    .map((job) => {
      const stats = job.stats || {};
      const message = job.error ? escapeHtml(job.error) : escapeHtml(job.message || "");
      return `
        <tr>
          <td data-col="job_id" data-label="Job ID"><code>${escapeHtml(job.id)}</code></td>
          <td data-col="status" data-label="Status">${renderStatusChip(job.status)}</td>
          <td data-col="created" data-label="Created">${escapeHtml(job.created_at || "")}</td>
          <td data-col="merged" data-label="Merged">${escapeHtml(String(stats.merged_rows ?? 0))}</td>
          <td data-col="duplicates" data-label="Duplicates">${escapeHtml(String(stats.duplicate_rows ?? 0))}</td>
          <td data-col="actions" data-label="Actions" class="actions-cell">
            <div class="small-controls">
              <button type="button" class="open-job" data-job-id="${escapeHtml(job.id)}">Open</button>
              <button type="button" class="delete-job" data-job-id="${escapeHtml(job.id)}">Delete</button>
              ${message ? `<span class="hint">${message}</span>` : ""}
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  bindHistoryRowHandlers();
}

/**
 * Extracted from app.js:2504 (bindHistoryOpenHandlers) + app.js:727
 * (deleteJobRequest, inlined via apiSend). GLOBAL -> LOCAL: "Open" no longer
 * calls openExistingJob(jobId, "job-panel") (SPA tab activation); it
 * navigates to the job's own page instead. Delete keeps its confirm dialog,
 * using window.confirm since the MPA templates carry no #confirm-modal
 * markup (showConfirm() in app.js already falls back to window.confirm in
 * that case).
 */
function bindHistoryRowHandlers() {
  if (!historyBody) {
    return;
  }
  historyBody.querySelectorAll(".open-job").forEach((btn) => {
    btn.addEventListener("click", () => {
      const jobId = String(btn.dataset.jobId || "");
      if (!jobId) {
        return;
      }
      window.location.href = `/jobs/${jobId}`;
    });
  });
  historyBody.querySelectorAll(".delete-job").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const jobId = String(btn.dataset.jobId || "");
      if (!jobId) {
        return;
      }
      const approved = window.confirm(`Delete job ${jobId}? This removes artifacts, logs and queue records.`);
      if (!approved) {
        return;
      }
      btn.disabled = true;
      try {
        await apiSend(`/api/jobs/${jobId}`, "DELETE");
        await loadJobs();
      } catch (error) {
        window.alert(error.message);
        btn.disabled = false;
      }
    });
  });
}

// Local port of app.js:4207 (_sortJobs), used by the TableColumnManager's
// client-side sort below.
function sortJobs(jobs, key, dir) {
  return [...jobs].sort((a, b) => {
    let av;
    let bv;
    if (key === "id") {
      av = String(a.id || "");
      bv = String(b.id || "");
    } else if (key === "status") {
      av = String(a.status || "");
      bv = String(b.status || "");
    } else if (key === "created") {
      av = String(a.created_at || "");
      bv = String(b.created_at || "");
    } else if (key === "merged") {
      av = Number((a.stats || {}).merged_rows ?? 0);
      bv = Number((b.stats || {}).merged_rows ?? 0);
    } else if (key === "duplicates") {
      av = Number((a.stats || {}).duplicate_rows ?? 0);
      bv = Number((b.stats || {}).duplicate_rows ?? 0);
    } else {
      av = String(a.id || "");
      bv = String(b.id || "");
    }
    const cmp = typeof av === "number" ? av - bv : av.localeCompare(bv);
    return dir === "asc" ? cmp : -cmp;
  });
}

const tcmHistory = new TableColumnManager({
  tableId: "history-table-tab",
  columns: [
    { key: "job_id", label: "Job ID", sortKey: "id", alwaysVisible: true },
    { key: "status", label: "Status", sortKey: "status" },
    { key: "created", label: "Created", sortKey: "created" },
    { key: "merged", label: "Merged", sortKey: "merged" },
    { key: "duplicates", label: "Duplicates", sortKey: "duplicates" },
    { key: "actions", label: "Actions", alwaysVisible: true },
  ],
  onClientSort: (sortKey, dir) => {
    historySortKey = sortKey;
    historySortDir = dir;
    renderHistoryRows(sortJobs(knownJobs, sortKey, dir));
    tcmHistory.applyToTable();
  },
});
tcmHistory.bindHeaderEvents();
tcmHistory._clientSortKey = historySortKey;
tcmHistory._clientSortDir = historySortDir;

if (columnsBtn) {
  columnsBtn.addEventListener("click", () => tcmHistory.openPicker(columnsBtn));
}

// Extracted from app.js:719 (fetchJobs) + app.js:2542 (loadJobHistory),
// rewired onto apiGet.
async function loadJobs() {
  try {
    const data = await apiGet("/api/jobs?limit=500");
    knownJobs = data.jobs || [];
    renderHistoryRows(sortJobs(knownJobs, historySortKey, historySortDir));
    tcmHistory.applyToTable();
  } catch (error) {
    if (historyBody) {
      historyBody.innerHTML = `<tr><td colspan="6">Failed to load jobs: ${escapeHtml(error.message)}</td></tr>`;
    }
  }
}

if (refreshBtn) {
  refreshBtn.addEventListener("click", () => loadJobs());
}

loadJobs();
