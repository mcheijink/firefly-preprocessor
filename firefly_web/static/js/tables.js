/**
 * Table / pagination / column-management helpers extracted from the legacy
 * static/app.js (SPA-era single script). See task-8-report.md for the full
 * list of global -> parameter conversions made during extraction.
 */

/**
 * Verbatim from app.js:1822 (escapeHtml). No globals referenced; exported
 * here (it was a bare global function in app.js) because renderTransactionRow,
 * renderDroppedPairingCell, renderCategorySelect and TableColumnManager all
 * depend on it, and later page modules (Tasks 9-13) will need it for their
 * own row renderers too.
 */
export function escapeHtml(raw) {
  const div = document.createElement("div");
  div.textContent = String(raw ?? "");
  return div.innerHTML;
}

/**
 * From app.js:1889 (amountClass). MODIFIED (Task 12, mandatory carried-over
 * fix from Task 8 review, step 12.3 of the plan): the legacy version emitted
 * a bare " amount-neg" suffix for negative amounts, matching the old
 * stylesheet's `.amount-neg` rule. The new stylesheet (styles.css:83-85)
 * instead styles `td.num.credit` / `td.num.debit` (with `td.num` handling
 * right-alignment/mono for all three cases). This now returns " credit" for
 * amount > 0, " debit" for amount < 0, and "" for zero/unparseable, so call
 * sites of the form `class="num${amountClass(x)}"` (renderTransactionRow
 * here, and the ollama/duplicate-review row renderers in later tasks) now
 * emit "num credit" / "num debit" / "num" without needing their own changes.
 */
export function amountClass(amount) {
  const num = parseFloat(String(amount || "").replace(",", "."));
  if (isNaN(num) || num === 0) return "";
  return num > 0 ? " credit" : " debit";
}

/**
 * Verbatim from app.js:2167 (renderPageButtonsHtml). No globals referenced;
 * exported because updateTxPagination depends on it and it is a pure
 * table-pagination helper reusable by other tables' pagination in later tasks.
 */
export function renderPageButtonsHtml(currentPage, totalPages, buttonClass) {
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

/**
 * Verbatim from app.js:1402 (buildTransactionRowKey). No globals referenced;
 * exported as a dependency of renderTransactionRow and of any page module
 * that needs to compute the same row key (e.g. to call selectTransactionRow
 * logic client-side).
 */
export function buildTransactionRowKey(rowSource, rowLocalIndex) {
  const source = String(rowSource || "").trim().toLowerCase();
  const idx = Number(rowLocalIndex || 0);
  return `${source}:${idx}`;
}

/**
 * Extracted from app.js:1307 (renderCategorySelect).
 * GLOBAL -> PARAMETER: the module-level `categoryOptions` array (populated
 * by loadTransactions from the /transactions payload) is now passed in
 * explicitly as `categoryOptions`.
 *
 * @param {number} mergeRowIndex
 * @param {string} currentCategory
 * @param {string[]} categoryOptions - was global `categoryOptions` in app.js
 */
export function renderCategorySelect(mergeRowIndex, currentCategory, categoryOptions) {
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
      const label = token || "—";
      return `<option value="${escapeHtml(token)}"${selected}>${escapeHtml(label)}</option>`;
    })
    .filter(Boolean);

  return [`<select class="tx-category-select" data-merge-row-index="${mergeRowIndex}">`, ...options, `</select>`].join("");
}

/**
 * Verbatim from app.js:1279 (renderDroppedPairingCell). No globals
 * referenced beyond escapeHtml (now a local module import/export); no
 * signature change.
 */
export function renderDroppedPairingCell(row) {
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

/**
 * Extracted from app.js:1243 (renderTransactionRow).
 * GLOBAL -> PARAMETER:
 *   - module-level `selectedRows` (a Set of merge-row indices) -> `selectedRows` param
 *   - module-level `activeTransactionKey` (string) -> `activeTransactionKey` param
 *   - module-level `categoryOptions` (via renderCategorySelect) -> `categoryOptions` param,
 *     forwarded to renderCategorySelect
 *
 * @param {object} row
 * @param {Set<number>} selectedRows - was global `selectedRows` in app.js
 * @param {string} activeTransactionKey - was global `activeTransactionKey` in app.js
 * @param {string[]} categoryOptions - was global `categoryOptions` in app.js
 */
export function renderTransactionRow(row, selectedRows, activeTransactionKey, categoryOptions) {
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
  const categoryCell = decision === "merged" ? renderCategorySelect(mergeRowIndex, String(row.category || ""), categoryOptions) : escapeHtml(row.category || "");
  const droppedPairingCell = renderDroppedPairingCell(row);
  const decisionLabel =
    decision === "merged" && Number(row._dropped_count || 0) > 0
      ? `merged + ${Number(row._dropped_count || 0)} dropped`
      : decision;

  return `
    <tr class="${rowClass}${selectedClass}" data-row-source="${escapeHtml(rowSource)}" data-row-local-index="${rowLocalIndex}" data-row-id="${escapeHtml(rowId)}" data-row-key="${escapeHtml(rowKey)}">
      <td data-col="select" data-label="Select"><input type="checkbox" class="row-checkbox" data-merge-row-index="${mergeRowIndex}" ${checked} ${disabled}></td>
      <td data-col="id" data-label="ID"><code>${escapeHtml(rowId)}</code></td>
      <td data-col="decision" data-label="Decision"><span class="decision-badge ${decision}">${escapeHtml(decisionLabel)}</span></td>
      <td data-col="date" data-label="Date">${escapeHtml(row.date || "")}</td>
      <td data-col="amount" data-label="Amount" class="num${amountClass(row.amount)}">${escapeHtml(row.amount || "")}</td>
      <td data-col="category" data-label="Category">${categoryCell}</td>
      <td data-col="description" data-label="Description">${escapeHtml(row.description || "")}</td>
      <td data-col="source_account" data-label="Source Account">${escapeHtml(row.source_account || "")}</td>
      <td data-col="destination_account" data-label="Destination Account">${escapeHtml(row.destination_account || "")}</td>
      <td data-col="dropped_pairing" data-label="Dropped Pairing">${droppedPairingCell}</td>
      <td data-col="details" data-label="Details"><button type="button" class="tx-open-detail secondary-btn" data-row-source="${escapeHtml(rowSource)}" data-row-local-index="${rowLocalIndex}" data-row-id="${escapeHtml(rowId)}">Open</button></td>
    </tr>
  `;
}

/**
 * Extracted from app.js:1425 (getTxTotalPages).
 * GLOBAL -> PARAMETER: module-level `txTotal` -> `txTotal` param,
 * module-level `txPageSize` -> `txPageSize` param.
 *
 * @param {number} txTotal - was global `txTotal` in app.js
 * @param {number} txPageSize - was global `txPageSize` in app.js
 */
export function getTxTotalPages(txTotal, txPageSize) {
  return Math.max(1, Math.ceil(txTotal / Math.max(1, txPageSize)));
}

/**
 * Extracted from app.js:1429 (updateTxPagination).
 * GLOBAL -> PARAMETER:
 *   - module-level `txPage` -> `txPage` param
 *   - `getTxTotalPages()` (no-arg global call) -> caller now passes the
 *     already-computed `totalPages` param
 *   - module-level DOM lookups `txPageFirstBtn`/`txPagePrevBtn`/`txPageNextBtn`/
 *     `txPageLastBtn`/`txPageButtons` -> bundled into an `els` param
 *     `{ firstBtn, prevBtn, nextBtn, lastBtn, pageButtons }`
 *   - the inline click handler used to call the global `loadTransactions(false)`
 *     and catch errors with the global `showToast`; both are page/module
 *     concerns outside tables.js's scope, so the handler now simply invokes
 *     the caller-supplied `onPageChange(page)` callback (the page module is
 *     responsible for updating its own `txPage` state, reloading data, and
 *     handling/reporting its own errors).
 *
 * @param {number} txPage - was global `txPage` in app.js
 * @param {number} totalPages - was computed internally via global getTxTotalPages(); caller now computes and passes it
 * @param {{firstBtn: Element|null, prevBtn: Element|null, nextBtn: Element|null, lastBtn: Element|null, pageButtons: Element|null}} els - was module-level DOM globals `txPageFirstBtn`, `txPagePrevBtn`, `txPageNextBtn`, `txPageLastBtn`, `txPageButtons`
 * @param {(page: number) => void} onPageChange - replaces the inline `txPage = page; await loadTransactions(false)` (with showToast error handling) from app.js; caller owns state update, reload, and error handling
 */
export function updateTxPagination(txPage, totalPages, els, onPageChange) {
  const canPrev = txPage > 1;
  const canNext = txPage < totalPages;
  if (els.firstBtn) els.firstBtn.disabled = !canPrev;
  if (els.prevBtn) els.prevBtn.disabled = !canPrev;
  if (els.nextBtn) els.nextBtn.disabled = !canNext;
  if (els.lastBtn) els.lastBtn.disabled = !canNext;
  if (!els.pageButtons) {
    return;
  }
  els.pageButtons.innerHTML = renderPageButtonsHtml(txPage, totalPages, "tx-page-btn");
  els.pageButtons.querySelectorAll(".tx-page-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const page = Number(btn.dataset.page || 1);
      if (page === txPage) {
        return;
      }
      onPageChange(page);
    });
  });
}

/**
 * Verbatim from app.js:1895-2162 (class TableColumnManager, the Excel-style
 * column manager added in commit 247a039). No SPA globals referenced — all
 * state (tableId, columns, sort/apply elements, callbacks) was already
 * passed in via the constructor options object in app.js, and the class
 * only reads `this.tableId`/`this.columns`/etc. and DOM ids that still
 * exist in the new templates. No signature changes were necessary; `export`
 * was added to the class declaration.
 */
export class TableColumnManager {
  constructor({ tableId, columns, sortByEl = null, sortDirEl = null, applyEl = null, onClientSort = null, onRedraw = null }) {
    this.tableId = tableId;
    this.columns = columns; // [{key, label, sortKey?, defaultHidden?, alwaysVisible?}]
    this.sortByEl = sortByEl;
    this.sortDirEl = sortDirEl;
    this.applyEl = applyEl;
    this.onClientSort = onClientSort;
    this.onRedraw = onRedraw;
    this._dragKey = null;
    this._styleEl = null;
    this.state = this._loadState();
    this._applyVisibility();
  }

  get _table() { return document.getElementById(this.tableId); }
  _storageKey() { return `tcm3_${this.tableId}`; }

  _loadState() {
    const defaultOrder = this.columns.map((c) => c.key);
    const defaultHidden = this.columns.filter((c) => c.defaultHidden).map((c) => c.key);
    try {
      const s = JSON.parse(localStorage.getItem(this._storageKey()) || "null");
      if (s && Array.isArray(s.order)) {
        const saved = s.order.filter((k) => defaultOrder.includes(k));
        const added = defaultOrder.filter((k) => !saved.includes(k));
        return {
          order: [...saved, ...added],
          hidden: Array.isArray(s.hidden) ? s.hidden.filter((k) => defaultOrder.includes(k)) : defaultHidden,
        };
      }
    } catch {}
    return { order: defaultOrder, hidden: defaultHidden };
  }

  _saveState() {
    try { localStorage.setItem(this._storageKey(), JSON.stringify(this.state)); } catch {}
  }

  _applyVisibility() {
    const id = `tcm-style-${this.tableId}`;
    this._styleEl = document.getElementById(id);
    if (!this._styleEl) {
      this._styleEl = document.createElement("style");
      this._styleEl.id = id;
      document.head.appendChild(this._styleEl);
    }
    this._styleEl.textContent = this.state.hidden
      .map((k) => `#${this.tableId} [data-col="${k}"] { display: none !important; }`)
      .join("\n");
  }

  setHidden(key, hidden) {
    const col = this.columns.find((c) => c.key === key);
    if (col && col.alwaysVisible) return;
    if (hidden) {
      if (!this.state.hidden.includes(key)) this.state.hidden.push(key);
    } else {
      this.state.hidden = this.state.hidden.filter((k) => k !== key);
    }
    this._saveState();
    this._applyVisibility();
  }

  // Apply stored column order to both <thead> and all <tbody> rows in the DOM.
  applyToTable() {
    const t = this._table;
    if (!t) return;
    const order = this.state.order;

    const theadRow = t.querySelector("thead > tr");
    if (theadRow) {
      const thMap = {};
      theadRow.querySelectorAll("[data-col]").forEach((th) => { thMap[th.dataset.col] = th; });
      order.forEach((key) => { if (thMap[key]) theadRow.appendChild(thMap[key]); });
      this._updateSortIndicators(theadRow);
    }

    t.querySelectorAll("tbody > tr").forEach((tr) => {
      const tdMap = {};
      tr.querySelectorAll("[data-col]").forEach((td) => { tdMap[td.dataset.col] = td; });
      order.forEach((key) => { if (tdMap[key]) tr.appendChild(tdMap[key]); });
    });
  }

  _updateSortIndicators(theadRow) {
    const row = theadRow || (this._table && this._table.querySelector("thead > tr"));
    if (!row) return;
    const currentKey = this.sortByEl ? this.sortByEl.value : (this._clientSortKey || "");
    const currentDir = this.sortDirEl ? this.sortDirEl.value : (this._clientSortDir || "asc");
    row.querySelectorAll("th[data-sort-key]").forEach((th) => {
      th.removeAttribute("data-sort-asc");
      th.removeAttribute("data-sort-desc");
      if (th.dataset.sortKey === currentKey) {
        th.setAttribute(currentDir === "asc" ? "data-sort-asc" : "data-sort-desc", "");
      }
    });
  }

  // Wire header click-to-sort and drag-to-reorder. Call after DOM is ready.
  bindHeaderEvents() {
    const t = this._table;
    if (!t) return;
    const theadRow = t.querySelector("thead > tr");
    if (!theadRow) return;

    theadRow.querySelectorAll("th[data-col]").forEach((th) => {
      // ── sort on click ──────────────────────────────────────────────────
      if (th.classList.contains("th-sortable") && th.dataset.sortKey) {
        th.addEventListener("click", () => {
          if (th._tcmWasDragged) { th._tcmWasDragged = false; return; }
          this._handleSort(th.dataset.sortKey);
        });
      }

      // ── drag to reorder columns ────────────────────────────────────────
      th.draggable = true;
      th.classList.add("th-draggable");
      th.addEventListener("dragstart", (e) => {
        this._dragKey = th.dataset.col;
        th.classList.add("th-dragging");
        e.dataTransfer.effectAllowed = "move";
      });
      th.addEventListener("dragend", () => {
        th.classList.remove("th-dragging");
        theadRow.querySelectorAll("th").forEach((h) => h.classList.remove("th-drag-over"));
      });
      th.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        theadRow.querySelectorAll("th").forEach((h) => h.classList.remove("th-drag-over"));
        if (this._dragKey !== th.dataset.col) th.classList.add("th-drag-over");
      });
      th.addEventListener("dragleave", () => th.classList.remove("th-drag-over"));
      th.addEventListener("drop", (e) => {
        e.preventDefault();
        th.classList.remove("th-drag-over");
        if (!this._dragKey || this._dragKey === th.dataset.col) return;
        const dragTh = theadRow.querySelector(`th[data-col="${this._dragKey}"]`);
        if (dragTh) {
          dragTh._tcmWasDragged = true;
          theadRow.insertBefore(dragTh, th);
        }
        // Derive new order from DOM
        const newOrder = Array.from(theadRow.querySelectorAll("th[data-col]")).map((h) => h.dataset.col);
        this.state.order = newOrder;
        this._saveState();
        // Reorder existing tbody rows
        t.querySelectorAll("tbody > tr").forEach((tr) => {
          const tdMap = {};
          tr.querySelectorAll("[data-col]").forEach((td) => { tdMap[td.dataset.col] = td; });
          newOrder.forEach((key) => { if (tdMap[key]) tr.appendChild(tdMap[key]); });
        });
      });
    });
  }

  _handleSort(sortKey) {
    if (this.onClientSort) {
      const newDir =
        this._clientSortKey === sortKey && this._clientSortDir === "asc" ? "desc" : "asc";
      this._clientSortKey = sortKey;
      this._clientSortDir = newDir;
      this._updateSortIndicators();
      this.onClientSort(sortKey, newDir);
      return;
    }
    if (!this.sortByEl || !this.sortDirEl) return;
    if (this.sortByEl.value === sortKey) {
      this.sortDirEl.value = this.sortDirEl.value === "asc" ? "desc" : "asc";
    } else {
      this.sortByEl.value = sortKey;
      this.sortDirEl.value = "asc";
    }
    this._updateSortIndicators();
    if (this.applyEl) this.applyEl.click();
    else if (this.onRedraw) this.onRedraw();
  }

  openPicker(anchorEl) {
    const PANEL_ID = "tcm-picker-panel";
    const existing = document.getElementById(PANEL_ID);
    if (existing) {
      if (existing.dataset.tcmTable === this.tableId) { existing.remove(); return; }
      existing.remove();
    }

    const panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.dataset.tcmTable = this.tableId;
    panel.className = "tcm-picker-panel";
    panel.innerHTML = `
      <div class="tcm-picker-header">
        <strong>Columns</strong>
        <button type="button" class="tcm-reset secondary-btn" style="font-size:0.75em;padding:0.2em 0.5em">Reset</button>
      </div>
      <ul class="tcm-picker-list">
        ${this.state.order
          .map((key) => {
            const def = this.columns.find((c) => c.key === key);
            if (!def) return "";
            const checked = !this.state.hidden.includes(key) ? "checked" : "";
            const disabled = def.alwaysVisible ? "disabled" : "";
            return `
              <li class="tcm-picker-item" data-key="${key}" draggable="true">
                <span class="tcm-drag-handle" title="Drag to reorder">⠿</span>
                <label><input type="checkbox" ${checked} ${disabled} data-key="${key}">${escapeHtml(def.label)}</label>
              </li>`;
          })
          .join("")}
      </ul>`;
    document.body.appendChild(panel);

    // Position below anchor
    if (anchorEl) {
      const rect = anchorEl.getBoundingClientRect();
      const panelW = 220;
      const left = Math.max(4, Math.min(rect.left, window.innerWidth - panelW - 4));
      Object.assign(panel.style, { position: "fixed", top: `${rect.bottom + 4}px`, left: `${left}px`, minWidth: `${panelW}px` });
    }

    // Close on outside click
    const onOutside = (e) => {
      if (!panel.contains(e.target) && e.target !== anchorEl) {
        panel.remove();
        document.removeEventListener("click", onOutside, true);
      }
    };
    setTimeout(() => document.addEventListener("click", onOutside, true), 0);

    // Visibility toggles
    panel.querySelectorAll("input[type='checkbox']").forEach((cb) => {
      cb.addEventListener("change", () => this.setHidden(cb.dataset.key, !cb.checked));
    });

    // Reset
    panel.querySelector(".tcm-reset").addEventListener("click", () => {
      this.state = { order: this.columns.map((c) => c.key), hidden: this.columns.filter((c) => c.defaultHidden).map((c) => c.key) };
      this._saveState();
      this._applyVisibility();
      this.applyToTable();
      if (this.onRedraw) this.onRedraw();
      panel.remove();
    });

    // Drag-to-reorder inside picker
    let pickerDragKey = null;
    const list = panel.querySelector(".tcm-picker-list");
    panel.querySelectorAll(".tcm-picker-item").forEach((item) => {
      item.addEventListener("dragstart", () => { pickerDragKey = item.dataset.key; item.classList.add("dragging"); });
      item.addEventListener("dragend", () => { item.classList.remove("dragging"); list.querySelectorAll(".tcm-picker-item").forEach((i) => i.classList.remove("drag-over")); pickerDragKey = null; });
      item.addEventListener("dragover", (e) => { e.preventDefault(); item.classList.add("drag-over"); });
      item.addEventListener("dragleave", () => item.classList.remove("drag-over"));
      item.addEventListener("drop", (e) => {
        e.preventDefault();
        item.classList.remove("drag-over");
        if (!pickerDragKey || pickerDragKey === item.dataset.key) return;
        const dragEl = list.querySelector(`[data-key="${pickerDragKey}"]`);
        if (dragEl) list.insertBefore(dragEl, item);
        const newOrder = Array.from(list.querySelectorAll(".tcm-picker-item")).map((i) => i.dataset.key);
        this.state.order = newOrder;
        this._saveState();
        this.applyToTable();
        if (this.onRedraw) this.onRedraw();
      });
    });
  }
}
