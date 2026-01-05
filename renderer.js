// DOM
const diagnoseButton = document.getElementById("diagnose");
const clearButton = document.getElementById("clear");
const exportButton = document.getElementById("export");
const autoRunCheckbox = document.getElementById("auto-run");
const statusEl = document.getElementById("status");
const lastRunEl = document.getElementById("last-run");
const checksEl = document.getElementById("checks");
const suggestedEl = document.getElementById("suggested");

// Config
const STATUS_COLORS = {
  ok: "#2c7a4b",
  warning: "#9f640b",
};

const CHECK_HINTS = {
  dev_server:
    "Why this matters: ensures your local dev workspace is reachable in the browser.",
  dependencies:
    "Why this matters: missing node_modules can block startup.",
  node_version: "Why this matters: Node mismatches often cause build failures.",
};

// Storage keys
const AUTO_RUN_KEY = "bootDoctor:autoRun";
const LAST_RESULT_KEY = "bootDoctor:lastResult";
const LAST_RUN_KEY = "bootDoctor:lastRun";

// State
let copyTimer = null;
let resultStatusText = "Status pending.";
let autoRunTriggered = false;
let lastResult = null;

// Helpers
function setStatus(text, level) {
  statusEl.textContent = text;
  if (level && STATUS_COLORS[level]) statusEl.style.color = STATUS_COLORS[level];
  else statusEl.style.removeProperty("color");
}

function resetView() {
  checksEl.innerHTML = "";
  suggestedEl.innerHTML = "";
}

function updateExportAvailability() {
  exportButton.disabled = !lastResult;
}

function renderChecks(checks) {
  resetView();

  (checks || []).forEach((check) => {
    const row = document.createElement("div");
    row.style.marginTop = "0.75rem";
    row.style.padding = "0.8rem";
    row.style.border = "1px solid #e2e8f0";
    row.style.borderRadius = "8px";
    row.style.background = "#fff";
    row.style.boxShadow = "0 1px 3px rgba(15,23,42,0.05)";

    const title = document.createElement("strong");
    title.textContent = `${check.title}:`;
    title.style.fontSize = "1rem";

    const message = document.createElement("p");
    message.style.margin = "0.3rem 0 0";
    message.style.color = "#0f172a";
    message.style.fontWeight = 500;
    message.textContent = check.message || "";

    row.appendChild(title);
    row.appendChild(message);

    const hintText = CHECK_HINTS[check.name] || "";
    if (hintText) {
      const hint = document.createElement("div");
      hint.style.fontSize = "0.85rem";
      hint.style.color = "#475569";
      hint.style.marginTop = "0.2rem";
      hint.style.lineHeight = "1.2";
      hint.textContent = hintText;
      row.appendChild(hint);
    }

    checksEl.appendChild(row);
  });
}

function renderSuggestedUrl(url) {
  suggestedEl.innerHTML = "";
  if (!url) return;

  const row = document.createElement("div");
  row.style.marginTop = "1rem";
  row.style.display = "flex";
  row.style.alignItems = "center";
  row.style.gap = "0.5rem";

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.textContent = url;
  anchor.target = "_blank";

  const copyButton = document.createElement("button");
  copyButton.textContent = "Copy URL";
  copyButton.addEventListener("click", async () => {
    await navigator.clipboard.writeText(url);

    // flash status
    const level = (lastResult && lastResult.status) || null;
    setStatus("Copied URL!", level);
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => {
      setStatus(resultStatusText, level);
    }, 2000);
  });

  const openButton = document.createElement("button");
  openButton.textContent = "Open URL";
  openButton.addEventListener("click", () => window.open(url, "_blank"));

  row.appendChild(anchor);
  row.appendChild(copyButton);
  row.appendChild(openButton);
  suggestedEl.appendChild(row);
}

function getAutoRunSetting() {
  return localStorage.getItem(AUTO_RUN_KEY) === "1";
}

function applyAutoRunSetting(value) {
  localStorage.setItem(AUTO_RUN_KEY, value ? "1" : "0");
  autoRunCheckbox.checked = !!value;
}

function persistResult(result) {
  localStorage.setItem(LAST_RESULT_KEY, JSON.stringify(result));
  localStorage.setItem(LAST_RUN_KEY, new Date().toISOString());
  lastResult = result;
  updateExportAvailability();
}

function clearPersisted() {
  localStorage.removeItem(LAST_RESULT_KEY);
  localStorage.removeItem(LAST_RUN_KEY);
  lastResult = null;
  updateExportAvailability();
}

function loadLastResult() {
  const stored = localStorage.getItem(LAST_RESULT_KEY);
  const lastRun = localStorage.getItem(LAST_RUN_KEY);

  if (!stored || !lastRun) {
    lastRunEl.textContent = "Last run: —";
    resetView();
    resultStatusText = "Status pending.";
    setStatus(resultStatusText, null);
    lastResult = null;
    updateExportAvailability();
    return null;
  }

  try {
    lastResult = JSON.parse(stored);
  } catch {
    // corrupted storage
    clearPersisted();
    lastRunEl.textContent = "Last run: —";
    resetView();
    resultStatusText = "Status pending.";
    setStatus(resultStatusText, null);
    return null;
  }

  lastRunEl.textContent = `Last run: ${new Date(lastRun).toLocaleString()}`;

  renderChecks(lastResult.checks || []);
  renderSuggestedUrl(lastResult.suggested_url || null);

  resultStatusText = lastResult.status === "ok" ? "OK" : "Warning";
  setStatus(resultStatusText, lastResult.status);

  updateExportAvailability();
  return lastResult;
}

// verify preload API
if (typeof window.bootDoctor === "undefined") {
  setStatus("bootDoctor bridge unavailable", null);
  console.error("bootDoctor preload API missing");
} 

async function runScan() {
  if (diagnoseButton.disabled) return;

  diagnoseButton.disabled = true;
  setStatus("Scanning...", null);
  resetView();

  try {
    let result;
    try {
      result = await window.bootDoctor.scan();
    } catch (err) {
      setStatus(`Error: ${err?.message || err}`, null);
      return;
    }

    persistResult(result);
    loadLastResult();
  } catch (err) {
    setStatus(`Error: ${err?.message || err}`, null);
  } finally {
    diagnoseButton.disabled = false;
  }
}

function exportLastResult() {
  if (!lastResult) return;

  const timestamp = new Date()
    .toISOString()
    .replace(/[:]/g, "-")
    .replace(/\..+/, "");
  const filename = `blacktent-boot-doctor-${timestamp}.json`;

  const blob = new Blob([JSON.stringify(lastResult, null, 2)], {
    type: "application/json",
  });

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function maybeAutoRun() {
  if (getAutoRunSetting() && !autoRunTriggered && !diagnoseButton.disabled) {
    autoRunTriggered = true;
    runScan();
  }
}

// Events
diagnoseButton.addEventListener("click", runScan);

clearButton.addEventListener("click", () => {
  clearPersisted();
  resetView();
  resultStatusText = "Status pending.";
  setStatus(resultStatusText, null);
  lastRunEl.textContent = "Last run: —";
});

exportButton.addEventListener("click", exportLastResult);

autoRunCheckbox.addEventListener("change", (event) => {
  applyAutoRunSetting(event.target.checked);
  if (event.target.checked) maybeAutoRun();
});

// Init
applyAutoRunSetting(getAutoRunSetting());
loadLastResult();
updateExportAvailability();
maybeAutoRun();

