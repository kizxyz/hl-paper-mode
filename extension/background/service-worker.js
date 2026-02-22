/**
 * Service Worker — Background script
 *
 * Handles:
 * - Paper mode state management
 * - DNR rule toggling (Layer 3 failsafe)
 * - Backend health check
 * - Message relay between popup and content scripts
 */

const BACKEND_URL = "http://localhost:8000";
const DNR_RULESET_ID = "block_rules";

// Initialize default state
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    paperMode: true,  // ON by default (spec: Safety Defaults)
    dnrEnabled: false, // OFF by default (spec: DNR OFF by default)
  });
});

// Handle messages from popup and content scripts
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "GET_STATE") {
    chrome.storage.local.get(["paperMode", "dnrEnabled"], (result) => {
      // Also check backend health
      checkBackendHealth().then((online) => {
        sendResponse({
          paperMode: result.paperMode !== false,
          dnrEnabled: result.dnrEnabled === true,
          backendOnline: online,
        });
      });
    });
    return true; // async response
  }

  if (msg.type === "TOGGLE_PAPER_MODE") {
    const enabled = msg.enabled;
    chrome.storage.local.set({ paperMode: enabled });

    // Relay to all HL tabs
    chrome.tabs.query({ url: "https://app.hyperliquid.xyz/*" }, (tabs) => {
      for (const tab of tabs) {
        chrome.tabs.sendMessage(tab.id, {
          type: "PAPER_MODE_TOGGLE",
          enabled,
        });
      }
    });

    sendResponse({ ok: true });
    return false;
  }

  if (msg.type === "TOGGLE_DNR") {
    const enabled = msg.enabled;
    chrome.storage.local.set({ dnrEnabled: enabled });
    toggleDNR(enabled);
    sendResponse({ ok: true });
    return false;
  }
});

// DNR toggle — enable/disable the block ruleset
async function toggleDNR(enabled) {
  try {
    if (enabled) {
      await chrome.declarativeNetRequest.updateEnabledRulesets({
        enableRulesetIds: [DNR_RULESET_ID],
      });
    } else {
      await chrome.declarativeNetRequest.updateEnabledRulesets({
        disableRulesetIds: [DNR_RULESET_ID],
      });
    }
    console.log(`[HL Paper] DNR ${enabled ? "enabled" : "disabled"}`);
  } catch (err) {
    console.error("[HL Paper] DNR toggle error:", err);
  }
}

// Backend health check
async function checkBackendHealth() {
  try {
    const resp = await fetch(`${BACKEND_URL}/api/v1/account`, {
      method: "GET",
      signal: AbortSignal.timeout(3000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

console.log("[HL Paper] Service worker loaded");
