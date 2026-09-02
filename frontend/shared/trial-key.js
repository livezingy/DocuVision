/* Trial API-key bridge (GLM trial P0-1).
 *
 * Keeps frontend/app.js untouched: this module wraps window.fetch and
 * window.WebSocket once so every existing call site automatically carries
 * the trial API key.
 *
 * Key resolution order:
 *   1. ?key= query parameter (also persisted to localStorage)
 *   2. localStorage "docuvision_trial_key"
 *   3. "" (auth off on the backend; no wrappers needed)
 *
 * Behaviour:
 *   - fetch: injects the X-API-Key header unless the caller set it.
 *   - WebSocket: appends &key= to the URL (browsers cannot set WS headers).
 *   - When a 401 is observed and no key is stored, a small banner lets the
 *     user paste the key, saves it and reloads.
 */
(function () {
  "use strict";

  var KEY_HEADER = "X-API-Key";
  var STORE_KEY = "docuvision_trial_key";

  function readInitialKey() {
    try {
      var params = new URLSearchParams(window.location.search);
      var fromUrl = params.get("key");
      if (fromUrl) {
        window.localStorage.setItem(STORE_KEY, fromUrl);
        return fromUrl;
      }
      return window.localStorage.getItem(STORE_KEY) || "";
    } catch (e) {
      return "";
    }
  }

  var trialKey = readInitialKey();

  /* ---------- banner ---------- */
  var banner = null;
  function ensureBanner() {
    if (banner) return banner;
    banner = document.createElement("div");
    banner.setAttribute("data-testid", "trial-key-banner");
    banner.style.cssText = [
      "position:fixed", "right:16px", "bottom:16px", "z-index:9999",
      "max-width:340px", "padding:10px 14px", "border-radius:8px",
      "background:#0f172a", "color:#e2e8f0", "font:13px/1.4 Inter,system-ui,sans-serif",
      "box-shadow:0 8px 24px rgba(0,0,0,.35)", "border:1px solid #334155"
    ].join(";");
    document.body.appendChild(banner);
    return banner;
  }

  function showKeyActive() {
    var b = ensureBanner();
    b.innerHTML = "Trial API key active";
    setTimeout(function () { if (b && b.parentNode) b.parentNode.removeChild(b); banner = null; }, 4000);
  }

  function showKeyRequired() {
    if (banner && banner.getAttribute("mode") === "required") return;
    var b = ensureBanner();
    b.setAttribute("mode", "required");
    b.innerHTML =
      "API key required. " +
      '<input id="trial-key-input" type="password" placeholder="paste trial key" ' +
      'style="margin-left:6px;padding:4px 6px;border-radius:4px;border:1px solid #475569;background:#1e293b;color:#e2e8f0"/>' +
      '<button id="trial-key-save" style="margin-left:6px;padding:4px 8px;border-radius:4px;border:1px solid #475569;background:#334155;color:#e2e8f0;cursor:pointer">Save</button>';
    var save = function () {
      var input = document.getElementById("trial-key-input");
      if (input && input.value) {
        window.localStorage.setItem(STORE_KEY, input.value);
        window.location.reload();
      }
    };
    var btn = document.getElementById("trial-key-save");
    if (btn) btn.addEventListener("click", save);
    var inp = document.getElementById("trial-key-input");
    if (inp) {
      inp.addEventListener("keydown", function (ev) { if (ev.key === "Enter") save(); });
    }
  }

  /* ---------- fetch wrapper ---------- */
  var nativeFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    if (trialKey) {
      var headers = new Headers(init.headers || {});
      if (!headers.has(KEY_HEADER)) headers.set(KEY_HEADER, trialKey);
      init.headers = headers;
    }
    var p = nativeFetch(input, init);
    if (!p || typeof p.then !== "function") return p;
    return p.then(function (response) {
      if (response && response.status === 401 && !response.__trialAuthHandled) {
        try { response.__trialAuthHandled = true; } catch (e) { /* frozen response — ignore */ }
        showKeyRequired();
      }
      return response;
    });
  };

  /* ---------- WebSocket wrapper ---------- */
  if (trialKey && window.WebSocket) {
    var NativeWS = window.WebSocket;
    var PatchedWS = function (url, protocols) {
      try {
        var u = new URL(url, window.location.href);
        if (!u.searchParams.get("key")) u.searchParams.set("key", trialKey);
        url = u.toString();
      } catch (e) { /* non-standard URL — pass through untouched */ }
      return protocols === undefined ? new NativeWS(url) : new NativeWS(url, protocols);
    };
    PatchedWS.prototype = NativeWS.prototype;
    PatchedWS.OPEN = NativeWS.OPEN;
    PatchedWS.CONNECTING = NativeWS.CONNECTING;
    PatchedWS.CLOSING = NativeWS.CLOSING;
    PatchedWS.CLOSED = NativeWS.CLOSED;
    window.WebSocket = PatchedWS;
  }

  if (trialKey) showKeyActive();
})();
