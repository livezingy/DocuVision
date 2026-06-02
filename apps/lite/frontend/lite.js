const API_BASE = window.LITE_API_BASE || "/api/v1/lite";
const LITE_SESSION_KEY = "docuvision.lite.session.v1";
const LITE_FILE_DB = "docuvision-lite-files";
const LITE_FILE_STORE = "files";
/** When true, image/scan PDF table extraction (Transformer) is disabled; text OCR only. */
const RASTER_TABLES_FROZEN = true;

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
  transformer: "transformer",
  languages: "eng",
  paramMode: "auto",
  customParams: null,
  scoreThreshold: 0.5,
};

const state = {
  queue: [],
  activeIndex: -1,
  file: null,
  profile: null,
  result: null,
  currentPage: 1,
  totalPages: 1,
  pdfDoc: null,
  previewUrl: null,
  options: { ...DEFAULT_OPTIONS },
  processing: false,
  previewScale: 1,
  previewBaseScale: 1,
  previewNaturalWidth: 0,
  previewNaturalHeight: 0,
};

function getActiveItem() {
  if (state.activeIndex < 0 || state.activeIndex >= state.queue.length) return null;
  return state.queue[state.activeIndex];
}

function syncActiveFromQueue() {
  const item = getActiveItem();
  state.file = item?.file || null;
  state.profile = item?.profile || null;
  state.result = item?.result || null;
}

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
  previewStage: $("previewStage"),
  previewContainer: $("previewContainer"),
  zoomInBtn: $("zoomInBtn"),
  zoomOutBtn: $("zoomOutBtn"),
  zoomFitBtn: $("zoomFitBtn"),
  zoomLevel: $("zoomLevel"),
  openValidationLink: $("openValidationLink"),
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
  exportMarkdownBtn: $("exportMarkdownBtn"),
  exportDocxBtn: $("exportDocxBtn"),
  statusDot: $("statusDot"),
  statusEngines: $("statusEngines"),
  statusMessage: $("statusMessage"),
  apiVersion: $("apiVersion"),
  saveValidationBtn: $("saveValidationBtn"),
  qualityPanel: $("qualityPanel"),
  contentTransactionsList: $("contentTransactionsList"),
  contentMappedList: $("contentMappedList"),
  modal: $("analysisOptionsModal"),
};

function newQueueItemId() {
  return crypto.randomUUID ? crypto.randomUUID() : `q_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function openLiteFileDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(LITE_FILE_DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(LITE_FILE_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function saveQueueFileBlob(id, file) {
  if (!id || !file) return;
  try {
    const db = await openLiteFileDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(LITE_FILE_STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(LITE_FILE_STORE).put(file, id);
    });
  } catch (err) {
    console.warn("[Lite] Failed to persist file blob:", err);
  }
}

async function loadQueueFileBlob(id) {
  try {
    const db = await openLiteFileDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(LITE_FILE_STORE, "readonly");
      tx.onerror = () => reject(tx.error);
      const req = tx.objectStore(LITE_FILE_STORE).get(id);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null;
  }
}

async function deleteQueueFileBlob(id) {
  if (!id) return;
  try {
    const db = await openLiteFileDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(LITE_FILE_STORE, "readwrite");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.objectStore(LITE_FILE_STORE).delete(id);
    });
  } catch (err) {
    console.warn("[Lite] Failed to delete file blob:", err);
  }
}

function persistSession() {
  try {
    const payload = {
      activeIndex: state.activeIndex,
      options: state.options,
      previewScale: state.previewScale,
      items: state.queue.map((item) => ({
        id: item.id,
        name: item.file?.name || "",
        size: item.file?.size || 0,
        type: item.file?.type || "",
        lastModified: item.file?.lastModified || 0,
        status: item.status,
        statusMessage: item.statusMessage,
        profile: item.profile,
        result: item.result,
      })),
    };
    sessionStorage.setItem(LITE_SESSION_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn("[Lite] Failed to persist session:", err);
  }
}

async function restoreSession() {
  const raw = sessionStorage.getItem(LITE_SESSION_KEY);
  if (!raw) return false;
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(LITE_SESSION_KEY);
    return false;
  }
  if (!payload?.items?.length) return false;

  const restored = [];
  for (const meta of payload.items) {
    const blob = await loadQueueFileBlob(meta.id);
    if (!blob) continue;
    const file = blob instanceof File
      ? blob
      : new File([blob], meta.name || "document", {
          type: meta.type || blob.type || "application/octet-stream",
          lastModified: meta.lastModified || Date.now(),
        });
    restored.push({
      id: meta.id,
      file,
      profile: meta.profile || null,
      result: meta.result || null,
      status: meta.status || "pending",
      statusMessage: meta.statusMessage || "",
    });
  }
  if (!restored.length) return false;

  state.queue = restored;
  state.activeIndex = Math.min(Math.max(payload.activeIndex ?? 0, 0), restored.length - 1);
  state.options = { ...DEFAULT_OPTIONS, ...(payload.options || {}), customParams: payload.options?.customParams ?? null };
  state.previewScale = payload.previewScale || 1;
  syncActiveFromQueue();
  updateQueueUI();
  return true;
}

function formatRoutingSummary(routing) {
  if (!routing) return "n/a";
  const engine = routing.engine_used || routing.requested_engine || "auto";
  const flavor = routing.flavor_used;
  if (flavor && flavor !== "auto" && !String(engine).includes(flavor)) {
    return `${engine} · ${formatFlavorLabel(flavor)}`;
  }
  return engine;
}

function formatFlavorLabel(flavor) {
  const labels = { auto: "Auto", bordered: "Bordered", unbordered: "Unbordered" };
  return labels[flavor] || flavor;
}

function normalizeFlavorFromProfile(flavor) {
  if (!flavor || flavor === "auto") return "auto";
  const f = String(flavor).toLowerCase();
  if (f === "bordered" || f.includes("lines") || f.includes("lattice")) return "bordered";
  if (f === "unbordered" || f.includes("text") || f.includes("stream")) return "unbordered";
  return "auto";
}

function resolveFlavorForApi(engine, flavor) {
  if (!flavor || flavor === "auto") return "auto";
  const eng = (engine || "auto").toLowerCase();
  if (flavor === "bordered") {
    if (eng === "camelot") return "lattice";
    if (eng === "pdfplumber") return "lines";
    return "bordered";
  }
  if (flavor === "unbordered") {
    if (eng === "camelot") return "stream";
    if (eng === "pdfplumber") return "text";
    return "unbordered";
  }
  return flavor;
}

function formatTableSourceLabel(source) {
  if (!source) return "unknown";
  return String(source).replace(/_/g, " · ");
}

function updateZoomUI() {
  const pct = Math.round(state.previewScale * 100);
  if (els.zoomLevel) els.zoomLevel.textContent = `${pct}%`;
  const hasPreview = Boolean(state.file);
  [els.zoomInBtn, els.zoomOutBtn, els.zoomFitBtn].forEach((btn) => {
    if (btn) btn.disabled = !hasPreview;
  });
}

function applyImagePreviewZoom() {
  if (!els.previewImage || els.previewImage.classList.contains("hidden")) return;
  const w = state.previewNaturalWidth * state.previewBaseScale * state.previewScale;
  const h = state.previewNaturalHeight * state.previewBaseScale * state.previewScale;
  els.previewImage.style.width = `${Math.max(1, w)}px`;
  els.previewImage.style.height = `${Math.max(1, h)}px`;
  updateZoomUI();
}

async function refreshPreviewZoom() {
  if (state.pdfDoc) {
    await renderPdfPage(state.currentPage);
  } else if (state.file && !els.previewImage.classList.contains("hidden")) {
    applyImagePreviewZoom();
  }
  updateZoomUI();
}

function setPreviewScale(next, { persist = true } = {}) {
  state.previewScale = Math.min(4, Math.max(0.25, next));
  void refreshPreviewZoom();
  if (persist) persistSession();
}

function resetPreviewScale() {
  state.previewScale = 1;
  void refreshPreviewZoom();
  persistSession();
}

function setStatus(msg) {
  els.statusMessage.textContent = msg;
}

function getDetectedFileType() {
  const fromProfile = state.profile?.input?.detected_file_type;
  if (fromProfile) return fromProfile;
  const name = (state.file?.name || "").toLowerCase();
  if (/\.(png|jpe?g|tiff?|webp|bmp|gif)$/.test(name)) return "image";
  if (name.endsWith(".pdf")) {
    return state.profile?.scan_profile ? "pdf_scan" : "pdf_digital";
  }
  return null;
}

function updateEnginesHint(fileType, extractTables, extractText) {
  const advanced = state.options.mode === "advanced";
  const hintEl = $("enginesHint");
  if (!hintEl) return;
  if (!fileType) {
    hintEl.textContent = "Upload a file to see engine options for its document type.";
    return;
  }
  if (!advanced) {
    hintEl.textContent = "Smart mode uses automatic engine selection.";
    return;
  }
  const parts = [];
  if (fileType === "pdf_digital" && extractTables) {
    parts.push("Digital PDF: choose table engine and flavor.");
  }
  if ((fileType === "image" || fileType === "pdf_scan") && extractText) {
    parts.push("Raster documents: choose OCR engine and languages for text.");
  }
  if ((fileType === "image" || fileType === "pdf_scan") && extractTables && !RASTER_TABLES_FROZEN) {
    parts.push("Raster documents: Transformer extracts tables from photos and scanned PDFs.");
  }
  hintEl.textContent = parts.length ? parts.join(" ") : "Override Smart routing with explicit engine settings.";
}

function updateOptionsVisibility() {
  const fileType = getDetectedFileType();
  const isDigitalPdf = fileType === "pdf_digital";
  const isRaster = fileType === "image" || fileType === "pdf_scan";
  const extractTables = $("optExtractTables")?.checked ?? state.options.extractTables;
  const extractText = $("optExtractText")?.checked ?? state.options.extractText;

  const extractTablesRow = $("extractTablesRow");
  if (isRaster && RASTER_TABLES_FROZEN) {
    if (extractTablesRow) extractTablesRow.hidden = true;
    state.options.extractTables = false;
    const optExtractTables = $("optExtractTables");
    if (optExtractTables) optExtractTables.checked = false;
  } else if (extractTablesRow) {
    extractTablesRow.hidden = false;
  }

  const effectiveExtractTables = isRaster && RASTER_TABLES_FROZEN ? false : extractTables;

  const pagesRow = $("pagesFieldRow");
  if (pagesRow) {
    pagesRow.hidden = !fileType || fileType === "image";
  }

  const advancedTabBtn = document.querySelector('.modal-tab[data-tab="advanced"]');
  const advancedTab = $("advancedTab");
  if (advancedTabBtn) advancedTabBtn.hidden = !isDigitalPdf;
  if (advancedTab && !isDigitalPdf && advancedTab.classList.contains("active")) {
    setActiveModalTab("processing");
  }

  const digitalGroup = $("enginesGroupDigital");
  const textGroup = $("enginesGroupText");
  const transformerGroup = $("enginesGroupTransformer");
  if (digitalGroup) digitalGroup.hidden = !(isDigitalPdf && effectiveExtractTables);
  if (textGroup) textGroup.hidden = !(isRaster && extractText);
  if (transformerGroup) {
    transformerGroup.hidden = !(isRaster && effectiveExtractTables && !RASTER_TABLES_FROZEN);
  }

  const transformerHint = $("transformerHint");
  const scanProfile = state.profile?.scan_profile;
  const transformerAvailable = scanProfile?.transformer_available !== false;
  const optTransformer = $("optTransformer");
  if (optTransformer && transformerGroup && !transformerGroup.hidden) {
    if (!transformerAvailable) {
      optTransformer.disabled = true;
      if (transformerHint) {
        transformerHint.textContent =
          "Table Transformer not installed. pip install docuvision-core[ocr-heavy]";
      }
    } else {
      if (transformerHint) transformerHint.textContent = "";
    }
  } else if (transformerHint) {
    transformerHint.textContent = "";
  }

  updateEnginesHint(fileType, effectiveExtractTables, extractText);
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
  els.queueCount.textContent = String(state.queue.length);
  if (!state.queue.length) {
    els.runBtn.disabled = true;
    return;
  }
  els.runBtn.disabled = false;

  state.queue.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "queue-item" + (index === state.activeIndex ? " active" : "");
    row.innerHTML = `
      <div class="queue-item-body">
        <div class="queue-item-name">${escapeHtml(item.file.name)}</div>
        <div class="queue-item-meta">${formatBytes(item.file.size)} · ${item.status || "pending"}</div>
        <div class="queue-item-status">${escapeHtml(item.statusMessage || "")}</div>
      </div>
      <button type="button" class="queue-item-action" title="Remove" aria-label="Remove">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>`;
    row.querySelector(".queue-item-body").addEventListener("click", () => selectQueueItem(index));
    row.querySelector(".queue-item-action").addEventListener("click", (e) => {
      e.stopPropagation();
      void removeQueueItem(index);
    });
    els.queueList.appendChild(row);
  });
}

async function removeQueueItem(index) {
  if (index < 0 || index >= state.queue.length) return;
  const item = state.queue[index];
  const wasActive = index === state.activeIndex;
  await deleteQueueFileBlob(item.id);
  state.queue.splice(index, 1);

  if (!state.queue.length) {
    state.activeIndex = -1;
    state.file = null;
    state.profile = null;
    state.result = null;
    resetPreviewState();
    els.previewPlaceholder.classList.remove("hidden");
    els.previewCanvas.classList.add("hidden");
    els.previewImage.classList.add("hidden");
    renderDocumentProfile();
    renderResults(null);
    els.runBtn.disabled = true;
    updateQueueUI();
    persistSession();
    setStatus("Queue empty");
    return;
  }

  if (wasActive) {
    state.activeIndex = Math.min(index, state.queue.length - 1);
  } else if (state.activeIndex > index) {
    state.activeIndex--;
  }
  syncActiveFromQueue();
  updateQueueUI();
  if (wasActive && state.file) {
    state.previewScale = 1;
    await renderPreview(state.file);
    if (state.profile) {
      renderDocumentProfile();
      setActiveMainTab("profile");
    } else {
      await fetchProfile(state.file);
    }
    renderResults(state.result);
  }
  persistSession();
  setStatus(`Removed ${item.file.name} from queue`);
}

async function selectQueueItem(index) {
  if (index < 0 || index >= state.queue.length) return;
  state.activeIndex = index;
  syncActiveFromQueue();
  updateQueueUI();
  persistSession();
  if (state.file) {
    state.previewScale = 1;
    await renderPreview(state.file);
    if (state.profile) {
      renderDocumentProfile();
      setActiveMainTab("profile");
    } else {
      await fetchProfile(state.file);
    }
    renderResults(state.result);
  }
}

function createQueueItem(file) {
  return {
    id: newQueueItemId(),
    file,
    profile: null,
    result: null,
    status: "pending",
    statusMessage: "",
  };
}

function enqueueFiles(files) {
  const list = Array.from(files || []);
  const added = [];
  list.forEach((file) => {
    const item = createQueueItem(file);
    state.queue.push(item);
    added.push(item);
  });
  return added;
}

function resetPreviewState() {
  state.currentPage = 1;
  state.pdfDoc = null;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = null;
}

async function addFilesToQueue(files, { replace = false } = {}) {
  if (!files?.length) return 0;
  if (replace) {
    state.queue = [];
    state.activeIndex = -1;
    resetPreviewState();
  }
  const addedItems = enqueueFiles(files);
  if (!addedItems.length) {
    setStatus("No files were added to the queue.");
    return 0;
  }
  await Promise.all(addedItems.map((item) => saveQueueFileBlob(item.id, item.file)));

  state.activeIndex = state.queue.length - 1;
  syncActiveFromQueue();
  state.result = null;
  els.runBtn.disabled = false;
  renderResults(null);
  setStatus(`Added ${addedItems.length} file(s) to queue (${state.queue.length} total)`);

  const item = getActiveItem();
  if (!item) return addedItems.length;

  state.previewScale = 1;
  await renderPreview(item.file);
  await fetchProfile(item.file);
  item.profile = state.profile;
  item.status = "ready";
  item.statusMessage = "Profile ready";
  updateQueueUI();
  persistSession();
  return addedItems.length;
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
  await addFilesToQueue([file], { replace: false });
}

async function handleFiles(files) {
  if (!files?.length) return;
  await addFilesToQueue(files, { replace: true });
}

async function renderPreview(file) {
  els.previewPlaceholder.classList.add("hidden");
  els.previewCanvas.classList.add("hidden");
  els.previewImage.classList.add("hidden");
  updateZoomUI();

  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
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
    state.pdfDoc = null;
    state.totalPages = 1;
    state.currentPage = 1;
    els.totalPages.textContent = "1";
    els.currentPage.textContent = "1";
    els.previewImage.onload = () => {
      state.previewNaturalWidth = els.previewImage.naturalWidth || 1;
      state.previewNaturalHeight = els.previewImage.naturalHeight || 1;
      const container = els.previewContainer;
      const fitScale = Math.min(
        (container.clientWidth - 16) / state.previewNaturalWidth,
        (container.clientHeight - 16) / state.previewNaturalHeight,
        1,
      );
      state.previewBaseScale = Math.max(0.1, fitScale || 1);
      applyImagePreviewZoom();
    };
    els.previewImage.src = state.previewUrl;
    els.previewImage.classList.remove("hidden");
    els.prevPage.disabled = true;
    els.nextPage.disabled = true;
  } else {
    state.pdfDoc = null;
    els.previewPlaceholder.textContent = file.name;
    els.previewPlaceholder.classList.remove("hidden");
  }
}

async function renderPdfPage(pageNum) {
  if (!state.pdfDoc) return;
  const page = await state.pdfDoc.getPage(pageNum);
  const baseViewport = page.getViewport({ scale: 1 });
  const container = els.previewContainer;
  const fitScale = Math.min(
    (container.clientWidth - 16) / baseViewport.width,
    (container.clientHeight - 16) / baseViewport.height,
    1.5,
  );
  state.previewBaseScale = Math.max(0.1, fitScale || 1);
  state.previewNaturalWidth = baseViewport.width;
  state.previewNaturalHeight = baseViewport.height;
  const viewport = page.getViewport({ scale: state.previewBaseScale * state.previewScale });
  const canvas = els.previewCanvas;
  const ctx = canvas.getContext("2d");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  canvas.style.width = `${viewport.width}px`;
  canvas.style.height = `${viewport.height}px`;
  await page.render({ canvasContext: ctx, viewport }).promise;
  canvas.classList.remove("hidden");
  els.currentPage.textContent = pageNum;
  updateZoomUI();
}

function updatePageButtons() {
  els.prevPage.disabled = state.currentPage <= 1;
  els.nextPage.disabled = state.currentPage >= state.totalPages;
}

async function fetchProfileForItem(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/analyze/profile`, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) {
    const msg = data?.error?.message || data?.detail?.error?.message || res.statusText;
    throw new Error(msg);
  }
  return data;
}

async function fetchProfile(file, { silent = false } = {}) {
  try {
    const data = await fetchProfileForItem(file);
    state.profile = data;
    const item = getActiveItem();
    if (item) item.profile = data;
    if (!silent) {
      renderDocumentProfile();
      setActiveMainTab("profile");
      setStatus("Profile ready — configure options or run extraction");
      persistSession();
    }
    return data;
  } catch (err) {
    if (!silent) {
      setStatus(`Profile failed: ${err.message}`);
      els.profileContent.innerHTML = `<p class="scan-profile-msg">Profile failed: ${escapeHtml(err.message)}</p>`;
    }
    throw err;
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
    els.profileContent.innerHTML = "<p class=\"scan-profile-msg\">Upload a document to see profile.</p>";
    els.profilePageSelect.innerHTML = "";
    return;
  }

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
        <div>Mode: <strong>${escapeHtml(sr.engine || "smart")}</strong></div>
        <div>Strategy: <strong>${escapeHtml(formatFlavorLabel(normalizeFlavorFromProfile(sr.flavor)))}</strong></div>
        <div>Params: ${escapeHtml(sr.param_mode || "auto")}</div>
        <p class="profile-routing-note">Smart mode runs pdfplumber first; camelot full-page fallback when scores are low.</p>
      </div>
    </div>
    <details class="profile-details" open>
      <summary>Typography &amp; spacing</summary>
      <div class="profile-details-body">
        <dl>
          <dt>Char width (mode)</dt><dd>${ty.mode_char_width_pt} pt</dd>
          <dt>Char height (mode)</dt><dd>${ty.mode_char_height_pt} pt</dd>
          <dt>Line height (mode)</dt><dd>${ty.mode_line_height_pt} pt</dd>
          <dt>Line spacing (mode)</dt><dd>${ty.mode_line_spacing_pt} pt</dd>
          <dt>Text lines / chars</dt><dd>${ty.total_lines} / ${ty.total_chars}</dd>
        </dl>
      </div>
    </details>
    <details class="profile-details">
      <summary>Line analysis</summary>
      <div class="profile-details-body">
        <dl>
          <dt>Method</dt><dd>${escapeHtml(cd.method || "—")}</dd>
          <dt>Horizontal lines</dt><dd>${cd.h_lines ?? "—"}</dd>
          <dt>Vertical lines</dt><dd>${cd.v_lines ?? "—"}</dd>
          <dt>Line concentration</dt><dd>${cd.line_concentration != null ? cd.line_concentration.toFixed(2) : "—"}</dd>
          <dt>Area ratio</dt><dd>${cd.area_ratio != null ? cd.area_ratio.toFixed(2) : "—"}</dd>
          <dt>Direction balance</dt><dd>${cd.direction_balance != null ? cd.direction_balance.toFixed(2) : "—"}</dd>
        </dl>
      </div>
    </details>`;
}

function applyProfileToAdvanced() {
  const pageProf = getCurrentPageProfile();
  if (!pageProf?.computed_params) return;
  state.options.mode = "advanced";
  state.options.paramMode = "custom";
  state.options.engine = pageProf.suggested_routing?.engine || "auto";
  state.options.flavor = normalizeFlavorFromProfile(pageProf.suggested_routing?.flavor);
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
  $("optFlavor").value = normalizeFlavorFromProfile(state.options.flavor);
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
  updateOptionsVisibility();
}

function updateModalProfileSummary() {
  const pp = getCurrentPageProfile();
  const el = $("modalProfileSummary");
  if (!pp) {
    el.textContent = state.profile?.scan_profile?.message || "Upload a file to see suggested parameters.";
    return;
  }
  el.textContent = `Page ${pp.page}: ${pp.table_type} (score ${pp.table_type_score?.toFixed(2)}) → ${pp.suggested_routing?.engine} / ${formatFlavorLabel(normalizeFlavorFromProfile(pp.suggested_routing?.flavor))}`;
}

function updateAdvancedControls() {
  const advanced = state.options.mode === "advanced";
  const custom = state.options.paramMode === "custom";
  $("enginesHint").textContent = advanced
    ? "Override Smart routing with explicit engine settings."
    : "Smart mode uses automatic engine selection.";
  updateOptionsVisibility();
  const hintEl = $("paramModeHint");
  if (hintEl) {
    if (!advanced) {
      hintEl.textContent = "";
    } else if (custom) {
      hintEl.textContent = "Custom mode uses the JSON parameter blocks below. Edit values or apply profile suggestions.";
    } else {
      hintEl.textContent = "Auto param mode derives extraction settings from page features at runtime.";
    }
  }
  const scanProfile = state.profile?.scan_profile;
  const transformerAvailable = scanProfile?.transformer_available !== false;
  ["optEngine", "optFlavor", "optOcrEngine", "optTransformer", "optLanguages"].forEach((id) => {
    const el = $(id);
    if (!el || el.closest("[hidden]")) return;
    el.disabled = !advanced;
  });
  const optTransformer = $("optTransformer");
  const transformerGroup = $("enginesGroupTransformer");
  if (
    optTransformer &&
    transformerGroup &&
    !transformerGroup.hidden &&
    !transformerAvailable
  ) {
    optTransformer.disabled = true;
  }
  ["paramsCamelotLattice", "paramsCamelotStream", "paramsPdfplumberBordered", "paramsPdfplumberUnbordered"].forEach((id) => {
    $(id).disabled = !custom;
  });
}

function readOptionsFromModal() {
  state.options.mode = document.querySelector('input[name="extractMode"]:checked').value;
  const fileType = getDetectedFileType();
  const isRaster = fileType === "image" || fileType === "pdf_scan";
  state.options.extractTables =
    isRaster && RASTER_TABLES_FROZEN ? false : $("optExtractTables").checked;
  state.options.extractText = $("optExtractText").checked;
  state.options.pages = $("optPages").value.trim();
  state.options.engine = $("optEngine").value;
  state.options.flavor = normalizeFlavorFromProfile($("optFlavor").value);
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
  header.textContent = `Table ${index + 1} · page ${table.page} · score ${(table.score || 0).toFixed(2)} · ${formatTableSourceLabel(table.source)}`;
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
      cellEl.textContent = decodeCidPlaceholders(cell ?? "");
      tr.appendChild(cellEl);
    });
    tableEl.appendChild(tr);
  });
  wrap.appendChild(tableEl);
  return wrap;
}

function decodeCidPlaceholders(text) {
  if (!text || !text.includes("(cid:")) return text;
  return text
    .replace(/(?:\(cid:\d+\))+/g, (run) => {
      const codes = [...run.matchAll(/\(cid:(\d+)\)/g)].map((m) => Number(m[1]));
      if (!codes.length) return run;
      if (codes.every((code) => code <= 255)) {
        try {
          return new TextDecoder("utf-8").decode(Uint8Array.from(codes));
        } catch {
          /* fall through */
        }
      }
      if (codes.length === 1 && codes[0] < 0x110000) {
        try {
          return String.fromCodePoint(codes[0]);
        } catch {
          /* fall through */
        }
      }
      return "";
    })
    .replace(/\(cid:\d+\)/g, "");
}

function buildFullText(data) {
  if (data.ocr?.length) {
    const blocks = [...data.ocr].sort((a, b) => {
      if (a.page !== b.page) return a.page - b.page;
      const ay = a.bbox?.[1] ?? 0;
      const by = b.bbox?.[1] ?? 0;
      if (Math.abs(ay - by) > 8) return ay - by;
      return (a.bbox?.[0] ?? 0) - (b.bbox?.[0] ?? 0);
    });
    return blocks.map((b) => decodeCidPlaceholders(b.text)).join("\n");
  }
  if (data.text_preview) {
    return decodeCidPlaceholders(data.text_preview);
  }
  if (data.tables?.length) {
    return (
      data.tables
        .flatMap((t) => (t.rows || []).map((r) => r.map((cell) => decodeCidPlaceholders(cell)).join("\t")))
        .join("\n") || "No plain text."
    );
  }
  return "No text content in result.";
}

function describeContentText(data) {
  if (!data) return "No text extracted yet.";
  if (data.status === "failed" || data.error) {
    return `Extraction failed: ${data.error?.message || "Unknown error."}`;
  }

  const warnings = data.warnings || [];
  const text = buildFullText(data);
  const hasOcr = (data.ocr || []).some((b) => (b.text || "").trim());
  const hasTables = (data.tables || []).length > 0;
  const hasPreview = !!(data.text_preview || "").trim();
  const hasText = hasOcr || hasTables || hasPreview;

  const failed = warnings.find((w) => w.code === "ocr_extraction_failed");
  if (failed && !hasText) {
    return failed.message || "OCR extraction failed.";
  }

  if (!hasText) {
    const noText = warnings.find((w) => w.code === "no_text_detected");
    return noText?.message || "Extraction completed but no text or tables were detected.";
  }

  if (failed && hasText) {
    return `${text}\n\nNote: ${failed.message || "Partial OCR failure on one or more pages."}`;
  }

  return text;
}

function renderQualityPanel(data) {
  if (!els.qualityPanel) return;
  if (!data) {
    els.qualityPanel.classList.add("hidden");
    els.qualityPanel.innerHTML = "";
    return;
  }
  const q = data.quality || {};
  const warnings = data.warnings || [];
  const hints = data.hints || [];
  const score = q.overall_confidence != null ? `${Math.round(q.overall_confidence * 100)}%` : "—";
  const routingLine = data.routing ? formatRoutingSummary(data.routing) : null;
  const ocrBlocks = q.ocr_blocks ?? (data.ocr || []).length;
  const warnHtml = warnings.length
    ? warnings.map((w) => {
        const isFailure = w.code === "ocr_extraction_failed";
        const cls = isFailure ? "quality-warn quality-fail" : "quality-warn";
        return `<div class="${cls}">⚠ ${escapeHtml(w.code || "")}: ${escapeHtml(w.message || "")}</div>`;
      }).join("")
    : "";
  const hintHtml = hints.length
    ? hints.map((h) => `<div class="quality-hint">💡 ${escapeHtml(h.message || "")}</div>`).join("")
    : "";
  els.qualityPanel.innerHTML = `
    <div class="quality-score">Confidence: ${score} · Tables: ${q.tables_accepted ?? 0}/${q.tables_found ?? 0} · OCR blocks: ${ocrBlocks} · Pages: ${q.pages_processed ?? 0}</div>
    ${routingLine ? `<div class="quality-hint">Routing: ${escapeHtml(routingLine)}</div>` : ""}
    ${warnHtml}${hintHtml}`;
  els.qualityPanel.classList.remove("hidden");
}

function renderTransactionTable(container, rows, emptyMsg) {
  container.innerHTML = "";
  if (!rows?.length) {
    container.innerHTML = `<p class="scan-profile-msg">${emptyMsg}</p>`;
    return;
  }
  const table = document.createElement("table");
  table.className = "tx-table";
  const headers = ["date", "description", "amount", "internal_code", "internal_label"];
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  headers.forEach((h) => {
    const th = document.createElement("th");
    th.textContent = h;
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  rows.forEach((tx) => {
    const tr = document.createElement("tr");
    headers.forEach((h) => {
      const td = document.createElement("td");
      td.textContent = tx[h] ?? "—";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

function renderResults(data) {
  state.result = data;
  const item = getActiveItem();
  if (item) item.result = data;

  els.contentTableList.innerHTML = "";
  els.exportJsonBtn.disabled = true;
  els.exportCsvBtn.disabled = true;
  els.exportMarkdownBtn.disabled = true;
  els.exportDocxBtn.disabled = true;
  els.saveValidationBtn.disabled = true;

  renderQualityPanel(data);

  if (!data) {
    els.contentText.textContent = "No text extracted yet.";
    els.resultJson.querySelector("code").textContent = "No result data available";
    if (window.DocuVisionUiFeatures?.isContentTabEnabled("transactions")) {
      renderTransactionTable(els.contentTransactionsList, [], "No transactions yet.");
    }
    if (window.DocuVisionUiFeatures?.isContentTabEnabled("mapped")) {
      renderTransactionTable(els.contentMappedList, [], "No mapped transactions yet.");
    }
    return;
  }

  els.contentText.textContent = describeContentText(data);

  (data.tables || []).forEach((t, i) => {
    els.contentTableList.appendChild(renderTable(t, i));
  });

  if (window.DocuVisionUiFeatures?.isContentTabEnabled("transactions")) {
    const transactions = data.transactions || (window.DocuVisionDemo && DocuVisionDemo.extractTransactions(data)) || [];
    renderTransactionTable(els.contentTransactionsList, transactions, "No transaction rows detected from tables.");
  }
  if (window.DocuVisionUiFeatures?.isContentTabEnabled("mapped")) {
    const mapped = data.mapped_transactions
      || (window.DocuVisionUiFeatures?.isContentTabEnabled("transactions")
        ? (data.transactions || (window.DocuVisionDemo && DocuVisionDemo.extractTransactions(data)) || [])
        : []);
    renderTransactionTable(els.contentMappedList, mapped, "No mapped transactions.");
  }

  els.resultJson.querySelector("code").textContent = JSON.stringify(data, null, 2);
  els.exportJsonBtn.disabled = false;
  els.exportCsvBtn.disabled = false;
  els.exportMarkdownBtn.disabled = false;
  els.exportDocxBtn.disabled = false;
  els.saveValidationBtn.disabled = false;
  persistSession();
}

async function runExtractionForItem(item, { silent = false } = {}) {
  if (!item?.file) return;

  const form = new FormData();
  form.append("file", item.file);
  form.append("mode", state.options.mode);
  form.append("engine", state.options.mode === "advanced" ? state.options.engine : "auto");
  form.append("flavor", state.options.mode === "advanced"
    ? resolveFlavorForApi(state.options.engine, state.options.flavor)
    : "auto");
  form.append("ocr_engine", state.options.mode === "advanced" ? state.options.ocrEngine : "auto");
  form.append("languages", state.options.languages || "eng");
  const fileType = getDetectedFileType();
  const isRaster = fileType === "image" || fileType === "pdf_scan";
  const extractTables =
    isRaster && RASTER_TABLES_FROZEN ? false : state.options.extractTables;
  form.append("extract_tables", String(extractTables));
  form.append("extract_text", String(state.options.extractText));
  form.append(
    "use_transformer",
    String(extractTables && state.options.transformer === "transformer"),
  );
  if (state.options.pages) form.append("pages", state.options.pages);
  form.append("score_threshold", String(state.options.scoreThreshold));
  form.append("param_mode", state.options.paramMode);
  if (state.options.paramMode === "custom" && state.options.customParams) {
    form.append("custom_params", JSON.stringify(state.options.customParams));
  }

  try {
    const res = await fetch(`${API_BASE}/extract/auto`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      const msg = data?.error?.message || data?.detail?.error?.message || res.statusText;
      if (!silent) setStatus(`Extraction failed: ${msg}`);
      item.result = null;
      if (!silent && state.activeIndex >= 0 && state.queue[state.activeIndex] === item) {
        els.contentText.textContent = `Extraction failed: ${msg}`;
        els.resultJson.querySelector("code").textContent = JSON.stringify(data, null, 2);
        renderQualityPanel(null);
        setActiveMainTab("content");
        setActiveContentTab("text");
      }
      return;
    }
    item.result = data;
    if (!silent && state.activeIndex >= 0 && state.queue[state.activeIndex] === item) {
      renderResults(data);
      const routing = formatRoutingSummary(data.routing);
      setStatus(`Done in ${data.processing_ms} ms — ${routing}`);
    }
    persistSession();
  } catch (err) {
    if (!silent) setStatus(`Request failed: ${err.message}`);
    item.result = null;
  }
}

async function runExtraction() {
  if (!state.queue.length) {
    setStatus("Please upload a file first.");
    return;
  }
  const item = getActiveItem();
  if (!item) {
    setStatus("Select a file in the queue to analyze.");
    return;
  }
  if (state.processing) return;

  state.processing = true;
  els.runBtn.disabled = true;

  if (!item.profile) {
    item.status = "profiling";
    item.statusMessage = "Analyzing profile…";
    updateQueueUI();
    try {
      item.profile = await fetchProfileForItem(item.file);
      state.profile = item.profile;
    } catch (err) {
      item.status = "failed";
      item.statusMessage = err.message || "Profile failed";
      updateQueueUI();
      state.processing = false;
      els.runBtn.disabled = !state.queue.length;
      setStatus(`Profile failed: ${err.message}`);
      persistSession();
      return;
    }
  }

  item.status = "extracting";
  item.statusMessage = "Extracting…";
  updateQueueUI();
  setStatus("Extracting…");
  await runExtractionForItem(item);

  item.status = item.result ? "done" : "failed";
  item.statusMessage = item.result ? `Done (${item.result.processing_ms || 0} ms)` : "Failed";
  updateQueueUI();
  state.processing = false;
  els.runBtn.disabled = !state.queue.length;
  persistSession();

  if (item.result) {
    setActiveMainTab("content");
    setActiveContentTab(item.result.tables?.length ? "tables" : "text");
    const routing = formatRoutingSummary(item.result.routing);
    setStatus(`Done in ${item.result.processing_ms || 0} ms — ${routing}`);
  }
}

function setActiveMainTab(tab) {
  document.querySelectorAll(".result-main-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.mainTab === tab);
  });
  $("profileView").classList.toggle("active", tab === "profile");
  $("contentView").classList.toggle("active", tab === "content");
  $("resultView").classList.toggle("active", tab === "result");
}

function setActiveContentTab(tab) {
  const tabBtn = document.querySelector(`.content-sub-tab[data-content="${tab}"]`);
  if (
    !window.DocuVisionUiFeatures?.isContentTabEnabled(tab)
    || (tabBtn && tabBtn.classList.contains("hidden"))
  ) {
    tab = "text";
  }
  document.querySelectorAll(".content-sub-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.content === tab);
  });
  $("contentTextView").classList.toggle("active", tab === "text");
  $("contentTablesView").classList.toggle("active", tab === "tables");
  $("contentTransactionsView").classList.toggle("active", tab === "transactions");
  $("contentMappedView").classList.toggle("active", tab === "mapped");
  $("contentFiguresView").classList.toggle("active", tab === "figures");
}

function initUpload() {
  els.uploadZone.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", () => {
    const files = els.fileInput.files;
    if (files?.length > 1) void handleFiles(files);
    else if (files?.[0]) void handleFile(files[0]);
    els.fileInput.value = "";
  });
  els.uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.uploadZone.classList.add("dragover");
  });
  els.uploadZone.addEventListener("dragleave", () => els.uploadZone.classList.remove("dragover"));
  els.uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    els.uploadZone.classList.remove("dragover");
    const files = e.dataTransfer.files;
    if (files?.length > 1) void handleFiles(files);
    else if (files?.[0]) void handleFile(files[0]);
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

  $("optExtractTables")?.addEventListener("change", () => {
    updateOptionsVisibility();
    updateAdvancedControls();
  });
  $("optExtractText")?.addEventListener("change", () => {
    updateOptionsVisibility();
    updateAdvancedControls();
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
    if (!state.result) {
      const msg = "No result data to copy.";
      DocuVisionNotify.show(msg, "error");
      setStatus(msg);
      return;
    }
    const text = JSON.stringify(state.result, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      DocuVisionNotify.show("JSON copied to clipboard", "success");
      setStatus("JSON copied to clipboard");
    }).catch(() => {
      DocuVisionNotify.show("Failed to copy JSON", "error");
      setStatus("Failed to copy JSON");
    });
  });

  $("downloadJsonBtn")?.addEventListener("click", () => {
    if (!state.result) {
      const msg = "No result data to download.";
      DocuVisionNotify.show(msg, "error");
      setStatus(msg);
      return;
    }
    const text = JSON.stringify(state.result, null, 2);
    const jobId = state.result.job_id || "lite_result";
    DocuVisionExport.downloadText(text, `${jobId}_result.json`, "application/json");
    DocuVisionNotify.show("JSON downloaded", "success");
    setStatus("JSON downloaded");
  });

  initExportButtons();

  els.saveValidationBtn?.addEventListener("click", async () => {
    if (!state.result?.job_id) return;
    els.saveValidationBtn.disabled = true;
    try {
      const res = await fetch(`${API_BASE}/demo/persist/${state.result.job_id}`, { method: "POST" });
      const data = await res.json();
      setStatus(data.message || (data.persisted ? "Saved to validation store" : "Save failed"));
    } catch (err) {
      setStatus(`Save failed: ${err.message}`);
    } finally {
      els.saveValidationBtn.disabled = false;
    }
  });
}

function downloadBlob(blob, name) {
  DocuVisionExport.downloadBlob(blob, name);
}

function initExportButtons() {
  DocuVisionExport.init({
    getJobId: () => state.result?.job_id || null,
    buildUrl: (jobId, apiFormat) => `${API_BASE}/export/${jobId}.${apiFormat}`,
    notify: (message, type) => DocuVisionNotify.show(message, type),
    onStatus: (message) => setStatus(message),
  });
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

function initPreviewZoom() {
  els.zoomInBtn?.addEventListener("click", () => setPreviewScale(state.previewScale + 0.15));
  els.zoomOutBtn?.addEventListener("click", () => setPreviewScale(state.previewScale - 0.15));
  els.zoomFitBtn?.addEventListener("click", () => resetPreviewScale());

  els.previewContainer?.addEventListener(
    "wheel",
    (e) => {
      if (!state.file) return;
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setPreviewScale(state.previewScale + delta);
    },
    { passive: false },
  );

  els.openValidationLink?.addEventListener("click", () => {
    persistSession();
  });

  window.addEventListener("beforeunload", () => {
    persistSession();
  });

  updateZoomUI();
}

async function init() {
  window.DocuVisionUiFeatures?.applyLiteUiFeatures?.()
    || window.DocuVisionUiFeatures?.applyContentTabFeatures();
  initUpload();
  initPagination();
  initProfile();
  initModal();
  initResultsTabs();
  initPanelLayout();
  initPreviewZoom();
  $("helpBtn")?.addEventListener("click", () => window.open("/docs", "_blank"));
  els.runBtn.addEventListener("click", runExtraction);
  fetchHealth();
  fetchEnginesCatalog();

  const restored = await restoreSession();
  if (restored && state.file) {
    els.runBtn.disabled = false;
    await renderPreview(state.file);
    if (state.profile) {
      renderDocumentProfile();
      setActiveMainTab("profile");
    } else {
      await fetchProfile(state.file);
    }
    renderResults(state.result);
    setStatus(`Restored ${state.queue.length} file(s) from session`);
  } else {
    setStatus("Ready");
  }
}

void init();
