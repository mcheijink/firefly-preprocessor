export async function apiGet(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(await extractDetail(res));
  return res.json();
}

export async function apiSend(path, method = "POST", body = undefined) {
  const opts = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await extractDetail(res));
  return res.json();
}

export async function apiUpload(path, formData) {
  const res = await fetch(path, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await extractDetail(res));
  return res.json();
}

async function extractDetail(res) {
  try {
    const data = await res.json();
    return data.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export function jobIdFromShell() {
  return document.querySelector(".job-shell")?.dataset.jobId ?? "";
}

// FIX 5: renders server ISO timestamps in the viewer's local time as
// "YYYY-MM-DD HH:MM" instead of the raw ISO string (which carries a "T" and
// a UTC offset). Callers should keep the raw ISO value available via a
// `title` attribute where the rendered markup allows it.
export function formatTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
