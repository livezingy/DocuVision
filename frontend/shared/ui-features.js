/**
 * Shared UI feature flags for Lite and Pro frontends.
 * Toggle contentTabs flags to enable optional demo tabs without DOM changes.
 */
(function (global) {
  const contentTabs = {
    transactions: false,
    mapped: false,
  };

  const exportActions = {
    validationDashboard: false,
  };

  function isContentTabEnabled(name) {
    if (!(name in contentTabs)) return true;
    return !!contentTabs[name];
  }

  function applyContentTabFeatures() {
    Object.keys(contentTabs).forEach((name) => {
      const btn = document.querySelector(`.content-sub-tab[data-content="${name}"]`);
      if (btn) btn.classList.toggle("hidden", !contentTabs[name]);
    });
  }

  function applyExportActionFeatures() {
    const showValidation = !!exportActions.validationDashboard;
    ["openValidationLink", "saveValidationBtn"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.classList.toggle("hidden", !showValidation);
    });
  }

  function applyLiteUiFeatures() {
    applyContentTabFeatures();
    applyExportActionFeatures();
  }

  global.DocuVisionUiFeatures = {
    contentTabs,
    exportActions,
    isContentTabEnabled,
    applyContentTabFeatures,
    applyExportActionFeatures,
    applyLiteUiFeatures,
  };
})(typeof window !== "undefined" ? window : globalThis);
