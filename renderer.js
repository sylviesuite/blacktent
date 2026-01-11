// DOM
const diagnoseButton = document.getElementById("diagnose");
const clearButton = document.getElementById("clear");
const exportButton = document.getElementById("export");
const autoRunCheckbox = document.getElementById("auto-run");
const statusEl = document.getElementById("status");
const lastRunEl = document.getElementById("last-run");
const checksEl = document.getElementById("checks");
const suggestedEl = document.getElementById("suggested");
const selectFileButton = document.getElementById("select-file");
const runRedactionButton = document.getElementById("run-redaction");
const redactionPreview = document.getElementById("redaction-preview");
const confirmPreviewButton = document.getElementById("confirm-preview");
const dryRunPlanSection = document.getElementById("dry-run-plan");
const dryRunStatusEl = document.getElementById("dry-run-status");
const dryRunCountsEl = document.getElementById("dry-run-counts");
const dryRunRiskEl = document.getElementById("dry-run-risk");
const dryRunSamplesEl = document.getElementById("dry-run-samples");

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
let previewStatus = null;
let previewConfirmed = false;
let selectedFileMeta = null;
let currentPreviewText = "";
let redactionPlan = null;

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

function clearRedactionPlan() {
  redactionPlan = null;
  currentPreviewText = "";
  selectedFileMeta = null;
  if (dryRunPlanSection) {
    dryRunPlanSection.style.display = "none";
  }
  if (dryRunStatusEl) {
    dryRunStatusEl.textContent = "Run the dry-run to see potential matches.";
  }
  if (dryRunCountsEl) {
    dryRunCountsEl.innerHTML = "";
  }
  if (dryRunRiskEl) {
    dryRunRiskEl.textContent = "";
  }
  if (dryRunSamplesEl) {
    dryRunSamplesEl.innerHTML = "";
  }
  updateExportAvailability();
}

const EMAIL_REGEX = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
const PHONE_REGEX =
  /(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?){1,3}\d{3,4}/g;
const URL_REGEX = /\b(?:https?:\/\/|www\.)[^\s]+/gi;
const API_KEY_REGEX = /\b[A-Za-z0-9_-]{24,}\b/g;

function collectMatches(text, pattern) {
  let flags = pattern.flags || "";
  if (!flags.includes("g")) {
    flags += "g";
  }
  const regex = new RegExp(pattern.source, flags);
  const matches = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    matches.push(match[0]);
  }
  return matches;
}

function uniqueSamples(values, limit = 3) {
  const seen = new Set();
  const result = [];
  for (const value of values) {
    if (result.length >= limit) break;
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}

function collectApiKeyMatches(text) {
  const tokens = collectMatches(text, API_KEY_REGEX);
  const lines = text.split(/\r?\n/);
  const keywordRegex = /\b(?:key|token|secret|api_key|bearer)\b/i;
  const keywordMatches = [];
  for (const line of lines) {
    if (keywordRegex.test(line)) {
      const trimmed = line.trim();
      if (trimmed) {
        keywordMatches.push(trimmed);
      }
    }
  }
  return tokens.concat(keywordMatches);
}

function formatBytes(bytes) {
  if (bytes == null) return "size unknown";
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function buildRedactionPlan(text) {
  const emails = collectMatches(text, EMAIL_REGEX);
  const phones = collectMatches(text, PHONE_REGEX);
  const urls = collectMatches(text, URL_REGEX);
  const apiKeys = collectApiKeyMatches(text);
  const counts = {
    emails: emails.length,
    phones: phones.length,
    urls: urls.length,
    apiKeys: apiKeys.length,
  };
  counts.total =
    counts.emails + counts.phones + counts.urls + counts.apiKeys;
  const samples = {
    emails: uniqueSamples(emails),
    phones: uniqueSamples(phones),
    urls: uniqueSamples(urls),
    apiKeys: uniqueSamples(apiKeys),
  };
  const flags = [];
  if (counts.apiKeys > 0) flags.push("POSSIBLE_PRIVATE_KEY");
  if (counts.emails > 5) flags.push("MANY_EMAILS");
  if (counts.phones > 3) flags.push("MANY_PHONE_NUMBERS");
  if (counts.urls > 5) flags.push("MANY_URLS");
  if (counts.total > 30) flags.push("HIGH_SENSITIVITY");
  if (counts.total === 0) flags.push("NO_DETECTIONS");
  return {
    createdAt: new Date().toISOString(),
    source: {
      name: selectedFileMeta?.name || "Selected file",
      sizeBytes: selectedFileMeta?.sizeBytes ?? null,
    },
    counts,
    samples,
    riskFlags: flags,
  };
}

function renderDryRunPlan(plan) {
  if (!dryRunPlanSection) return;
  if (!plan) {
    dryRunPlanSection.style.display = "none";
    if (dryRunStatusEl) {
      dryRunStatusEl.textContent = "Run the dry-run to see potential matches.";
    }
    if (dryRunCountsEl) {
      dryRunCountsEl.innerHTML = "";
    }
    if (dryRunRiskEl) {
      dryRunRiskEl.textContent = "";
    }
    if (dryRunSamplesEl) {
      dryRunSamplesEl.innerHTML = "";
    }
    return;
  }
  dryRunPlanSection.style.display = "block";
  if (dryRunStatusEl) {
    const sizeLabel = formatBytes(plan.source.sizeBytes);
    dryRunStatusEl.textContent = `Plan generated from ${plan.source.name} (${sizeLabel}) at ${new Date(
      plan.createdAt
    ).toLocaleString()}.`;
  }
  if (dryRunCountsEl) {
    dryRunCountsEl.innerHTML = "";
    const fragment = document.createDocumentFragment();
    const entries = [
      ["emails", "Emails"],
      ["phones", "Phone numbers"],
      ["urls", "URLs"],
      ["apiKeys", "API keys/secrets"],
      ["total", "Total matches"],
    ];
    entries.forEach(([key, label]) => {
      const value = plan.counts[key] ?? 0;
      const badge = document.createElement("div");
      badge.style.padding = "0.4rem 0.6rem";
      badge.style.border = "1px solid #cbd5f5";
      badge.style.borderRadius = "6px";
      badge.style.background = "#fff";
      badge.style.minWidth = "140px";
      badge.style.fontSize = "0.85rem";
      badge.style.lineHeight = "1.3";
      const strong = document.createElement("strong");
      strong.style.display = "block";
      strong.textContent = label;
      const valueSpan = document.createElement("span");
      valueSpan.textContent = value.toString();
      badge.appendChild(strong);
      badge.appendChild(valueSpan);
      fragment.appendChild(badge);
    });
    dryRunCountsEl.appendChild(fragment);
  }
  if (dryRunRiskEl) {
    dryRunRiskEl.textContent =
      plan.riskFlags.length > 0
        ? `Risk flags: ${plan.riskFlags.join(", ")}`
        : "Risk flags: none detected.";
  }
  if (dryRunSamplesEl) {
    dryRunSamplesEl.innerHTML = "";
    const sampleLabels = {
      emails: "Emails",
      phones: "Phone numbers",
      urls: "URLs",
      apiKeys: "API keys/secrets",
    };
    Object.entries(plan.samples).forEach(([key, values]) => {
      const section = document.createElement("div");
      section.style.marginTop = "0.6rem";
      const title = document.createElement("strong");
      title.textContent = `${sampleLabels[key] || key} samples (${values.length})`;
      section.appendChild(title);
      if (values.length === 0) {
        const empty = document.createElement("div");
        empty.style.color = "#475569";
        empty.style.fontSize = "0.85rem";
        empty.textContent = "None detected.";
        section.appendChild(empty);
      } else {
        const list = document.createElement("ul");
        list.style.margin = "0.2rem 0 0";
        list.style.paddingLeft = "1.1rem";
        list.style.color = "#0f172a";
        list.style.fontSize = "0.85rem";
        values.forEach((value) => {
          const item = document.createElement("li");
          item.textContent = value;
          list.appendChild(item);
        });
        section.appendChild(list);
      }
      dryRunSamplesEl.appendChild(section);
    });
  }
}

function updateExportAvailability() {
  exportButton.disabled = !redactionPlan;
}

function updateConfirmationState(show) {
  previewConfirmed = false;
  if (confirmPreviewButton) {
    confirmPreviewButton.style.display = show ? "inline-block" : "none";
  }
  if (!show) {
    previewStatus = null;
    clearRedactionPlan();
  }
  runRedactionButton.disabled = true;
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
    updateConfirmationState(false);
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
    updateConfirmationState(false);
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

if (selectFileButton) {
  selectFileButton.addEventListener("click", async () => {
    setStatus("Selecting file...", null);
    const result = await window.redaction.selectFile();
    if (!result.ok) {
      redactionPreview.textContent = result.error || "File selection cancelled.";
      runRedactionButton.disabled = true;
      updateConfirmationState(false);
      return;
    }
    const read = await window.redaction.readFileText(result.path);
    if (!read.ok) {
      redactionPreview.textContent = read.error;
      runRedactionButton.disabled = true;
      updateConfirmationState(false);
      if (read.error?.includes("large")) {
        setStatus("File too large (>2MB). Please select a smaller text file.", "warning");
        console.debug("redaction:file-size-rejected", result.path);
      } else if (read.error?.includes("Binary")) {
        setStatus("Binary file detected. Only UTF-8 text files are supported.", "warning");
        console.debug("redaction:binary-rejected", result.path);
      } else {
        setStatus(read.error, null);
        console.error("redaction:read-error", read.error);
      }
      return;
    }
    const preview = read.text.slice(0, 4000);
    const truncated = read.text.length > 4000 ? "\n...(truncated)" : "";
    redactionPreview.textContent = `Selected: ${result.name} (${result.path})\n\n${preview}${truncated}`;
    runRedactionButton.disabled = true;
    previewStatus = "success";
    updateConfirmationState(true);
    setStatus("Preview loaded (showing first 4,000 characters)", "ok");
    console.debug("redaction:preview-success", result.path);
  });
}

if (runRedactionButton) {
  runRedactionButton.addEventListener("click", () => {
    redactionPreview.textContent = "Redaction logic pending.";
  });
}

if (confirmPreviewButton) {
  confirmPreviewButton.addEventListener("click", () => {
    if (previewStatus !== "success") {
      return;
    }
    previewConfirmed = true;
    runRedactionButton.disabled = false;
    setStatus("Preview confirmed; redaction can run next.", "ok");
  });
}

// Init
applyAutoRunSetting(getAutoRunSetting());
loadLastResult();
updateExportAvailability();
maybeAutoRun();

