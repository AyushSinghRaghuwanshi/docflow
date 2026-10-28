// DocFlow review console. Plain JavaScript, no build step: served by FastAPI from /static.
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const main = $("#main");

// ---------------------------------------------------------------- helpers
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    const err = new Error(typeof body === "object" ? (body.detail?.message || body.detail || res.statusText) : body || res.statusText);
    err.status = res.status; err.body = body;
    throw err;
  }
  return body;
}

const pct = (x, d = 1) => (x == null ? "–" : `${(x * 100).toFixed(d)}%`);
const pts = (x) => (x * 100).toFixed(1);

function money(value, currency) {
  if (value == null || value === "") return "–";
  const n = Number(value);
  if (Number.isNaN(n)) return esc(value);
  try {
    if (currency && /^[A-Z]{3}$/.test(currency)) return new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(n);
  } catch { /* unknown code: fall through */ }
  return n.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function niceDate(iso) {
  if (!iso) return "–";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return Number.isNaN(+d) ? esc(iso) : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function ago(iso) {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} d ago`;
  return niceDate(iso);
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.hidden = true), 3200);
}

const ICON = {
  error: '<svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="10" cy="10" r="7.5"/><path d="M10 6v4.5M10 13.5v.01"/></svg>',
  warning: '<svg viewBox="0 0 20 20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3l7.5 13h-15z"/><path d="M10 8v3.5M10 14v.01"/></svg>',
  upload: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 14V4M6 8l4-4 4 4M4 16h12"/></svg>',
};

// What each check means for the person clearing the queue.
const ISSUE_TEXT = {
  TOTAL_MISMATCH: "Total doesn't add up",
  VAT_MISMATCH: "VAT doesn't match the rate",
  LINE_ARITHMETIC: "A line's quantity × price is wrong",
  LINE_ITEMS_MISMATCH: "Line items don't sum to the subtotal",
  NO_LINE_ITEMS: "No line items found",
  MISSING_FIELD: "A required field is missing",
  MISSING_CURRENCY: "Currency not stated",
  FUTURE_DATE: "Invoice is dated in the future",
  DUE_BEFORE_ISSUE: "Due date is before the invoice date",
  NON_POSITIVE_TOTAL: "Total is zero or negative",
  UNUSUAL_VAT_RATE: "Unusual VAT rate",
  DUPLICATE: "Already received",
  POSSIBLE_DUPLICATE: "Possibly already received",
  PROMPT_INJECTION: "Hidden instructions in the document",
  FIELD_DISAGREEMENT: "Model and rules disagree",
  UNGROUNDED_FIELD: "Value not found in the document",
  UNCERTAIN_FIELD: "Model was unsure",
  NUMBER_IS_REFERENCE: "Invoice number looks like a PO or reference",
  SUPPLIER_IS_LABEL: "Supplier name looks like a label",
  IMAGE_UNVERIFIED: "Image: values couldn't be checked against text",
};
const issueTitle = (code) => ISSUE_TEXT[code] || code.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

const FIELDS = [
  ["supplier_name", "Supplier", "text"],
  ["supplier_address", "Supplier address", "text"],
  ["invoice_number", "Invoice number", "text"],
  ["invoice_date", "Invoice date", "date"],
  ["due_date", "Due date", "date"],
  ["currency", "Currency", "text"],
  ["subtotal", "Subtotal", "money"],
  ["vat_rate", "VAT rate (%)", "money"],
  ["vat_amount", "VAT", "money"],
  ["total", "Total", "money"],
];

const DECISION = { auto_approved: "Auto-approved", needs_review: "Needs review", rejected: "Rejected" };
const STATUS = { pending: "Waiting for review", approved: "Approved", rejected: "Rejected" };
const statusPill = (s) => `<span class="pill ${esc(s)}">${esc(STATUS[s] || s)}</span>`;
const decisionPill = (d) => `<span class="pill ${esc(d)}">${esc(DECISION[d] || d)}</span>`;
const invoiceOf = (doc) => doc.reviewed || doc.result.invoice;

// ---------------------------------------------------------------- shell state
const state = { health: null, pending: [] };

async function refreshShell() {
  try {
    state.pending = await api("/documents?status=pending");
    const c = $("#nav-pending");
    c.textContent = state.pending.length; c.hidden = !state.pending.length;
  } catch { /* the page itself will show the error */ }
}

async function loadHealth() {
  const eng = $("#engine");
  try {
    state.health = await api("/health");
    $("#engine-name").textContent = state.health.model ? state.health.model : "Rules only (no model)";
    eng.className = "engine ok";
    eng.title = `Reading documents with ${state.health.extractor}`;
  } catch {
    $("#engine-name").textContent = "Service unreachable";
    eng.className = "engine down";
  }
}

// ---------------------------------------------------------------- router
const routes = { overview: viewOverview, review: viewReview, documents: viewDocuments, benchmarks: viewBenchmarks, system: viewSystem };

function parseHash() {
  const [path, query = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const [name, id] = path.split("/");
  return { name: routes[name] ? name : "overview", id: id ? Number(id) : null, q: new URLSearchParams(query) };
}

let renderToken = 0;
async function render() {
  const r = parseHash();
  const token = ++renderToken;
  $$(".nav nav a").forEach((a) => a.setAttribute("aria-current", a.dataset.route === r.name ? "page" : "false"));
  document.body.classList.remove("nav-open");
  cleanupKeys();
  main.innerHTML = '<div class="skeleton" style="width:30%;height:22px"></div><div class="skeleton" style="width:60%"></div><div class="skeleton" style="width:45%"></div>';
  try {
    await routes[r.name](r, () => token === renderToken);
  } catch (e) {
    if (token !== renderToken) return;
    main.innerHTML = `<div class="panel empty"><h2>This page couldn't load</h2><p>${esc(e.message)}. Check that the DocFlow service is running, then try again.</p>
      <button class="btn" type="button" onclick="location.reload()">Try again</button></div>`;
  }
  const title = { overview: "Overview", review: "Review queue", documents: "Documents", benchmarks: "Benchmarks", system: "System" }[r.name];
  document.title = `${title} · DocFlow`;
}

// Keyboard handlers registered by a view are removed when the route changes.
let viewKeys = null;
function cleanupKeys() { if (viewKeys) document.removeEventListener("keydown", viewKeys); viewKeys = null; }
const typing = (e) => /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;

// ---------------------------------------------------------------- overview
async function viewOverview(_r, live) {
  const [m, docs] = await Promise.all([api("/metrics"), api("/documents")]);
  if (!live()) return;
  if (!m.documents) {
    main.innerHTML = `<div class="page-head"><div><h1>Overview</h1><p>Nothing has been processed yet.</p></div></div>
      <div class="panel empty"><h2>Upload your first invoice</h2>
      <p>DocFlow reads PDFs, spreadsheets, text files and receipt photos, checks the arithmetic and the source text,<br>and sends anything doubtful to the review queue.</p>
      <button class="btn primary" type="button" data-upload>${ICON.upload}Upload documents</button></div>`;
    return;
  }
  const d = m.by_decision, s = m.by_status, n = m.documents;
  const share = (k) => (d[k] / n) * 100;
  const worst = Math.max(1, ...m.issues.map((i) => i.documents));
  const recent = docs.slice(0, 7);

  main.innerHTML = `
  <div class="page-head">
    <div><h1>Overview</h1>
    <p>${n} document${n === 1 ? "" : "s"} processed. ${s.pending ? `<a href="#/review">${s.pending} waiting for review</a>.` : "The review queue is clear."}</p></div>
    <button class="btn" type="button" data-upload>${ICON.upload}Upload documents</button>
  </div>
  <dl class="ledger">
    <div><dt>Processed</dt><dd class="num">${n}</dd></div>
    <div><dt>Approved without a person</dt><dd class="num">${pct(m.straight_through_rate, 0)}<small>${d.auto_approved} of ${n}</small></dd></div>
    <div><dt>Waiting for review</dt><dd class="num">${s.pending}</dd></div>
    <div><dt>Average time per document</dt><dd class="num">${m.avg_seconds_per_document || "<0.1"}<small>s</small></dd></div>
  </dl>
  <section class="flow" aria-label="How documents were decided">
    <div class="flow-bar" role="img" aria-label="${d.auto_approved} auto-approved, ${d.needs_review} sent to review, ${d.rejected} rejected">
      ${d.auto_approved ? `<span class="a" style="flex:${share("auto_approved")}"></span>` : ""}
      ${d.needs_review ? `<span class="r" style="flex:${share("needs_review")}"></span>` : ""}
      ${d.rejected ? `<span class="x" style="flex:${share("rejected")}"></span>` : ""}
    </div>
    <div class="flow-legend">
      <span><i style="background:var(--ok)"></i><b class="num">${d.auto_approved}</b>approved automatically</span>
      <span><i style="background:var(--warn)"></i><b class="num">${d.needs_review}</b>sent to a person</span>
      <span><i style="background:var(--bad)"></i><b class="num">${d.rejected}</b>rejected</span>
      ${m.injections_blocked ? `<span><b class="num">${m.injections_blocked}</b>with hidden instructions blocked</span>` : ""}
    </div>
  </section>
  <div class="two">
    <section class="panel">
      <header><div><h2>Recent documents</h2></div><a href="#/documents" class="small">All documents</a></header>
      <div class="table-wrap"><table>
        <thead><tr><th>Document</th><th class="r">Total</th><th>Status</th><th>Received</th></tr></thead>
        <tbody>${recent.map((doc) => {
          const inv = invoiceOf(doc);
          return `<tr class="clickable" data-href="#/review/${doc.id}" tabindex="0">
            <td><div class="doc-cell"><strong>${esc(inv.supplier_name || doc.name)}</strong><span>${esc(doc.name)}</span></div></td>
            <td class="r num">${money(inv.total, inv.currency)}</td><td>${statusPill(doc.status)}</td>
            <td class="muted small">${ago(doc.created_at)}</td></tr>`;
        }).join("")}</tbody></table></div>
    </section>
    <section class="panel">
      <header><div><h2>Why documents were stopped</h2><p>Checks that fired, by number of documents</p></div></header>
      <div class="panel-body">${m.issues.length ? m.issues.slice(0, 8).map((i) => `
        <div class="issue-row">
          <span>${esc(issueTitle(i.code))}</span><span class="num muted">${i.documents}</span>
          <div class="bar"><span class="${esc(i.severity)}" style="width:${(i.documents / worst) * 100}%"></span></div>
        </div>`).join("") : '<p class="muted">No checks have fired yet.</p>'}
      </div>
    </section>
  </div>`;
}

// ---------------------------------------------------------------- documents
async function viewDocuments(r, live) {
  const docs = await api("/documents");
  if (!live()) return;
  let filter = r.q.get("status") || "all";
  let query = r.q.get("q") || $("#search-input").value || "";
  $("#search-input").value = query;

  main.innerHTML = `
  <div class="page-head">
    <div><h1>Documents</h1><p>Every document DocFlow has read, newest first.</p></div>
    <div class="filters">
      <div class="seg" role="group" aria-label="Filter by status">
        ${[["all", "All"], ["pending", "Waiting"], ["approved", "Approved"], ["rejected", "Rejected"]].map(([k, l]) =>
          `<button type="button" data-filter="${k}" aria-pressed="${k === filter}">${l} <span class="faint num">${k === "all" ? docs.length : docs.filter((d) => d.status === k).length}</span></button>`).join("")}
      </div>
    </div>
  </div>
  <section class="panel"><div class="table-wrap"><table>
    <thead><tr><th>Document</th><th>Invoice number</th><th>Invoice date</th><th class="r">Total</th><th>DocFlow decided</th><th>Status</th><th>Received</th></tr></thead>
    <tbody id="doc-rows"></tbody></table></div>
    <div id="doc-empty" class="empty" hidden></div>
  </section>`;

  const draw = () => {
    const q = query.trim().toLowerCase();
    const rows = docs.filter((d) => (filter === "all" || d.status === filter) && (!q || [d.name, invoiceOf(d).supplier_name, invoiceOf(d).invoice_number]
      .some((v) => (v || "").toLowerCase().includes(q))));
    $("#doc-rows").innerHTML = rows.map((doc) => {
      const inv = invoiceOf(doc), errs = doc.result.issues.filter((i) => i.severity === "error").length;
      return `<tr class="clickable" data-href="#/review/${doc.id}" tabindex="0">
        <td><div class="doc-cell"><strong>${esc(inv.supplier_name || "Supplier not found")}</strong><span>${esc(doc.name)}</span></div></td>
        <td class="num">${esc(inv.invoice_number || "–")}</td><td class="num">${niceDate(inv.invoice_date)}</td>
        <td class="r num">${money(inv.total, inv.currency)}</td>
        <td>${decisionPill(doc.decision)}${errs ? ` <span class="sev error small">${errs} error${errs > 1 ? "s" : ""}</span>` : ""}</td>
        <td>${statusPill(doc.status)}</td><td class="muted small">${ago(doc.created_at)}</td></tr>`;
    }).join("");
    const empty = $("#doc-empty");
    empty.hidden = rows.length > 0;
    empty.innerHTML = docs.length ? `<h2>No documents match</h2><p>Try a different supplier, invoice number or file name.</p>`
      : `<h2>No documents yet</h2><p>Upload invoices or receipts and they'll appear here.</p><button class="btn primary" type="button" data-upload>${ICON.upload}Upload documents</button>`;
  };
  draw();
  $$("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    filter = b.dataset.filter;
    $$("[data-filter]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    draw();
  }));
  const input = $("#search-input");
  const onInput = () => { query = input.value; draw(); };
  input.addEventListener("input", onInput);
  const stop = () => { input.removeEventListener("input", onInput); window.removeEventListener("hashchange", stop); };
  window.addEventListener("hashchange", stop);
}

// ---------------------------------------------------------------- review workspace
async function viewReview(r, live) {
  await refreshShell();
  const queue = state.pending;
  const id = r.id ?? queue[0]?.id;
  if (!live()) return;
  if (id == null) {
    main.innerHTML = `<div class="page-head"><div><h1>Review queue</h1><p>Documents DocFlow wasn't sure about wait here for a person.</p></div></div>
      <div class="panel empty"><h2>Nothing to review</h2><p>Every document has been decided. New uploads that need a person will appear here.</p>
      <a class="btn" href="#/documents">See all documents</a></div>`;
    return;
  }
  const [doc, ev] = await Promise.all([api(`/documents/${id}`), api(`/documents/${id}/evidence`).catch(() => ({ text: null, spans: {}, original: false }))]);
  if (!live()) return;

  const inv = invoiceOf(doc);
  const res = doc.result;
  const pending = doc.status === "pending";
  const conf = res.field_confidence || {};
  const ext = (doc.name.split(".").pop() || "").toLowerCase();
  const isImage = ["jpg", "jpeg", "png", "webp", "gif"].includes(ext);
  const flagged = new Set(res.issues.filter((i) => i.field).map((i) => i.field));
  const errors = res.issues.filter((i) => i.severity === "error");
  const pos = queue.findIndex((d) => d.id === id);

  const fieldRow = ([key, label, kind]) => {
    const v = inv[key];
    const val = v == null ? "" : String(v);
    const c = conf[key];
    const found = ev.text == null || !val ? "" : ev.spans[key]
      ? `<span class="found">Found in the document${ev.spans[key].length > 1 ? ` (${ev.spans[key].length} places)` : ""}</span>`
      : `<span class="found none">Not found in the document text</span>`;
    return `<div class="field${flagged.has(key) ? " flagged" : ""}" data-field="${key}">
      <label for="f-${key}">${label}</label>
      <input class="field-input${kind !== "text" ? " num" : ""}" id="f-${key}" name="${key}" ${kind === "date" ? 'type="date"' : 'type="text"'}
        ${kind === "money" ? 'inputmode="decimal"' : ""} value="${esc(val)}" data-orig="${esc(val)}" ${pending ? "" : "readonly"} autocomplete="off">
      <span class="conf ${esc(c || "")}" title="${c ? `Confidence: ${c}` : "No confidence recorded"}"><i></i><i></i><i></i></span>
      ${found}</div>`;
  };

  const hasOriginal = ev.original !== false;
  const originalView = !hasOriginal ? `<div class="empty"><h2>Original file not kept</h2><p>This document was uploaded before DocFlow started keeping originals, so only the extracted values are available. Upload it again to see the file here.</p></div>`
    : isImage ? `<img src="/documents/${id}/file" alt="Original upload: ${esc(doc.name)}">`
    : ext === "pdf" ? `<iframe src="/documents/${id}/file#view=FitH" title="Original PDF"></iframe>`
    : ev.text != null ? `<pre class="doc-text">${esc(ev.text)}</pre>`
    : `<div class="empty"><h2>No preview for this file type</h2><a class="btn" href="/documents/${id}/file" download>Download original</a></div>`;

  main.innerHTML = `
  <div class="review">
    <aside class="panel queue" aria-label="Review queue">
      <header><h2>Waiting <span class="faint num">${queue.length}</span></h2></header>
      ${queue.length ? `<ol>${queue.map((d) => {
        const i = d.result.invoice, e = d.result.issues.filter((x) => x.severity === "error");
        return `<li><a href="#/review/${d.id}" aria-current="${d.id === id}">
          <div class="q-top"><span>${esc(i.supplier_name || d.name)}</span><span class="num muted">${money(i.total, i.currency)}</span></div>
          <div class="q-sub">${esc(d.name)}</div>
          ${e.length ? `<div class="q-flag">${esc(issueTitle(e[0].code))}${e.length > 1 ? ` +${e.length - 1}` : ""}</div>` : ""}</a></li>`;
      }).join("")}</ol>` : '<p class="panel-body muted">The queue is clear.</p>'}
    </aside>

    <section class="panel viewer" aria-label="Document">
      <header>
        <div><h2>${ev.text != null ? "What DocFlow read" : "Original"}</h2><p id="viewer-hint">${ev.text != null ? "Point at a field to see where its value came from." : isImage ? "Read from the image by the vision model." : ""}</p></div>
        ${ev.text != null && hasOriginal && (isImage || ext === "pdf") ? `<div class="seg" role="group" aria-label="View">
          <button type="button" data-view="text" aria-pressed="true">Text</button><button type="button" data-view="original" aria-pressed="false">Original</button></div>` : ""}
      </header>
      <div class="viewer-body" id="viewer">${ev.text != null ? `<pre class="doc-text" id="doc-text">${highlight(ev.text, ev.spans)}</pre>` : originalView}</div>
    </section>

    <div class="side">
      <section class="panel doc-head">
        <h1>${esc(inv.supplier_name || doc.name)}</h1>
        <div class="meta">${decisionPill(doc.decision)} ${statusPill(doc.status)}
          <span>${esc(doc.name)}</span><span>${ago(doc.created_at)}</span>
          <span title="${esc(res.extractor)}">${res.usage.llm_calls ? `${res.usage.llm_calls} model call${res.usage.llm_calls > 1 ? "s" : ""}` : "Rules only"} · ${(res.usage.latency_ms / 1000).toFixed(1)} s</span>
        </div>
      </section>

      <section class="panel">
        <header><div><h2>${errors.length ? `${errors.length} problem${errors.length > 1 ? "s" : ""} to resolve` : res.issues.length ? "Worth a look" : "No problems found"}</h2>
          <p>${pending ? (errors.length ? "Correct the fields below, or approve with a reason." : "Check the values, then approve.") : "This document has been decided."}</p></div></header>
        ${res.issues.length ? `<ul class="issues">${res.issues.map((i) => `<li class="${esc(i.severity)}" ${i.field ? `data-for="${esc(i.field)}"` : ""}>${ICON[i.severity] || ""}
          <div><strong>${esc(issueTitle(i.code))}</strong><p class="muted small">${esc(i.message)}</p></div></li>`).join("")}</ul>` : ""}
      </section>

      <form class="panel" id="review-form" autocomplete="off">
        <header><div><h2>Extracted fields</h2><p>${pending ? "Edit any value that's wrong. Approval re-checks the final values." : "Final values"}</p></div></header>
        <div class="fields">${FIELDS.map(fieldRow).join("")}</div>
        ${inv.line_items?.length ? `<div class="table-wrap"><table class="lines"><thead><tr><th>Line item</th><th class="r">Qty</th><th class="r">Price</th><th class="r">Amount</th></tr></thead>
          <tbody>${inv.line_items.map((l) => `<tr><td>${esc(l.description)}</td><td class="r num">${esc(l.quantity)}</td><td class="r num">${money(l.unit_price)}</td><td class="r num">${money(l.amount)}</td></tr>`).join("")}</tbody></table></div>` : ""}
        ${pending ? `<div class="decide">
          <label class="small muted" for="reason">Reason ${errors.length ? "(needed to approve while problems remain; at least 10 characters)" : "(optional, kept in the audit log)"}</label>
          <textarea id="reason" placeholder="${errors.length ? "e.g. Checked with the supplier: the total includes a delivery charge" : "Add a note for the audit log"}"></textarea>
          <div id="blocked" class="blocked" hidden></div>
          <div class="row">
            <button class="btn approve" type="submit" data-act="approve">Approve<kbd>A</kbd></button>
            <button class="btn reject" type="button" data-act="reject">Reject<kbd>R</kbd></button>
          </div>
          <p class="hint" id="change-hint">No changes made.</p>
        </div>` : ""}
      </form>

      <section class="panel">
        <header><h2>History</h2></header>
        <ol class="timeline">
          <li><div>Read by DocFlow and ${esc((DECISION[doc.decision] || doc.decision).toLowerCase())}</div><div class="when">${new Date(doc.created_at).toLocaleString("en-GB")}</div></li>
          ${(doc.audit || []).map((a) => `<li class="${esc(a.action)}"><div>${esc({ approved: "Approved", approved_with_override: "Approved with an override", rejected: "Rejected", blocked: "Approval blocked" }[a.action] || a.action)}${
            Object.keys(a.changes || {}).length ? ` · changed ${Object.keys(a.changes).map((k) => esc(FIELDS.find((f) => f[0] === k)?.[1] || k)).join(", ")}` : ""}</div>
            <div class="when">${new Date(a.at).toLocaleString("en-GB")}</div>${a.reason ? `<div class="why">“${esc(a.reason)}”</div>` : ""}</li>`).join("")}
        </ol>
      </section>
      ${pending ? `<div class="shortcuts"><span><kbd>A</kbd> approve</span><span><kbd>R</kbd> reject</span><span><kbd>J</kbd> <kbd>K</kbd> next and previous</span></div>` : ""}
    </div>
  </div>`;

  wireEvidence();
  $$("[data-view]").forEach((b) => b.addEventListener("click", () => {
    $$("[data-view]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    $("#viewer").innerHTML = b.dataset.view === "text" ? `<pre class="doc-text" id="doc-text">${highlight(ev.text, ev.spans)}</pre>` : originalView;
    $("#viewer-hint").textContent = b.dataset.view === "text" ? "Point at a field to see where its value came from." : "";
    wireEvidence();
  }));

  if (!pending) return;
  const form = $("#review-form");
  const changed = () => $$(".field-input", form).filter((i) => i.value.trim() !== i.dataset.orig);
  form.addEventListener("input", () => {
    $$(".field").forEach((f) => f.classList.toggle("changed", $(".field-input", f).value.trim() !== $(".field-input", f).dataset.orig));
    const c = changed();
    $("#change-hint").textContent = c.length ? `${c.length} field${c.length > 1 ? "s" : ""} changed. Approving saves your values and re-checks them.` : "No changes made.";
  });

  const submit = async (approve) => {
    const reason = $("#reason").value.trim();
    if (!approve && reason.length < 3 && !confirm("Reject without a reason?")) return;
    const body = { approve, reason: reason || null };
    if (approve && changed().length) {
      const corrected = { ...res.invoice, ...(doc.reviewed || {}) };
      for (const [key, , kind] of FIELDS) {
        const v = $(`#f-${key}`).value.trim();
        corrected[key] = v === "" ? null : kind === "money" ? v.replace(/[^\d.\-]/g, "") : key === "currency" ? v.toUpperCase() : v;
      }
      body.corrected = corrected;
    }
    $$("[data-act]").forEach((b) => (b.disabled = true));
    try {
      await api(`/documents/${id}/review`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      toast(approve ? "Approved" : "Rejected");
      await refreshShell();
      const next = state.pending.find((d) => d.id !== id);
      location.hash = next ? `#/review/${next.id}` : `#/review/${id}`;
      if (!next) render();
    } catch (e) {
      const box = $("#blocked");
      const issues = e.body?.detail?.issues || [];
      box.innerHTML = `<strong>${esc(e.message)}</strong>${issues.length ? `<ul style="margin:6px 0 0 18px;padding:0">${issues.map((i) => `<li>${esc(issueTitle(i.code))}: ${esc(i.message)}</li>`).join("")}</ul>` : ""}`;
      box.hidden = false;
      box.scrollIntoView({ block: "nearest" });
      if (e.status === 409) $("#reason").focus();
      $$("[data-act]").forEach((b) => (b.disabled = false));
    }
  };
  form.addEventListener("submit", (e) => { e.preventDefault(); submit(true); });
  $('[data-act="reject"]').addEventListener("click", () => submit(false));

  viewKeys = (e) => {
    if (typing(e) || e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === "a") { e.preventDefault(); submit(true); }
    else if (k === "r") { e.preventDefault(); $("#reason").focus(); toast("Add a reason, then press Reject"); }
    else if ((k === "j" || k === "k") && queue.length) {
      const step = k === "j" ? 1 : -1;
      const next = queue[(Math.max(pos, 0) + step + queue.length) % queue.length];
      location.hash = `#/review/${next.id}`;
    }
  };
  document.addEventListener("keydown", viewKeys);
}

// Wrap each extracted value's location in a <mark>; where spans overlap, the earlier one wins.
function highlight(text, spans) {
  const all = Object.entries(spans).flatMap(([f, list]) => list.map(([s, e]) => ({ s, e, f }))).sort((a, b) => a.s - b.s || b.e - a.e);
  let out = "", at = 0;
  for (const m of all) {
    if (m.s < at) continue;
    out += esc(text.slice(at, m.s)) + `<mark class="ev" data-f="${m.f}">${esc(text.slice(m.s, m.e))}</mark>`;
    at = m.e;
  }
  return out + esc(text.slice(at));
}

function wireEvidence() {
  const textEl = $("#doc-text");
  const show = (key, scroll) => {
    $$(".field").forEach((f) => f.classList.toggle("hot", f.dataset.field === key));
    if (!textEl) return;
    const marks = $$(`mark[data-f="${key}"]`, textEl);
    $$("mark.ev", textEl).forEach((m) => m.classList.toggle("on", m.dataset.f === key));
    textEl.classList.toggle("focus", marks.length > 0);
    const box = $("#viewer");
    if (scroll && marks[0] && box) {  // scroll the document pane only, never the page
      const mr = marks[0].getBoundingClientRect(), br = box.getBoundingClientRect();
      if (mr.top < br.top + 40 || mr.bottom > br.bottom - 40) {
        box.scrollTo({ top: box.scrollTop + mr.top - br.top - br.height / 2,
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      }
    }
  };
  const clear = () => {
    $$(".field.hot").forEach((f) => f.classList.remove("hot"));
    if (textEl) { textEl.classList.remove("focus"); $$("mark.on", textEl).forEach((m) => m.classList.remove("on")); }
  };
  $$(".field").forEach((f) => {
    f.addEventListener("mouseenter", () => show(f.dataset.field, true));
    f.addEventListener("mouseleave", () => { if (!f.contains(document.activeElement)) clear(); });
    f.addEventListener("focusin", () => show(f.dataset.field, true));
    f.addEventListener("focusout", clear);
  });
  $$(".issues li[data-for]").forEach((li) => {
    li.addEventListener("mouseenter", () => show(li.dataset.for, true));
    li.addEventListener("mouseleave", clear);
  });
  if (textEl) textEl.addEventListener("click", (e) => {
    const m = e.target.closest("mark.ev");
    if (m) $(`#f-${m.dataset.f}`)?.focus();
  });
}

// ---------------------------------------------------------------- benchmarks
async function viewBenchmarks(_r, live) {
  let b;
  try { b = await api("/benchmarks"); } catch (e) {
    if (!live()) return;
    main.innerHTML = `<div class="page-head"><div><h1>Benchmarks</h1></div></div><div class="panel empty"><h2>No results summary yet</h2>
      <p>Run <span class="mono">python evals/build_dashboard_data.py</span> to collect the evaluation results, then reload.</p></div>`;
    return;
  }
  if (!live()) return;
  const f = b.sroie_finetune, zs = f.zero_shot, ft = f.fine_tuned;
  const fieldNames = { company: "Company", date: "Date", address: "Address", total: "Total" };

  main.innerHTML = `
  <div class="page-head"><div><h1>Benchmarks</h1>
    <p>How well DocFlow reads documents, measured on data it was not tuned on. Every number here comes from result files in the repository.</p></div></div>

  <div class="lede">
    <section class="panel headline">
      <h2>Real receipts: SROIE test set</h2>
      <div class="big"><strong class="num">${pts(ft.mean)}%</strong><span class="from num">from <s>${pts(zs.mean)}%</s></span></div>
      <p>Field accuracy of the fine-tuned vision model on all ${f.receipts} held-out scanned receipts (ICDAR 2019), averaged over company, date, address and total. LoRA fine-tuning on the ${f.train_receipts} training receipts took ${f.training_minutes} minutes on one ${esc(f.hardware.split(", ").pop())}.</p>
      <dl class="facts">
        <div><dt>95% confidence interval</dt><dd class="num">${pts(f.ci95.fine_tuned[0])}–${pts(f.ci95.fine_tuned[1])}%</dd></div>
        <div><dt>All four fields right</dt><dd class="num">${pts(ft.all_four)}% <span class="muted small">from ${pts(zs.all_four)}%</span></dd></div>
        <div><dt>Strict exact match</dt><dd class="num">${pts(f.strict.fine_tuned.mean)}% <span class="muted small">from ${pts(f.strict.zero_shot.mean)}%</span></dd></div>
      </dl>
    </section>
    <section class="panel">
      <header><div><h2>By field</h2><p>Before and after fine-tuning, same ${f.receipts} receipts</p></div>
        <div class="legend"><span><i style="background:var(--line-strong)"></i>Zero-shot</span><span><i style="background:var(--accent)"></i>Fine-tuned</span></div></header>
      <div class="panel-body">${fieldChart(Object.keys(fieldNames).map((k) => ({ label: fieldNames[k], a: zs[k], b: ft[k] })))}</div>
    </section>
  </div>

  <section class="panel">
    <header><div><h2>Against published image-only models</h2><p>Field-level F1 on SROIE for models that read the image without OCR input</p></div></header>
    <div class="panel-body">
      ${compareChart([...b.published.map((p) => ({ label: `${p.model} (${p.year})`, v: p.f1 })), { label: "DocFlow, fine-tuned 3B (strict)", v: f.strict.fine_tuned.mean, ours: true }].sort((x, y) => y.v - x.v))}
      <p class="note">DocFlow is shown with its strict exact-match score, the closest of its numbers to the published metric, but the two are not identical, so read this as "in the same range", not a ranking. Models that are given the dataset's own OCR text score 96–98 and are not comparable.</p>
    </div>
  </section>

  <div class="grid-3">
    <section class="panel" style="grid-column: span 2">
      <header><div><h2>Ways of reading, without fine-tuning</h2><p>100 test receipts, run on a laptop with Ollama</p></div></header>
      <div class="table-wrap"><table>
        <thead><tr><th>Method</th><th class="r">Company</th><th class="r">Date</th><th class="r">Address</th><th class="r">Total</th><th class="r">Mean</th><th class="r">Seconds each</th></tr></thead>
        <tbody>${b.sroie_local.map((m) => `<tr><td>${esc(m.label)}</td>${["company", "date", "address", "total"].map((k) => `<td class="r num">${pts(m.fields[k])}</td>`).join("")}
          <td class="r num"><strong>${pts(m.mean)}</strong></td><td class="r num muted">${m.seconds || "<0.1"}</td></tr>`).join("")}</tbody></table></div>
    </section>
    <section class="panel">
      <header><div><h2>Cost of fine-tuning</h2><p>One free Colab T4</p></div></header>
      <dl class="kv"><dt>Training time</dt><dd class="num">${f.training_minutes} min</dd>
        <dt>Parameters trained</dt><dd class="num">${pct(f.trained_share, 2)}</dd>
        <dt>Per receipt, before</dt><dd class="num">${f.seconds_per_receipt.zero_shot} s</dd>
        <dt>Per receipt, after</dt><dd class="num">${f.seconds_per_receipt.fine_tuned} s</dd></dl>
    </section>
  </div>

  <section class="panel" style="margin-top:18px">
    <header><div><h2>Approve-or-review decisions on invoices written by someone else</h2>
      <p>40 invoices per set, half with a planted fault. A false approval is a faulty invoice DocFlow let through.</p></div></header>
    <div class="table-wrap"><table>
      <thead><tr><th>Run</th><th class="r">Right decision</th><th class="r">False approvals</th><th class="r">Sent to review needlessly</th></tr></thead>
      <tbody>${b.independent.map((x) => `<tr><td>${esc(x.label)}</td><td class="r num"><strong>${pct(x.decision_accuracy)}</strong></td>
        <td class="r num ${x.false_approvals ? "sev error" : ""}">${x.false_approvals} of ${x.faulty}</td><td class="r num">${x.unnecessary_reviews} of ${x.valid}</td></tr>`).join("")}</tbody></table></div>
    <p class="note" style="margin:0 18px 18px">"Set 2, after fixes" was re-run after changes made by looking at that set, so it is not an unbiased score. Set 5 was seen for the first time and is the honest figure.</p>
  </section>`;
}

function fieldChart(rows) {
  const W = 520, row = 44, left = 78, right = 46, H = rows.length * row + 4;
  const x = (v) => left + (W - left - right) * v;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Accuracy by field before and after fine-tuning">
    ${[0, .25, .5, .75, 1].map((t) => `<line class="grid" x1="${x(t)}" x2="${x(t)}" y1="0" y2="${H - 4}"/>`).join("")}
    ${rows.map((r, i) => {
      const y = i * row + 6;
      return `<text x="0" y="${y + 19}">${esc(r.label)}</text>
        <rect class="zs" x="${left}" y="${y}" width="${x(r.a) - left}" height="13" rx="2"><title>Zero-shot ${pts(r.a)}%</title></rect>
        <rect class="ft" x="${left}" y="${y + 16}" width="${x(r.b) - left}" height="13" rx="2"><title>Fine-tuned ${pts(r.b)}%</title></rect>
        <text x="${x(r.a) + 6}" y="${y + 11}" class="num">${pts(r.a)}</text>
        <text x="${x(r.b) + 6}" y="${y + 27}" class="val num">${pts(r.b)}</text>`;
    }).join("")}
  </svg>`;
}

function compareChart(rows) {
  const W = 1100, row = 30, left = 250, right = 60, H = rows.length * row;
  const lo = 0.7, x = (v) => left + (W - left - right) * ((v - lo) / (1 - lo));
  return `<svg class="chart" viewBox="0 0 ${W} ${H + 22}" role="img" aria-label="Published F1 scores compared with DocFlow">
    ${[0.7, 0.8, 0.9, 1].map((t) => `<line class="grid" x1="${x(t)}" x2="${x(t)}" y1="0" y2="${H}"/><text x="${x(t)}" y="${H + 16}" text-anchor="middle">${t * 100}</text>`).join("")}
    ${rows.map((r, i) => {
      const y = i * row + 6;
      return `<text x="0" y="${y + 13}" class="${r.ours ? "lab-ours" : ""}">${esc(r.label)}</text>
        <rect class="${r.ours ? "ours" : "pub"}" x="${left}" y="${y}" width="${Math.max(2, x(r.v) - left)}" height="17" rx="2"/>
        <text x="${x(r.v) + 6}" y="${y + 13}" class="val num">${pts(r.v)}</text>`;
    }).join("")}
  </svg>`;
}

// ---------------------------------------------------------------- system
async function viewSystem(_r, live) {
  const h = await api("/health");
  if (!live()) return;
  main.innerHTML = `
  <div class="page-head"><div><h1>System</h1><p>What is reading your documents and how to connect other tools.</p></div></div>
  <div class="two">
    <section class="panel">
      <header><h2>Reading engine</h2><span class="pill approved">Running</span></header>
      <dl class="kv">
        <dt>Text documents</dt><dd>${esc(h.model || "None: rules only")}</dd>
        <dt>Provider</dt><dd>${esc(h.provider || "–")}</dd>
        <dt>Photos and scans</dt><dd>${h.images_supported ? esc(h.vision_model) + (h.vision_model !== h.model ? "" : " (same model)") : "Not available without a model"}</dd>
        <dt>Largest upload</dt><dd class="num">${h.max_upload_mb} MB</dd>
        <dt>File types</dt><dd>PDF, Excel, CSV, text, JPG, PNG</dd>
      </dl>
    </section>
    <section class="panel">
      <header><h2>How each document is processed</h2></header>
      <ol class="steps">
        <li><b>Screen</b> for hidden instructions aimed at the model.</li>
        <li><b>Extract</b> the fields with the model, and separately with the rules engine.</li>
        <li><b>Cross-check</b> every value against the document text and against the rules result.</li>
        <li><b>Validate</b> the arithmetic, dates, VAT and duplicates.</li>
        <li><b>Retry</b> once if the model was unsure, then approve, reject or send to a person.</li>
      </ol>
    </section>
  </div>
  <section class="panel" style="margin-top:18px">
    <header><div><h2>Connect an AI agent</h2><p>DocFlow runs as an MCP server, so an agent such as Claude Desktop can process the inbox folder. Agents can approve only when no problems remain; overrides stay with people.</p></div></header>
    <pre class="code">{
  "mcpServers": {
    "docflow": {
      "command": "python",
      "args": ["-m", "docflow.mcp_server"],
      "env": { "DOCFLOW_INBOX": "inbox" }
    }
  }
}</pre>
  </section>`;
}

// ---------------------------------------------------------------- uploads
async function uploadFiles(files) {
  files = [...files];
  if (!files.length) return;
  const panel = $("#uploads"), list = $("#upload-list");
  panel.hidden = false;
  const items = files.map((f) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="name">${esc(f.name)}</span><span class="spinner" aria-hidden="true"></span><span class="state">Waiting</span>`;
    list.prepend(li);
    return li;
  });
  const limit = (state.health?.max_upload_mb || 5) * 1024 * 1024;
  let last = null;
  for (const [i, f] of files.entries()) {
    const li = items[i], st = $(".state", li);
    if (f.size > limit) { $(".spinner", li).remove(); st.textContent = `Larger than ${limit / 1048576} MB, not uploaded`; st.classList.add("err"); continue; }
    st.textContent = "Reading and checking…";
    try {
      const fd = new FormData(); fd.append("file", f);
      const doc = await api("/documents", { method: "POST", body: fd });
      last = doc;
      $(".spinner", li).replaceWith(Object.assign(document.createElement("span"), { innerHTML: statusPill(doc.status) }));
      st.innerHTML = `${esc(DECISION[doc.decision])}${doc.result.issues.length ? ` · ${doc.result.issues.length} check${doc.result.issues.length > 1 ? "s" : ""} fired` : ""} · <a href="#/review/${doc.id}">Open</a>`;
    } catch (e) {
      $(".spinner", li).remove();
      st.textContent = e.message; st.classList.add("err");
    }
  }
  await refreshShell();
  if (last) {
    const r = parseHash();
    if (r.name === "overview" || r.name === "documents" || (r.name === "review" && !r.id)) render();
  }
}

// ---------------------------------------------------------------- startup
function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("docflow-theme"); } catch { /* storage blocked */ }
  if (saved) document.documentElement.dataset.theme = saved;
  $("#theme").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("docflow-theme", document.documentElement.dataset.theme); } catch { /* ignore */ }
  });
}

function init() {
  initTheme();
  const input = $("#file-input");
  $("#upload-btn").addEventListener("click", () => input.click());
  input.addEventListener("change", () => { uploadFiles(input.files); input.value = ""; });
  $("#uploads-close").addEventListener("click", () => { $("#uploads").hidden = true; $("#upload-list").innerHTML = ""; });
  $("#menu").addEventListener("click", () => document.body.classList.toggle("nav-open"));

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-upload]")) input.click();
    const row = e.target.closest("tr[data-href]");
    if (row && !e.target.closest("a")) location.hash = row.dataset.href;
  });
  document.addEventListener("keydown", (e) => {
    const row = e.target.closest?.("tr[data-href]");
    if (row && e.key === "Enter") location.hash = row.dataset.href;
    if (e.key === "/" && !typing(e)) { e.preventDefault(); $("#search-input").focus(); }
    if (e.key === "Escape" && typing(e)) e.target.blur();
  });
  $("#search").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#search-input").value.trim();
    location.hash = `#/documents${q ? `?q=${encodeURIComponent(q)}` : ""}`;
  });
  $("#search-input").addEventListener("focus", () => { if (parseHash().name !== "documents") location.hash = "#/documents"; });

  // Drag files anywhere on the page to upload them.
  let depth = 0;
  const overlay = $("#drop-overlay");
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
  window.addEventListener("dragenter", (e) => { if (hasFiles(e)) { depth++; overlay.hidden = false; } });
  window.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; overlay.hidden = true; } });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("drop", (e) => { if (!hasFiles(e)) return; e.preventDefault(); depth = 0; overlay.hidden = true; uploadFiles(e.dataTransfer.files); });

  window.addEventListener("hashchange", render);
  if (!location.hash) history.replaceState(null, "", "#/overview");
  loadHealth();
  refreshShell();
  render();
}

init();
