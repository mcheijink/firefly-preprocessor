import { apiGet } from "./api.js";
import { startPoll } from "./polling.js";

const badge = document.getElementById("queue-badge");
if (badge) {
  startPoll(async () => {
    const data = await apiGet("/api/queues/summary");
    const o = data.ollama?.metrics || {};
    const f = data.firefly_export?.metrics || {};
    const active = (o.queued || 0) + (o.running || 0) + (f.queued || 0) + (f.running || 0);
    if (active > 0) {
      badge.hidden = false;
      badge.textContent = `⚙ ${active} running`;
      if ((o.queued || 0) + (o.running || 0) > 0 && data.ollama.job_id) {
        badge.href = `/jobs/${data.ollama.job_id}/transactions`;
      } else if (data.firefly_export.job_id) {
        badge.href = `/jobs/${data.firefly_export.job_id}/export`;
      }
    } else {
      badge.hidden = true;
    }
  }, 5000);
}
