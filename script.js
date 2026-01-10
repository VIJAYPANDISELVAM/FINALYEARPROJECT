let lastAnalysisResult = null;
let lastReportId = null;
let currentMode = null;

// ✅ UPDATE THIS WITH YOUR RENDER BACKEND URL
const API_BASE = "https://finalyearproject-3-n6xk.onrender.com";

/* ===============================
   SAFE ELEMENT GETTER
=============================== */
function el(id) {
  return document.getElementById(id);
}

/* ===============================
   AUTO RESIZE
=============================== */
function autoResize(t) {
  if (!t) return;
  t.style.height = "auto";
  t.style.height = Math.max(t.scrollHeight, 120) + "px";
}

/* ===============================
   MODE SELECTION
=============================== */
function selectMode(mode) {
  currentMode = mode;

  el("modeSelectionPanel") && (el("modeSelectionPanel").style.display = "none");
  el("analysisForm") && (el("analysisForm").style.display = "block");

  if (mode === "COMPLIANCE") {
    el("oldConditionPanel") && (el("oldConditionPanel").style.display = "none");
    el("newConditionPanel") && (el("newConditionPanel").style.display = "none");

    el("expectedOutputBadge") && (el("expectedOutputBadge").innerText = "02");
    el("constraintsBadge") && (el("constraintsBadge").innerText = "03");
    el("expectedOutputHint") &&
      (el("expectedOutputHint").innerText =
        "Describe the expected behavior (contract)");
    el("analyzeBtnText") &&
      (el("analyzeBtnText").innerText = "Check Compliance");
  } else {
    el("oldConditionPanel") && (el("oldConditionPanel").style.display = "block");
    el("newConditionPanel") && (el("newConditionPanel").style.display = "block");

    el("expectedOutputBadge") && (el("expectedOutputBadge").innerText = "04");
    el("constraintsBadge") && (el("constraintsBadge").innerText = "05");
    el("expectedOutputHint") &&
      (el("expectedOutputHint").innerText =
        "Describe expected behavior after change");
    el("analyzeBtnText") &&
      (el("analyzeBtnText").innerText = "Analyze Change");
  }
}

/* ===============================
   GO BACK TO MODE SELECTION
=============================== */
function goBackToModeSelection() {
  currentMode = null;
  
  el("modeSelectionPanel") && (el("modeSelectionPanel").style.display = "block");
  el("analysisForm") && (el("analysisForm").style.display = "none");
  
  el("sourceCode") && (el("sourceCode").value = "");
  el("oldCondition") && (el("oldCondition").value = "");
  el("newCondition") && (el("newCondition").value = "");
  el("expectedOutput") && (el("expectedOutput").value = "");
  
  el("noBehaviorChange") && (el("noBehaviorChange").checked = false);
  el("allowBoundaryChange") && (el("allowBoundaryChange").checked = false);
  
  el("downloadJsonBtn") && (el("downloadJsonBtn").style.display = "none");
  el("downloadPdfBtn") && (el("downloadPdfBtn").style.display = "none");
  
  const resultBox = el("resultBox");
  if (resultBox) {
    resultBox.className = "result-box";
    resultBox.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🧠</div>
        <p>Click "Analyze" to see output here.</p>
        <p class="empty-hint">Your analysis results will appear with technical explanations and AI insights.</p>
      </div>
    `;
  }
}

/* ===============================
   ANALYZE
=============================== */
async function analyzeChange() {
  if (!currentMode) {
    alert("Select a mode first");
    return;
  }

  // ✅ REQUIRED FIELD VALIDATION (NEW)
  const sourceCode = el("sourceCode")?.value.trim();
  const oldCondition = el("oldCondition")?.value.trim();
  const newCondition = el("newCondition")?.value.trim();
  const expectedOutput = el("expectedOutput")?.value.trim();

  if (
    (currentMode === "COMPLIANCE" && (!sourceCode || !expectedOutput)) ||
    (currentMode === "CHANGE" && (!oldCondition || !newCondition || !expectedOutput))
  ) {
    alert("Please fill all required fields before analyzing.");
    return;
  }

  // Show loading state
  const analyzeBtn = el("analyzeBtn");
  const analyzeBtnText = el("analyzeBtnText");
  const originalText = analyzeBtnText ? analyzeBtnText.innerText : "";
  
  if (analyzeBtnText) {
    analyzeBtnText.innerText = "Analyzing...";
  }
  if (analyzeBtn) {
    analyzeBtn.disabled = true;
  }

  const payload = {
    mode: currentMode,
    source_code: sourceCode || "",
    expected_output: expectedOutput || "",
    constraints: {
      no_behavior_change: el("noBehaviorChange")?.checked || false,
      allow_boundary_change: el("allowBoundaryChange")?.checked || false
    }
  };

  if (currentMode === "CHANGE") {
    payload.old_condition = oldCondition || "";
    payload.new_condition = newCondition || "";
  }

  let res;
  try {
    res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    console.error("Network error:", e);
    alert("Network error. Backend may be sleeping or unreachable. Please wait 30 seconds for Render to wake up.");
    
    if (analyzeBtnText) analyzeBtnText.innerText = originalText;
    if (analyzeBtn) analyzeBtn.disabled = false;
    return;
  }

  if (!res.ok) {
    const errorText = await res.text();
    console.error("Backend error:", errorText);
    alert(`Backend error (${res.status}): ${errorText}`);
    
    if (analyzeBtnText) analyzeBtnText.innerText = originalText;
    if (analyzeBtn) analyzeBtn.disabled = false;
    return;
  }

  const data = await res.json();
  lastAnalysisResult = data;
  lastReportId = data.report_id;

  renderResult(data);

  if (analyzeBtnText) analyzeBtnText.innerText = originalText;
  if (analyzeBtn) analyzeBtn.disabled = false;
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

  const formattedResult = `
<div class="result-header">
  <h3>🧠 Analysis Report</h3>
  <span class="status-badge status-${result.status.toLowerCase()}">${result.status}</span>
</div>
<div class="result-content">
  <div class="result-section">
    <h4>📋 Summary</h4>
    <p><strong>Mode:</strong> ${result.mode}</p>
    <p><strong>Status:</strong> <span class="status-${result.status.toLowerCase()}">${result.status}</span></p>
    <p><strong>Risk Score:</strong> ${result.risk_score}/100</p>
    <p><strong>AI Provider:</strong> ${result.ai_provider}</p>
  </div>
  ...
</div>
  `;

  box.innerHTML = formattedResult;

  el("downloadJsonBtn") && (el("downloadJsonBtn").style.display = "inline-flex");
  el("downloadPdfBtn") && (el("downloadPdfBtn").style.display = "inline-flex");

  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ===============================
   DOWNLOADS
=============================== */
function downloadJSON() {
  if (!lastReportId) {
    alert("Run analysis first");
    return;
  }
  window.open(`${API_BASE}/report/json/${lastReportId}`, "_blank");
}

function downloadPDF() {
  if (!lastReportId) {
    alert("Run analysis first");
    return;
  }
  window.open(`${API_BASE}/report/pdf/${lastReportId}`, "_blank");
}

/* ===============================
   INIT
=============================== */
document.addEventListener("DOMContentLoaded", () => {
  console.log("🚀 CRONOS Frontend ready!");
});
