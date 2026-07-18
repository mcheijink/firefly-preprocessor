import { apiUpload, apiGet } from "../api.js";
import { escapeHtml } from "../tables.js";

const form = document.getElementById("job-form");
const submitButton = document.getElementById("submit");
const filesInput = document.getElementById("files");
const csvDropZone = document.getElementById("csv-drop-zone");
const filesSelectedHint = document.getElementById("files-selected-hint");

/**
 * Verbatim from app.js:231 (updateSelectedFilesHint). No SPA globals beyond
 * the two DOM lookups above (filesSelectedHint, filesInput), both re-declared
 * locally in this module.
 */
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

function readCheckbox(name) {
  const input = document.getElementById(name);
  return !!(input && input.checked);
}

// Drop-zone + file-input wiring, extracted from app.js:3150-3184.
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

async function submitMerge(formData) {
  const data = await apiUpload("/api/jobs", formData);
  window.location.href = `/jobs/${data.job_id}`;
}

// Merge-form submit handler, rewired from app.js:3186-3244 (FormData / fetch
// plumbing replaced with apiUpload; dedupe_scope and the merged-import-CSV
// flow dropped along with all SPA tab/session bookkeeping).
if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!filesInput || !filesInput.files.length) {
      window.alert("Select at least one bank statement file (CSV or MT940).");
      return;
    }

    submitButton.disabled = true;

    const formData = new FormData();
    for (const file of filesInput.files) {
      formData.append("files", file);
    }
    formData.append("no_dedup", String(readCheckbox("no_dedup")));
    formData.append("dedupe_first_only", String(readCheckbox("dedupe_first_only")));
    formData.append("push_firefly", String(readCheckbox("push_firefly")));

    try {
      await submitMerge(formData);
    } catch (error) {
      window.alert(error.message);
      submitButton.disabled = false;
    }
  });
}

// Recent-jobs strip. Field names (`id`, `created_at`, `status`, `stats`) match
// the real store.list_jobs() output (firefly_web/store.py) — note the list
// item key is `id`, not `job_id` as in the brief's illustrative snippet.
async function loadRecentJobs() {
  const list = document.getElementById("recent-jobs-list");
  const empty = document.getElementById("recent-jobs-empty");
  if (!list || !empty) {
    return;
  }
  try {
    const data = await apiGet("/api/jobs?limit=3");
    const jobs = data.jobs || [];
    empty.hidden = jobs.length > 0;
    list.innerHTML = jobs
      .map(
        (job) => `
      <div class="recent-job-row">
        <a href="/jobs/${escapeHtml(job.id)}" class="mono">${escapeHtml(String(job.id).slice(0, 12))}</a>
        <span class="status-chip ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
        <span class="hint">${escapeHtml(job.created_at || "")}</span>
        <span class="hint">${escapeHtml(String(job.stats?.merged_rows ?? "-"))} merged</span>
      </div>`
      )
      .join("");
  } catch (error) {
    empty.hidden = false;
    empty.textContent = `Unable to load recent jobs: ${error.message}`;
  }
}

loadRecentJobs();
