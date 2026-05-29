/**
 * Shared export button handler for Pro and Lite.
 */
(function (global) {
  function normalizeFormat(format) {
    const value = (format || "").toLowerCase();
    return value === "word" ? "docx" : value;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  function downloadText(text, filename, mimeType) {
    downloadBlob(new Blob([text], { type: mimeType }), filename);
  }

  async function exportResults(format, options) {
    const opts = options || {};
    const notify = opts.notify || (() => {});
    const onStatus = opts.onStatus || (() => {});
    const getJobId = opts.getJobId;
    const buildUrl = opts.buildUrl;
    const supportsAzure = !!opts.supportsAzure;

    const jobId = typeof getJobId === "function" ? getJobId() : null;
    if (!jobId) {
      const msg = "No completed task to export. Run analysis first.";
      notify(msg, "error");
      onStatus(msg);
      return;
    }

    const apiFormat = normalizeFormat(format);

    try {
      const response = await fetch(buildUrl(jobId, apiFormat));

      if (!response.ok) {
        let detail = response.statusText;
        try {
          const errBody = await response.json();
          detail = errBody.detail || errBody?.error?.message || detail;
        } catch {
          /* ignore */
        }
        const msg = `Export failed: ${detail}`;
        notify(msg, "error");
        onStatus(msg);
        return;
      }

      const contentType = response.headers.get("content-type") || "";

      if (
        contentType.includes("application/json") &&
        (apiFormat === "markdown" || apiFormat === "md")
      ) {
        const payload = await response.json();
        const md = payload.markdown || "";
        downloadText(md, `${jobId}_result.md`, "text/markdown");
      } else if (supportsAzure && contentType.includes("application/json") && apiFormat === "azure") {
        const payload = await response.json();
        downloadText(JSON.stringify(payload, null, 2), `${jobId}_azure.json`, "application/json");
      } else if (apiFormat === "json") {
        const text = await response.text();
        downloadText(text, `${jobId}_result.json`, "application/json");
      } else {
        const blob = await response.blob();
        const disposition = response.headers.get("content-disposition") || "";
        const match = disposition.match(/filename=\"?([^\";\n]+)\"?/i);
        const filename = match?.[1] || `${jobId}_result.${apiFormat}`;
        downloadBlob(blob, filename);
      }

      const successMsg = `Exported ${apiFormat.toUpperCase()} successfully`;
      notify(successMsg, "success");
      onStatus(successMsg);
    } catch (err) {
      const msg = `Export failed: ${err.message}`;
      notify(msg, "error");
      onStatus(msg);
    }
  }

  function init(options) {
    const opts = options || {};
    const selector = opts.buttonSelector || ".export-btn[data-format]";

    document.querySelectorAll(selector).forEach((btn) => {
      btn.addEventListener("click", () => {
        exportResults(btn.dataset.format, opts);
      });
    });
  }

  global.DocuVisionExport = {
    init,
    exportResults,
    downloadBlob,
    downloadText,
    normalizeFormat,
  };
})(typeof window !== "undefined" ? window : globalThis);
