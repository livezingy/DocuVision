const API_BASE = window.LITE_API_BASE || "/api/v1/lite";

const fileInput = document.getElementById("fileInput");
const runBtn = document.getElementById("runBtn");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");
const tablesEl = document.getElementById("tables");
const exportsEl = document.getElementById("exports");
const csvLink = document.getElementById("csvLink");
const xlsxLink = document.getElementById("xlsxLink");
const advancedOptions = document.getElementById("advancedOptions");

document.querySelectorAll('input[name="mode"]').forEach((el) => {
  el.addEventListener("change", () => {
    const advanced = document.querySelector('input[name="mode"]:checked').value === "advanced";
    advancedOptions.classList.toggle("hidden", !advanced);
  });
});

function renderTable(table, index) {
  const wrap = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = `Table ${index + 1} (page ${table.page}, score ${(table.score || 0).toFixed(2)})`;
  wrap.appendChild(title);

  const rows = [];
  if (table.headers && table.headers.length) rows.push(table.headers);
  rows.push(...(table.rows || []));

  if (!rows.length) {
    wrap.textContent += " (empty)";
    return wrap;
  }

  const tableEl = document.createElement("table");
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

runBtn.addEventListener("click", async () => {
  const file = fileInput.files?.[0];
  if (!file) {
    statusEl.textContent = "Please choose a file.";
    return;
  }

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  if (mode === "advanced") {
    form.append("engine", document.getElementById("engineSelect").value);
    form.append("flavor", document.getElementById("flavorSelect").value);
  }

  statusEl.textContent = "Processing...";
  tablesEl.innerHTML = "";
  metaEl.textContent = "";
  exportsEl.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/extract/auto`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      const msg = data?.error?.message || data?.detail?.error?.message || res.statusText;
      statusEl.textContent = `Error: ${msg}`;
      return;
    }

    statusEl.textContent = `Done in ${data.processing_ms} ms — ${data.routing?.engine_used || "n/a"}`;
    metaEl.textContent = `Type: ${data.input?.detected_file_type} | Tables: ${data.tables?.length || 0}`;

    (data.tables || []).forEach((t, i) => tablesEl.appendChild(renderTable(t, i)));

    if (data.exports?.csv) {
      csvLink.href = data.exports.csv;
      xlsxLink.href = data.exports.xlsx;
      exportsEl.classList.remove("hidden");
    }
  } catch (err) {
    statusEl.textContent = `Request failed: ${err.message}`;
  }
});
