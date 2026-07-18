import { apiGet } from "./api.js";
import { startPoll } from "./polling.js";

export function mountStepper(jobId) {
  const rail = document.getElementById("pipeline-rail");
  if (!rail || !jobId) return () => {};
  return startPoll(async () => {
    const s = await apiGet(`/api/jobs/${jobId}/summary`);
    const job = s.job || {};
    const review = s.review || {};
    const status = String(job.status || "");
    const merged = job.stats?.merged_rows ?? 0;
    const pendingDup = review.pending_duplicates ?? 0;
    const exportStatus = s.latest_export?.status || "";

    const steps = [
      {
        name: "Upload", count: status === "completed" ? `${merged} merged` : status || "queued",
        cls: status === "completed" ? "done" : status === "failed" ? "flagged" : "current",
      },
      {
        name: "Review",
        count: review.confirmed ? "confirmed" : `${pendingDup} flagged`,
        cls: status !== "completed" ? "locked" : review.confirmed ? "done" : "flagged current",
      },
      {
        name: "Categorize",
        count: `${s.categorized_rows}/${s.total_rows}`,
        cls: status !== "completed" || !review.confirmed ? "locked"
          : s.categorized_rows >= s.total_rows && s.total_rows > 0 ? "done" : "current",
      },
      {
        name: "Export",
        count: exportStatus || "not started",
        cls: status !== "completed" || !review.confirmed ? "locked"
          : exportStatus === "completed" ? "done" : exportStatus ? "current" : "",
      },
    ];
    rail.innerHTML = steps.map(step =>
      `<div class="rail-step ${step.cls}"><span class="step-name">${step.name}</span><span class="step-count">${step.count}</span></div>`
    ).join("");
  }, 4000);
}
