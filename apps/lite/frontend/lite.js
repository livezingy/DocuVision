const API_BASE = window.LITE_API_BASE || "/api/v1/lite";

if (window.pdfjsLib) {
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
}

const DEFAULT_OPTIONS = {
  mode: "smart",
  extractTables: true,
  extractText: true,
  pages: "",
  engine: "auto",
  flavor: "auto",
  ocrEngine: "auto",
  transformer: "off",
  languages: "eng",
  paramMode: "auto",
  customParams: null,
  scoreThreshold: 0.5,
};

const state = {
  file: null,
  profile: null,
  result: null,
  currentPage: 1,
  totalPages: 1,
  pdfDoc: null,
  previewUrl: null,
  options: { ...DEFAULT_OPTIONS },
};

const $ = (id) => document.getElementById(id);

const els = {
  uploadZone: $("uploadZone"),
  fileInput: $("fileInput"),
  queueList: $("queueList"),
  queueCount: $("queueCount"),
  runBtn: $("runBtn"),
  analysisOptionsBtn: $("analysisOptionsBtn"),
  previewPlaceholder: $("previewPlaceholder"),
  previewCanvas: $("previewCanvas"),
  previewImage: $("previewImage"),
  prevPage: $("prevPage"),
  nextPage: $("nextPage"),
  currentPage: $("currentPage"),
  totalPages: $("totalPages"),
  documentProfile: $("documentProfile"),
  profilePageSelect: $("profilePageSelect"),
  profileContent: $("profileContent"),
  applyProfileBtn: $("applyProfileBtn"),
  contentText: $("contentText"),
  contentTableList: $("contentTableList"),
  resultJson: $("resultJson"),
  exportJsonBtn: $("exportJsonBtn"),
  exportCsvBtn: $("exportCsvBtn"),
  exportXlsxBtn: $("exportXlsxBtn"),
  statusDot: $("statusDot"),
  statusEngines: $("statusEngines"),
  statusMessage: $("statusMessage"),
  apiVersion: $("apiVersion"),
  modal: $("analysisOptionsModal"),
};

function setStatus(msg) {
  els.statusMessage.textContent = msg;
}

function defaultOptions() {
  return { ...DEFAULT_OPTIONS, customParams: null };
}

async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    els.apiVersion.textContent = data.api_version || "—";
    els.statusDot.classList.add("online");
    const engines = data.engines || {};
    const parts = Object.entries(engines).map(([k, v]) => `${k}${v.available ? " ✓" : " ✗"}`);
    els.statusEngines.textContent = parts.join(" · ");
  } catch {
    els.statusEngines.textContent = "Backend unreachable";
  }
}

async function fetchEnginesCatalog() {
  try {
    const res = await fetch(`${API_BASE}/engines`);
    const data = await res.json();
    const tableSelect = $("optEngine");
    tableSelect.innerHTML = '<option value="auto">Auto</option>';
    (data.engines || []).forEach((e) => {
      if (["pdfplumber", "camelot"].includes(e.id)) {
        const opt = document.createElement("option");
        opt.value = e.id;
        opt.textContent = e.label;
        tableSelect.appendChild(opt);
      }
    });
  } catch {
    /* keep defaults */
  }
}

function updateQueueUI() {
  els.queueList.innerHTML = "";
  if (!state.file) {
    els.queueCount.textContent = "0";
    return;
  }
  els.queueCount.textContent = "1";
  const item = document.createElement("div");
  item.className = "queue-item";
  item.innerHTML = `<div class="queue-item-name">${escapeHtml(state.file.name)}</div>
    <div class="queue-item-meta">${formatBytes(state.file.size)} · ${state.profile?.input?.detected_file_type || "pending"}</div>`;
  els.queueList.appendChild(item);
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function handleFile(file) {
  if (!file) return;
  state.file = file;
  state.result = null;
  state.profile = null;
  state.currentPage = 1;
  state.pdfDoc = null;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);

  els.runBtn.disabled = false;
  updateQueueUI();
  renderResults(null);
  setStatus("Analyzing document profile…");

  await renderPreview(file);
  await fetchProfile(file);
  updateQueueUI();
}

async function renderPreview(file) {
  els.previewPlaceholder.classList.add("hidden");
  els.previewCanvas.classList.add("hidden");
  els.previewImage.classList.add("hidden");

  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  state.previewUrl = URL.createObjectURL(file);

  if (isPdf && window.pdfjsLib) {
    const buf = await file.arrayBuffer();
    state.pdfDoc = await pdfjsLib.getDocument({ data: buf }).promise;
    state.totalPages = state.pdfDoc.numPages;
    els.totalPages.textContent = state.totalPages;
    els.currentPage.textContent = state.currentPage;
    updatePageButtons();
    await renderPdfPage(state.currentPage);
  } else if (file.type.startsWith("image/") || /\.(png|jpe?g|bmp|tiff?)$/i.test(file.name)) {
    state.totalPages = 1;
    state.currentPage = 1;
    els.totalPages.textContent = "1";
    els.currentPage.textContent = "1";
    els.previewImage.src = state.previewUrl;
    els.previewImage.classList.remove("hidden");
    els.prevPage.disabled = true;
    els.nextPage.disabled = true;
  } else {
    els.previewPlaceholder.textContent = file.name;
    els.previewPlaceholder.classList.remove("hidden");
  }
}

async function renderPdfPage(pageNum) {
  if (!state.pdfDoc) return;
  const page = await state.pdfDoc.getPage(pageNum);
  const viewport = page.getViewport({ scale: 1.2 });
  const canvas = els.previewCanvas;
  const ctx = canvas.getContext("2d");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: ctx, viewport }).promise;
  canvas.classList.remove("hidden");
  els.currentPage.textContent = pageNum;
}

function updatePageButtons() {
  els.prevPage.disabled = state.currentPage <= 1;
  els.nextPage.disabled = state.currentPage >= state.totalPages;
}

async function fetchProfile(file) {
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(`${API_BASE}/analyze/profile`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      const msg = data?.error?.message || data?.detail?.error?.message || res.statusText;
      setStatus(`Profile error: ${msg}`);
      els.documentProfile.classList.add("hidden");
      return;
    }
    state.profile = data;
    renderDocumentProfile();
    setStatus("Profile ready — configure options or run extraction");
  } catch (err) {
    setStatus(`Profile failed: ${err.message}`);
    els.documentProfile.classList.add("hidden");
  }
}

function getCurrentPageProfile() {
  if (!state.profile?.pages?.length) return null;
  const pageNum = parseInt(els.profilePageSelect.value, 10) || state.currentPage;
  return state.profile.pages.find((p) => p.page === pageNum) || state.profile.pages[0];
}

function renderDocumentProfile() {
  const profile = state.profile;
  if (!profile) {
    els.documentProfile.classList.add("hidden");
    return;
  }
  els.documentProfile.classList.remove("hidden");

  els.profilePageSelect.innerHTML = "";
  if (profile.scan_profile) {
    els.profilePageSelect.classList.add("hidden");
    els.profileContent.innerHTML = `
      <div class="scan-profile-msg">
        <p>${escapeHtml(profile.scan_profile.message)}</p>
        <p style="margin-top:8px">Recommended OCR: <strong>${escapeHtml(profile.scan_profile.recommended_ocr)}</strong></p>
        <p>Transformer: ${profile.scan_profile.transformer_available ? "available" : "not installed"}</p>
      </div>`;
    return;
  }

  els.profilePageSelect.classList.remove("hidden");
  profile.pages.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.page;
    opt.textContent = p.page;
    if (p.page === state.currentPage) opt.selected = true;
    els.profilePageSelect.appendChild(opt);
  });

  renderPageProfileDetail(getCurrentPageProfile());
}

function renderPageProfileDetail(pageProf) {
  if (!pageProf) {
    els.profileContent.innerHTML = "<p class='scan-profile-msg'>No page data.</p>";
    return;
  }
  const cls = pageProf.table_type === "bordered" ? "badge-bordered" : "badge-unbordered";
  const scorePct = Math.round((pageProf.table_type_score || 0) * 100);
  const cd = pageProf.classification_detail || {};
  const ty = pageProf.typography_summary || {};
  const sr = pageProf.suggested_routing || {};

  els.profileContent.innerHTML = `
    <div class="profile-grid">
      <div class="profile-card">
        <h5>Classification</h5>
        <span class="badge ${cls}">${escapeHtml(pageProf.table_type)}</span>
        <div class="score-bar"><div class="score-bar-fill" style="width:${scorePct}%"></div></div>
        <div>Score: ${pageProf.table_type_score?.toFixed(2) ?? "—"} · H:${cd.h_lines ?? 0} V:${cd.v_lines ?? 0}</div>
      </div>
      <div class="profile-card">
        <h5>Routing suggestion</h5>
        <div>Engine: <strong>${escapeHtml(sr.engine)}</strong></div>
        <div>Flavor: <strong>${escapeHtml(sr.flavor)}</strong></div>
        <div>Params: ${escapeHtml(sr.param_mode || "auto")}</div>
      </div>
    </div>
    <details class="profile-details">
      <summary>Typography &amp; spacing</summary>
      <dl>
        <dt>Char width (mode)</dt><dd>${ty.mode_char_width_pt} pt</dd>
        <dt>Char height (mode)</dt><dd>${ty.mode_char_height_pt} pt</dd>
        <dt>Line height (mode)</dt><dd>${ty.mode_line_height_pt} pt</dd>
        <dt>Line spacing (mode)</dt><dd>${ty.mode_line_spacing_pt} pt</dd>
        <dt>Text lines / chars</dt><dd>${ty.total_lines} / ${ty.total_chars}</dd>
      </dl>
    </details>
    <details class="profile-details">
      <summary>Line analysis</summary>
      <dl>
        <dt>Method</dt><dd>${escapeHtml(cd.method || "—")}</dd>
        <dt>Line concentration</dt><dd>${cd.line_concentration != null ? cd.line_concentration.toFixed(2) : "—"}</dd>
        <dt>Area ratio</dt><dd>${cd.area_ratio != null ? cd.area_ratio.toFixed(2) : "—"}</dd>
        <dt>Direction balance</dt><dd>${cd.direction_balance != null ? cd.direction_balance.toFixed(2) : "—"}</dd>
      </dl>
    </details>`;
}

function applyProfileToAdvanced() {
  const pageProf = getCurrentPageProfile();
  if (!pageProf?.computed_params) return;
  state.options.mode = "advanced";
  state.options.paramMode = "custom";
  state.options.engine = pageProf.suggested_routing?.engine || "auto";
  state.options.flavor = pageProf.suggested_routing?.flavor || "auto";
  state.options.customParams = pageProf.computed_params;
  openModal();
  syncModalFromState();
  setActiveModalTab("advanced");
}

function syncModalFromState() {
  document.querySelector(`input[name="extractMode"][value="${state.options.mode}"]`).checked = true;
  $("optExtractTables").checked = state.options.extractTables;
  $("optExtractText").checked = state.options.extractText;
  $("optPages").value = state.options.pages || "";
  $("optEngine").value = state.options.engine;
  $("optFlavor").value = state.options.flavor;
  $("optOcrEngine").value = state.options.ocrEngine;
  $("optTransformer").value = state.options.transformer;
  $("optLanguages").value = state.options.languages;
  $("optScoreThreshold").value = state.options.scoreThreshold;
  document.querySelector(`input[name="paramMode"][value="${state.options.paramMode}"]`).checked = true;

  const cp = state.options.customParams || getCurrentPageProfile()?.computed_params;
  $("paramsCamelotLattice").value = cp ? JSON.stringify(cp.camelot_lattice || {}, null, 2) : "{}";
  $("paramsCamelotStream").value = cp ? JSON.stringify(cp.camelot_stream || {}, null, 2) : "{}";
  $("paramsPdfplumberBordered").value = cp ? JSON.stringify(cp.pdfplumber_bordered || {}, null, 2) : "{}";
  $("paramsPdfplumberUnbordered").value = cp ? JSON.stringify(cp.pdfplumber_unbordered || {}, null, 2) : "{}";

  updateModalProfileSummary();
  updateAdvancedControls();
}

function updateModalProfileSummary() {
  const pp = getCurrentPageProfile();
  const el = $("modalProfileSummary");
  if (!pp) {
    el.textContent = state.profile?.scan_profile?.message || "Upload a file to see suggested parameters.";
    return;
  }
  el.textContent = `Page ${pp.page}: ${pp.table_type} (score ${pp.table_type_score?.toFixed(2)}) → ${pp.suggested_routing?.engine} / ${pp.suggested_routing?.flavor}`;
}

function updateAdvancedControls() {
  const advanced = state.options.mode === "advanced";
  const custom = state.options.paramMode === "custom";
  $("enginesHint").textContent = advanced
    ? "Override Smart routing with explicit engine settings."
    : "Smart mode uses automatic engine selection.";
  ["optEngine", "optFlavor", "optOcrEngine", "optTransformer", "optLanguages"].forEach((id) => {
    $(id).disabled = !advanced;
  });
  ["paramsCamelotLattice", "paramsCamelotStream", "paramsPdfplumberBordered", "paramsPdfplumberUnbordered"].forEach((id) => {
    $(id).disabled = !custom;
  });
}

function readOptionsFromModal() {
  state.options.mode = document.querySelector('input[name="extractMode"]:checked').value;
  state.options.extractTables = $("optExtractTables").checked;
  state.options.extractText = $("optExtractText").checked;
  state.options.pages = $("optPages").value.trim();
  state.options.engine = $("optEngine").value;
  state.options.flavor = $("optFlavor").value;
  state.options.ocrEngine = $("optOcrEngine").value;
  state.options.transformer = $("optTransformer").value;
  state.options.languages = $("optLanguages").value.trim() || "eng";
  state.options.paramMode = document.querySelector('input[name="paramMode"]:checked').value;
  state.options.scoreThreshold = parseFloat($("optScoreThreshold").value) || 0.5;

  if (state.options.paramMode === "custom") {
    try {
      state.options.customParams = {
        camelot_lattice: JSON.parse($("paramsCamelotLattice").value || "{}"),
        camelot_stream: JSON.parse($("paramsCamelotStream").value || "{}"),
        pdfplumber_bordered: JSON.parse($("paramsPdfplumberBordered").value || "{}"),
        pdfplumber_unbordered: JSON.parse($("paramsPdfplumberUnbordered").value || "{}"),
      };
    } catch {
      throw new Error("Invalid JSON in custom parameters");
    }
  } else {
    state.options.customParams = null;
  }
}

function openModal() {
  syncModalFromState();
  els.modal.classList.add("active");
}

function closeModal() {
  els.modal.classList.remove("active");
}

function setActiveModalTab(tab) {
  document.querySelectorAll(".modal-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });
  document.querySelectorAll(".modal-tab-content").forEach((c) => {
    c.classList.toggle("active", c.id === `${tab}Tab`);
  });
}

function renderTable(table, index) {
  const wrap = document.createElement("div");
  wrap.className = "table-card";
  const header = document.createElement("div");
  header.className = "table-card-header";
  header.textContent = `Table ${index + 1} · page ${table.page} · score ${(table.score || 0).toFixed(2)} · ${table.source || ""}`;
  wrap.appendChild(header);

  const rows = [];
  if (table.headers?.length) rows.push(table.headers);
  rows.push(...(table.rows || []));

  if (!rows.length) {
    const empty = document.createElement("p");
    empty.style.padding = "10px";
    empty.textContent = "(empty)";
    wrap.appendChild(empty);
    return wrap;
  }

  const tableEl = document.createElement("table");
  tableEl.className = "extracted-table";
  rows.forEach((row, ri) => {
    const tr = document.createElement("tr");
    row.forEach((cell) => {
      const cellEl = document.createElement(ri === 0 && table.headers?.length ? "th" : "td");
      cellEl.textContent = cell ?? "";
      tr.appendChild(cellEl);
    });
    tableEl.appendChild(tr);
  });
  wrap.appendChild(tableEl);
  return wrap;
}

function buildFullText(data) {
  if (data.ocr?.length) {
    return data.ocr.map((b) => b.text).join("\n");
  }
  if (data.text_preview) {
    return data.text_preview;
  }
  if (data.tables?.length) {
    return (
      data.tables.flatMap((t) => (t.rows || []).map((r) => r.join("\t"))).join("\n") || "No plain text."
    );
  }
  return "No text content in result.";
}

function renderResults(data) {
  state.result = data;
  els.contentTableList.innerHTML = "";
  els.exportJsonBtn.disabled = true;
  els.exportCsvBtn.disabled = true;
  els.exportXlsxBtn.disabled = true;

  if (!data) {
    els.contentText.textContent = "No text extracted yet.";
    els.resultJson.querySelector("code").textContent = "No result data available";
    return;
  }

  els.contentText.textContent = buildFullText(data);

  (data.tables || []).forEach((t, i) => {
    els.contentTableList.appendChild(renderTable(t, i));
  });

  els.resultJson.querySelector("code").textContent = JSON.stringify(data, null, 2);
  els.exportJsonBtn.disabled = false;
  if (data.exports?.csv) {
    els.exportCsvBtn.disabled = false;
    els.exportXlsxBtn.disabled = false;
  }
}

async function runExtraction() {
  if (!state.file) {
    setStatus("Please upload a file first.");
    return;
  }

  const form = new FormData();
  form.append("file", state.file);
  form.append("mode", state.options.mode);
  form.append("engine", state.options.mode === "advanced" ? state.options.engine : "auto");
  form.append("flavor", state.options.mode === "advanced" ? state.options.flavor : "auto");
  if (state.options.pages) form.append("pages", state.options.pages);
  form.append("score_threshold", String(state.options.scoreThreshold));
  form.append("param_mode", state.options.paramMode);
  if (state.options.paramMode === "custom" && state.options.customParams) {
    form.append("custom_params", JSON.stringify(state.options.customParams));
  }

  els.runBtn.disabled = true;
  setStatus("Extracting…");

  try {
    const res = await fetch(`${API_BASE}/extract/auto`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      const msg = data?.error?.message || data?.detail?.error?.message || res.statusText;
      setStatus(`Error: ${msg}`);
      return;
    }
    renderResults(data);
    setStatus(`Done in ${data.processing_ms} ms — ${data.routing?.engine_used || "n/a"}`);
    setActiveMainTab("content");
    setActiveContentTab(data.tables?.length ? "tables" : "text");
  } catch (err) {
    setStatus(`Request failed: ${err.message}`);
  } finally {
    els.runBtn.disabled = false;
  }
}

function setActiveMainTab(tab) {
  document.querySelectorAll(".result-main-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.mainTab === tab);
  });
  $("contentView").classList.toggle("active", tab === "content");
  $("resultView").classList.toggle("active", tab === "result");
}

function setActiveContentTab(tab) {
  document.querySelectorAll(".content-sub-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.content === tab);
  });
  $("contentTextView").classList.toggle("active", tab === "text");
  $("contentTablesView").classList.toggle("active", tab === "tables");
  $("contentFiguresView").classList.toggle("active", tab === "figures");
}

function initUpload() {
  els.uploadZone.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", () => {
    const f = els.fileInput.files?.[0];
    if (f) handleFile(f);
  });
  els.uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.uploadZone.classList.add("dragover");
  });
  els.uploadZone.addEventListener("dragleave", () => els.uploadZone.classList.remove("dragover"));
  els.uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    els.uploadZone.classList.remove("dragover");
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  });
}

function initPagination() {
  els.prevPage.addEventListener("click", async () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      await renderPdfPage(state.currentPage);
      updatePageButtons();
      if (els.profilePageSelect.options.length) {
        els.profilePageSelect.value = String(state.currentPage);
        renderPageProfileDetail(getCurrentPageProfile());
      }
    }
  });
  els.nextPage.addEventListener("click", async () => {
    if (state.currentPage < state.totalPages) {
      state.currentPage++;
      await renderPdfPage(state.currentPage);
      updatePageButtons();
      if (els.profilePageSelect.options.length) {
        els.profilePageSelect.value = String(state.currentPage);
        renderPageProfileDetail(getCurrentPageProfile());
      }
    }
  });
}

function initProfile() {
  els.profilePageSelect.addEventListener("change", () => {
    const p = parseInt(els.profilePageSelect.value, 10);
    state.currentPage = p;
    if (state.pdfDoc) renderPdfPage(p);
    renderPageProfileDetail(getCurrentPageProfile());
  });
  els.applyProfileBtn.addEventListener("click", applyProfileToAdvanced);
}

function initModal() {
  els.analysisOptionsBtn.addEventListener("click", openModal);
  $("closeAnalysisOptionsBtn").addEventListener("click", closeModal);
  $("cancelOptionsBtn").addEventListener("click", closeModal);
  $("resetOptionsBtn").addEventListener("click", () => {
    state.options = defaultOptions();
    syncModalFromState();
  });
  $("saveOptionsBtn").addEventListener("click", () => {
    try {
      readOptionsFromModal();
      closeModal();
      setStatus("Options applied");
    } catch (err) {
      alert(err.message);
    }
  });

  document.querySelectorAll(".modal-tab").forEach((btn) => {
    btn.addEventListener("click", () => setActiveModalTab(btn.dataset.tab));
  });

  document.querySelectorAll('input[name="extractMode"]').forEach((el) => {
    el.addEventListener("change", () => {
      state.options.mode = document.querySelector('input[name="extractMode"]:checked').value;
      updateAdvancedControls();
    });
  });
  document.querySelectorAll('input[name="paramMode"]').forEach((el) => {
    el.addEventListener("change", () => {
      state.options.paramMode = document.querySelector('input[name="paramMode"]:checked').value;
      updateAdvancedControls();
    });
  });

  els.modal.addEventListener("click", (e) => {
    if (e.target === els.modal) closeModal();
  });
}

function initResultsTabs() {
  document.querySelectorAll(".result-main-tab").forEach((btn) => {
    btn.addEventListener("click", () => setActiveMainTab(btn.dataset.mainTab));
  });
  document.querySelectorAll(".content-sub-tab").forEach((btn) => {
    btn.addEventListener("click", () => setActiveContentTab(btn.dataset.content));
  });

  $("copyJsonBtn").addEventListener("click", () => {
    if (state.result) navigator.clipboard.writeText(JSON.stringify(state.result, null, 2));
  });

  $("exportJsonBtn").addEventListener("click", () => {
    if (!state.result) return;
    const blob = new Blob([JSON.stringify(state.result, null, 2)], { type: "application/json" });
    downloadBlob(blob, "lite-result.json");
  });
  $("exportCsvBtn").addEventListener("click", () => {
    if (state.result?.exports?.csv) window.open(state.result.exports.csv, "_blank");
  });
  $("exportXlsxBtn").addEventListener("click", () => {
    if (state.result?.exports?.xlsx) window.open(state.result.exports.xlsx, "_blank");
  });
}

function downloadBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function initPanelLayout() {
  if (typeof initThreePanelResize === "function") {
    initThreePanelResize({
      left: $("leftPanel"),
      center: $("centerPanel"),
      right: $("rightPanel"),
      leftHandle: $("leftPanelResizeHandle"),
      rightHandle: $("rightPanelResizeHandle"),
      leftMin: 180,
      leftMax: 400,
      rightMin: 250,
      rightMax: 800,
    });
  }
}

function init() {
  initUpload();
  initPagination();
  initProfile();
  initModal();
  initResultsTabs();
  initPanelLayout();
  $("helpBtn")?.addEventListener("click", () => window.open("/docs", "_blank"));
  els.runBtn.addEventListener("click", runExtraction);
  fetchHealth();
  fetchEnginesCatalog();
  setStatus("Ready");
}

init();
