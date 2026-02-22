/**
 * Layer 2 — WebSocket Patch (OPTIONAL BEST-EFFORT)
 *
 * Injected into MAIN world to access WebSocket.prototype.send.
 * Detects order payloads and blocks them when paper mode is on.
 * Communicates back to content script via window.postMessage.
 */

(function () {
  "use strict";

  let paperModeEnabled = true;

  // Listen for paper mode toggle from content script
  window.addEventListener("message", (e) => {
    if (e.source !== window) return;
    if (e.data?.type === "HL_PAPER_MODE_SET") {
      paperModeEnabled = e.data.enabled;
    }
  });

  const OriginalWebSocket = window.WebSocket;
  const originalSend = OriginalWebSocket.prototype.send;

  OriginalWebSocket.prototype.send = function (data) {
    if (!paperModeEnabled) {
      return originalSend.call(this, data);
    }

    // Try to detect order payloads
    let parsed = null;
    try {
      if (typeof data === "string") {
        parsed = JSON.parse(data);
      }
    } catch {
      // Not JSON — let it through (heartbeats, subscriptions, etc.)
      return originalSend.call(this, data);
    }

    if (parsed && isOrderPayload(parsed)) {
      console.log("[HL Paper WS] Blocked order payload:", parsed);

      window.postMessage(
        {
          type: "HL_PAPER_WS_BLOCKED",
          payload: parsed,
        },
        window.location.origin
      );

      // Don't send — order is blocked
      return;
    }

    // Not an order — let it through
    return originalSend.call(this, data);
  };

  function isOrderPayload(msg) {
    // HL exchange messages typically have an "action" field
    // with type "order" or similar
    if (msg.method === "exchange" || msg.action?.type === "order") {
      return true;
    }

    // Check for common order-related fields
    if (
      msg.action &&
      (msg.action.type === "order" ||
        msg.action.type === "cancel" ||
        msg.action.type === "batchModify")
    ) {
      return true;
    }

    return false;
  }

  console.log("[HL Paper WS] WebSocket patch loaded (MAIN world)");
})();
