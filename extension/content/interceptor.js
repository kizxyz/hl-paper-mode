/**
 * Layer 1 — DOM Interception (PRIMARY)
 *
 * Uses MutationObserver + capture-phase click listener to intercept
 * order submissions on the Hyperliquid UI.
 *
 * When Paper Mode is ON:
 *   - preventDefault + stopPropagation on order buttons
 *   - Scrape order details from the UI
 *   - Send order intent to local backend
 */

const BACKEND_URL = "http://localhost:8000";
const ORDER_BUTTON_TEXTS = [
  "Place Order",
  "Buy / Long",
  "Sell / Short",
  "Close Position",
  "Market Buy",
  "Market Sell",
  "Limit Buy",
  "Limit Sell",
];

let paperModeEnabled = true;

// Load saved state
chrome.storage.local.get("paperMode", (result) => {
  paperModeEnabled = result.paperMode !== false; // default ON
});

// Listen for toggle messages from popup/service-worker
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "PAPER_MODE_TOGGLE") {
    paperModeEnabled = msg.enabled;
  }
});

// ---------------------------------------------------------------
// Button detection — NO :has-text(), loop + match textContent
// ---------------------------------------------------------------

function isOrderButton(el) {
  if (!el || el.tagName !== "BUTTON") return false;
  const text = (el.textContent || "").trim();
  return ORDER_BUTTON_TEXTS.some(
    (t) => text === t || text.startsWith(t)
  );
}

function findOrderButton(target) {
  let el = target;
  // Walk up max 5 levels to find the button
  for (let i = 0; i < 5 && el; i++) {
    if (isOrderButton(el)) return el;
    el = el.parentElement;
  }
  return null;
}

// ---------------------------------------------------------------
// Order scraping from HL UI
// ---------------------------------------------------------------

function scrapeOrderFromUI() {
  const order = {
    symbol: "",
    side: "BUY",
    order_type: "MARKET",
    size_value: 0,
    size_unit: "USD",
    leverage: 10,
    limit_price: null,
    reduce_only: false,
    client_id: `ext-${Date.now()}`,
    timestamp: Math.floor(Date.now() / 1000),
  };

  // Try to find the active symbol from the page
  // HL typically shows the symbol in a header/selector
  const symbolEl = document.querySelector(
    '[class*="asset-selector"], [class*="market-name"], [class*="symbol"]'
  );
  if (symbolEl) {
    const raw = symbolEl.textContent.trim();
    // Extract just the base symbol (e.g., "BTC" from "BTC-PERP" or "BTC/USD")
    order.symbol = raw.replace(/-PERP|\/USD|\/USDC/gi, "").trim();
  }

  // Detect side from active tab or button state
  const buttons = document.querySelectorAll("button");
  for (const btn of buttons) {
    const text = (btn.textContent || "").trim().toLowerCase();
    if (
      (text.includes("sell") || text.includes("short")) &&
      (btn.classList.contains("active") ||
        btn.getAttribute("aria-selected") === "true" ||
        btn.dataset.active === "true")
    ) {
      order.side = "SELL";
      break;
    }
  }

  // Scrape size input
  const sizeInputs = document.querySelectorAll(
    'input[type="text"], input[type="number"]'
  );
  for (const input of sizeInputs) {
    const label = input.closest("label")?.textContent || "";
    const placeholder = input.placeholder || "";
    const val = parseFloat(input.value);

    if (isNaN(val) || val <= 0) continue;

    if (
      label.toLowerCase().includes("size") ||
      placeholder.toLowerCase().includes("size") ||
      placeholder.toLowerCase().includes("amount")
    ) {
      order.size_value = val;
    }

    if (
      label.toLowerCase().includes("price") ||
      placeholder.toLowerCase().includes("price")
    ) {
      order.limit_price = val;
      order.order_type = "LIMIT";
    }
  }

  // Scrape leverage if visible
  const levEls = document.querySelectorAll(
    '[class*="leverage"], [class*="lever"]'
  );
  for (const el of levEls) {
    const match = el.textContent.match(/(\d+)x/i);
    if (match) {
      order.leverage = parseInt(match[1], 10);
      break;
    }
  }

  // Check for reduce-only toggle
  const reduceOnlyEls = document.querySelectorAll(
    'input[type="checkbox"], [class*="reduce"]'
  );
  for (const el of reduceOnlyEls) {
    const label = el.closest("label")?.textContent || "";
    if (label.toLowerCase().includes("reduce")) {
      order.reduce_only =
        el.type === "checkbox" ? el.checked : el.classList.contains("active");
      break;
    }
  }

  return order;
}

// ---------------------------------------------------------------
// Capture-phase click listener
// ---------------------------------------------------------------

document.addEventListener(
  "click",
  async (e) => {
    if (!paperModeEnabled) return;

    const btn = findOrderButton(e.target);
    if (!btn) return;

    // Block the real order
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    console.log("[HL Paper] Order button intercepted:", btn.textContent.trim());

    const order = scrapeOrderFromUI();

    // Infer side from button text if not already set
    const btnText = btn.textContent.trim().toLowerCase();
    if (btnText.includes("sell") || btnText.includes("short")) {
      order.side = "SELL";
    } else if (btnText.includes("buy") || btnText.includes("long")) {
      order.side = "BUY";
    }

    // Send to backend
    try {
      const resp = await fetch(`${BACKEND_URL}/api/v1/order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(order),
      });
      const data = await resp.json();
      console.log("[HL Paper] Backend response:", data);

      // Notify overlay
      window.postMessage(
        { type: "HL_PAPER_FILL", data },
        window.location.origin
      );
    } catch (err) {
      console.error("[HL Paper] Backend error:", err);
      window.postMessage(
        {
          type: "HL_PAPER_ERROR",
          error: "Backend offline — order blocked for safety",
        },
        window.location.origin
      );
    }
  },
  true // capture phase
);

// ---------------------------------------------------------------
// MutationObserver — watch for dynamically added order buttons
// ---------------------------------------------------------------

const observer = new MutationObserver((mutations) => {
  // The capture-phase listener handles clicks automatically.
  // The observer ensures we detect when the UI changes structure.
  // No action needed here — the click listener is always active.
});

observer.observe(document.body || document.documentElement, {
  childList: true,
  subtree: true,
});

console.log("[HL Paper] DOM interceptor loaded, paper mode:", paperModeEnabled);
