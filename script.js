/* ===============================
   CRONOS v3.0 - Frontend Script
   Corrected: global bindings + safe init
=============================== */

/* ===============================
   GLOBAL STATE
=============================== */
let lastAnalysisResult = null;
let lastReportId = null;
let currentMode = null;

/* ===============================
   API BASE
=============================== */
const API_BASE = window.location.origin;

/* ===============================
   SAFE ELEMENT GETTER
=============================== */
function el(id) {
  const e = document.getElementById(id);
  if (!e) {
    console.warn(`⚠️ Missing element: ${id}`);
    return null;
  }
  return e;
}

/* ===============================
   AUTO-RESIZE TEXTAREAS
=============================== */
function autoResize(elm) {
  if (!elm) return;
  elm.style.height = "auto";
  elm.style.height = Math.max(elm.scrollHeight, 120) + "px";
}

/* ===============================
   MODE SELECTION
=============================== */
function selectMode(mode) {
  currentMode = mode;

  el("modeSelectionPanel")?.style && (el("modeSelectionPanel").style.display = "none");
  el("analysisForm")?.style && (el("analysisForm").style.display = "block");

  if (mode === "COMPLIANCE") {
    el("oldConditionPanel")?.style && (el("oldConditionPanel").style.display = "none");
    el("newConditionPanel")?.style && (el("newConditionPanel").style.display = "none");

    el("expectedOutputBadge") && (el("expectedOutputBadge").textContent = "02");
    el("constraintsBadge") && (el("constraintsBadge").textContent = "03");

    el("expectedOutputHint") &&
      (el("expectedOutputHint").textContent =
        "Describe the expected behavior (contract)");

    el("analyzeBtnText") && (el("analyzeBtnText").textContent = "Check Compliance");
  } else {
    el("oldConditionPanel")?.style && (el("oldConditionPanel").style.display = "block");
    el("newConditionPanel")?.style && (el("newConditionPanel").style.display = "block");

    el("expectedOutputBadge") && (el("expectedOutputBadge").textContent = "04");
    el("constraintsBadge") && (el("constraintsBadge").textContent = "05");

    el("expectedOutputHint") &&
      (el("expectedOutputHint").textContent =
        "Describe expected behavior after change");

    el("analyzeBtnText") && (el("analyzeBtnText").textContent = "Analyze Change");
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ===============================
   BACK TO MODE SELECTION
=============================== */
function goBackToModeSelection() {
  currentMode = null;

  el("modeSelectionPanel")?.style && (el("modeSelectionPanel").style.display = "block");
  el("analysisForm")?.style && (el("analysisForm").style.display = "none");

  const resultBox = el("resultBox");
  if (resultBox) {
    resultBox.className = "result-box";
    resultBox.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎯</div>
        <p>Click "Analyze" to see output here.</p>
        <span class="empty-hint">Your analysis results will appear in this section</span>
      </div>
    `;
  }

  ["sourceCode", "oldCondition", "newCondition", "expectedOutput"].forEach(id => {
    const t = el(id);
    if (t) {
      t.value = "";
      autoResize(t);
    }
  });

  el("noBehaviorChange") && (el("noBehaviorChange").checked = false);
  el("allowBoundaryChange") && (el("allowBoundaryChange").checked = false);

  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ===============================
   COLLAPSE HANDLER
=============================== */
function setupCollapse() {
  const btn = document.querySelector("[data-collapse]");
  const content = el("collapsibleContent");
  if (!btn || !content) return;

  btn.onclick = () => {
    const collapsed = content.classList.toggle("collapsed");
    btn.textContent = collapsed ? "Expand" : "Collapse";
  };
}

/* ===============================
   RENDER RESULT
=============================== */
function renderResult(result) {
  const box = el("resultBox");
  if (!box) return;

  box.className =
    "result-box " +
    (result.status === "PASS"
      ? "result-pass"
      : result.status === "FAIL"
      ? "result-fail"
      : "result-error");

  let complianceExtras = "";

  // ✅ Compliance-only AI solution block
  if (result.mode === "COMPLIANCE" && result.ai_solution) {
    complianceExtras += `
      <section class="result-section">
        <h4>🛠 AI Suggested Solution</h4>
        <pre>${escapeHtml(result.ai_solution)}</pre>
      </section>
    `;
  }

  box.innerHTML = `
    <div class="result-header">
      <h3>🧠 Analysis Report (${result.mode})</h3>
      <button class="collapse-btn" data-collapse>Collapse</button>
    </div>

    <div id="collapsibleContent" class="collapsible-content">

      <section class="result-section">
        <strong>Status:</strong> ${result.status}<br/>
        <strong>Risk Score:</strong> ${result.risk_score}
      </section>

      <section class="result-section">
        <h4>🔍 Technical Explanation</h4>
        <pre>${escapeHtml(result.technical_explanation || "N/A")}</pre>
      </section>

      ${
        result.mode === "CHANGE"
          ? `
        <section class="result-section">
          <h4>🧑 Human Explanation</h4>
          <pre>${escapeHtml(result.human_explanation || "N/A")}</pre>
        </section>
        `
          : ""
      }

      ${complianceExtras}

      <section class="result-section">
        <h4>📎 Metadata</h4>
        <pre>
Report ID: ${result.report_id}
Timestamp: ${result.timestamp}
AI Provider: ${result.ai_provider}
        </pre>
      </section>

    </div>
  `;

  setupCollapse();

  // ✅ enable downloads ONLY after success
  el("downloadJsonBtn").style.display = "inline-flex";
  el("downloadPdfBtn").style.display = "inline-flex";

  box.scrollIntoView({ behavior: "smooth" });
}
/* ===============================
   ANALYZE
=============================== */
async function analyzeChange() {
  if (!currentMode) {
    alert("Select a mode first");
    return;
  }

  const payload = {
    mode: currentMode,
    source_code: el("sourceCode")?.value || "",
    expected_output: el("expectedOutput")?.value || "",
    constraints: {
      no_behavior_change: el("noBehaviorChange")?.checked || false,
      allow_boundary_change: el("allowBoundaryChange")?.checked || false
    }
  };

  if (currentMode === "CHANGE") {
    payload.old_condition = el("oldCondition")?.value || "";
    payload.new_condition = el("newCondition")?.value || "";
  }

  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  lastAnalysisResult = data;
  lastReportId = data.report_id;

  renderResult(data);
}

/* ===============================
   DOWNLOADS
=============================== */
function downloadJSON() {
  if (!lastReportId) return alert("Run analysis first");
  window.open(`${API_BASE}/report/json/${lastReportId}`, "_blank");
}

function downloadPDF() {
  if (!lastReportId) return alert("Run analysis first");
  window.open(`${API_BASE}/report/pdf/${lastReportId}`, "_blank");
}

/* ===============================
   INIT
=============================== */
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ CRONOS Frontend Initialized");

  el("analyzeBtn")?.addEventListener("click", analyzeChange);
  el("downloadJsonBtn")?.addEventListener("click", downloadJSON);
  el("downloadPdfBtn")?.addEventListener("click", downloadPDF);

  document.querySelectorAll("textarea").forEach(t => {
    autoResize(t);
    t.addEventListener("input", () => autoResize(t));
  });
});

/* ===============================
   🔴 REQUIRED GLOBAL EXPORTS
=============================== */
window.selectMode = selectMode;
window.goBackToModeSelection = goBackToModeSelection;
function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}