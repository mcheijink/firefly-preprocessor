import { apiGet, jobIdFromShell } from "../api.js";
import { mountStepper } from "../stepper.js";
import { escapeHtml } from "../tables.js";

const jobId = jobIdFromShell();
mountStepper(jobId);

// ── DOM lookups ──────────────────────────────────────────────────────────
const chartEl = document.getElementById("balance-chart");
const legendEl = document.getElementById("balance-legend");

// ── API layer, extracted from app.js:1050 (fetchBalances) and rewired onto
// api.js's apiGet (which already extracts `detail` from error responses, so
// the manual `response.ok`/`payload.detail` check is dropped). ──
async function fetchBalances(id) {
  return apiGet(`/api/jobs/${id}/balances`);
}

// ── Chart rendering, extracted from app.js:1756 (drawBalanceChart).
// GLOBAL -> PARAMETER: the module-level `chartEl`/`legendEl` globals in
// app.js are now passed in explicitly so this function has no implicit
// dependency on this module's own top-level DOM lookups. ──
function drawBalanceChart(series, chart, legend) {
  if (!chart || !legend) {
    return;
  }
  chart.innerHTML = "";
  legend.innerHTML = "";
  if (!series.length) {
    chart.innerHTML = "<text x='20' y='40'>No balance data available.</text>";
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

  chart.insertAdjacentHTML("beforeend", `<rect x="${pad}" y="${pad}" width="${plotW}" height="${plotH}" class="chart-frame"></rect>`);

  series.forEach((accountSeries, i) => {
    const color = palette[i % palette.length];
    const points = (accountSeries.points || []).map((p) => {
      const xIdx = dateIndex.get(p.date) || 0;
      const x = pad + (dates.length <= 1 ? 0 : (xIdx / (dates.length - 1)) * plotW);
      const y = pad + plotH - ((Number(p.balance || 0) - minY) / span) * plotH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    if (points.length >= 2) {
      chart.insertAdjacentHTML("beforeend", `<polyline points="${points.join(" ")}" fill="none" stroke="${color}" stroke-width="2"></polyline>`);
    }
    legend.insertAdjacentHTML("beforeend", `<span class="legend-item"><i style="background:${color}"></i>${escapeHtml(accountSeries.account || "Unknown")}</span>`);
  });

  chart.insertAdjacentHTML("beforeend", `<text x="10" y="${pad + 8}" class="chart-label">${maxY.toFixed(2)}</text>`);
  chart.insertAdjacentHTML("beforeend", `<text x="10" y="${height - pad}" class="chart-label">${minY.toFixed(2)}</text>`);
}

// ── Loading, extracted from app.js:1329 (loadBalanceChart). GLOBAL ->
// MODULE-LOCAL: `activeJobId` -> the page-scoped `jobId` constant above. ──
async function loadBalanceChart() {
  if (!jobId) {
    drawBalanceChart([], chartEl, legendEl);
    return;
  }
  const payload = await fetchBalances(jobId);
  drawBalanceChart(payload.series || [], chartEl, legendEl);
}

// ── Initial load ─────────────────────────────────────────────────────────
async function initBalancesPage() {
  if (!jobId) {
    return;
  }
  try {
    await loadBalanceChart();
  } catch (error) {
    window.alert(error.message);
  }
}

initBalancesPage();
