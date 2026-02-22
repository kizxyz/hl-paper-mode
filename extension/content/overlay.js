/**
 * Overlay — Paper Mode indicator on HL UI
 *
 * Shows a persistent banner when paper mode is active.
 * Displays fill/error notifications from the interceptor.
 */

const OVERLAY_ID = "hl-paper-overlay";
const TOAST_ID = "hl-paper-toast";

let paperModeEnabled = true;

chrome.storage.local.get("paperMode", (result) => {
  paperModeEnabled = result.paperMode !== false;
  if (paperModeEnabled) showBanner();
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "PAPER_MODE_TOGGLE") {
    paperModeEnabled = msg.enabled;
    if (paperModeEnabled) {
      showBanner();
    } else {
      removeBanner();
    }
  }
});

// Listen for fill/error messages from interceptor
window.addEventListener("message", (e) => {
  if (e.source !== window) return;

  if (e.data?.type === "HL_PAPER_FILL") {
    const d = e.data.data;
    if (d.status === "filled") {
      showToast(`Paper fill: ${d.fill?.side} ${d.fill?.size?.toFixed(4)} @ ${d.fill?.price?.toFixed(2)}`, "success");
    } else if (d.status === "resting") {
      showToast("Paper limit order placed", "info");
    }
  }

  if (e.data?.type === "HL_PAPER_ERROR") {
    showToast(e.data.error, "error");
  }

  if (e.data?.type === "HL_PAPER_WS_BLOCKED") {
    showToast("WS order blocked (paper mode)", "info");
  }
});

function showBanner() {
  if (document.getElementById(OVERLAY_ID)) return;

  const banner = document.createElement("div");
  banner.id = OVERLAY_ID;
  Object.assign(banner.style, {
    position: "fixed",
    top: "0",
    left: "0",
    right: "0",
    zIndex: "999999",
    background: "#f59e0b",
    color: "#000",
    textAlign: "center",
    padding: "6px 12px",
    fontSize: "13px",
    fontWeight: "bold",
    fontFamily: "monospace",
    letterSpacing: "1px",
  });
  banner.textContent = "PAPER MODE — NO REAL TRADES";
  document.body.appendChild(banner);
}

function removeBanner() {
  const el = document.getElementById(OVERLAY_ID);
  if (el) el.remove();
}

function showToast(message, level = "info") {
  // Remove existing toast
  const existing = document.getElementById(TOAST_ID);
  if (existing) existing.remove();

  const colors = {
    success: "#22c55e",
    error: "#ef4444",
    info: "#3b82f6",
  };

  const toast = document.createElement("div");
  toast.id = TOAST_ID;
  Object.assign(toast.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "999999",
    background: colors[level] || colors.info,
    color: "#fff",
    padding: "10px 16px",
    borderRadius: "6px",
    fontSize: "13px",
    fontFamily: "monospace",
    maxWidth: "350px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
  });
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 4000);
}

console.log("[HL Paper] Overlay loaded");
