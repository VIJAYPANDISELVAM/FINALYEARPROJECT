let lastAnalysisResult = null;
let lastReportId = null;
let currentMode = null;

// ✅ PRODUCTION API BASE - Update this after deploying to Render
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
   MODE SELECTION (SAFE)
=============================== */
function selectMode(mode) {
  console.log("🎯 Mode selected:", mode);
  currentMode = mode;

  const modePanel = el("modeSelectionPanel");
  const analysisForm = el("analysisForm");
  
  if (modePanel) modePanel.style.display = "none";
  if (analysisForm) analysisForm.style.display = "block";

  if (mode === "COMPLIANCE") {
    // Hide change-specific fields
    const oldPanel = el("oldConditionPanel");
    const newPanel = el("newConditionPanel");
    if (oldPanel) oldPanel.style.display = "none";
    if (newPanel) newPanel.style.display = "none";

    // Update badges
    const expectedBadge = el("expectedOutputBadge");
    const constraintsBadge = el("constraintsBadge");
    if (expectedBadge) expectedBadge.innerText = "02";
    if (constraintsBadge) constraintsBadge.innerText = "03";

    // Update hints
    const expectedHint = el("expectedOutputHint");
    if (expectedHint) {
      expectedHint.innerText = "Describe the expected behavior (contract)";
    }

    // Update button text
    const analyzeBtnText = el("analyzeBtnText");
    if (analyzeBtnText) analyzeBtnText.innerText = "Check Compliance";
  } else {
    // Show change-specific fields
    const oldPanel = el("oldConditionPanel");
    const newPanel = el("newConditionPanel");
    if (oldPanel) oldPanel.style.display = "block";
    if (newPanel) newPanel.style.display = "block";

    // Update badges
    const expectedBadge = el("expectedOutputBadge");
    const constraintsBadge = el("constraintsBadge");
    if (expectedBadge) expectedBadge.innerText = "04";
    if (constraintsBadge) constraintsBadge.innerText = "05";

    // Update hints
    const expectedHint = el("expectedOutputHint");
    if (expectedHint) {
      expectedHint.innerText = "Describe expected behavior after change";
    }

    // Update button text
    const analyzeBtnText = el("analyzeBtnText");
    if (analyzeBtnText) analyzeBtnText.innerText = "Analyze Change";
  }
}

/* ===============================
   GO BACK TO MODE SELECTION
=============================== */
function goBackToModeSelection() {
  console.log("⬅️ Returning to mode selection");
  currentMode = null;
  
  const modePanel = el("modeSelectionPanel");
  const analysisForm = el("analysisForm");
  
  if (modePanel) modePanel.style.display = "block";
  if (analysisForm) analysisForm.style.display = "none";
  
  // Clear all form fields
  const fields = ["sourceCode", "oldCondition", "newCondition", "expectedOutput"];
  fields.forEach(id => {
    const field = el(id);
    if (field) field.value = "";
  });
  
  // Clear checkboxes
  const noBehavior = el("noBehaviorChange");
  const allowBoundary = el("allowBoundaryChange");
  if (noBehavior) noBehavior.checked = false;
  if (allowBoundary) allowBoundary.checked = false;
  
  // Hide download buttons
  const jsonBtn = el("downloadJsonBtn");
  const pdfBtn = el("downloadPdfBtn");
  if (jsonBtn) jsonBtn.style.display = "none";
  if (pdfBtn) pdfBtn.style.display = "none";
  
  // Reset result box
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
   ANALYZE (NO FORM SUBMIT)
=============================== */
async function analyzeChange() {
  console.log("🔍 Starting analysis...");
  
  if (!currentMode) {
    alert("Select a mode first");
    return;
  }

  // Show loading state
  const analyzeBtn = el("analyzeBtn");
  const analyzeBtnText = el("analyzeBtnText");
  const originalText = analyzeBtnText?.innerText;
  
  if (analyzeBtnText) analyzeBtnText.innerText = "Analyzing...";
  if (analyzeBtn) analyzeBtn.disabled = true;

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

  console.log("📤 Sending payload:", payload);

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
    
    console.log("📥 Response status:", res.status);
  } catch (e) {
    console.error("❌ Network error:", e);
    alert("Network error. Backend may be sleeping or unreachable. Please wait 30 seconds for Render to wake up.");
    
    // Restore button
    if (analyzeBtnText && originalText) analyzeBtnText.innerText = originalText;
    if (analyzeBtn) analyzeBtn.disabled = false;
    return;
  }

  if (!res.ok) {
    const errorText = await res.text();
    console.error("❌ Backend error:", errorText);
    alert(`Backend error (${res.status}): ${errorText}`);
    
    // Restore button
    if (analyzeBtnText && originalText) analyzeBtnText.innerText = originalText;
    if (analyzeBtn) analyzeBtn.disabled = false;
    return;
  }

  const data = await res.json();
  console.log("✅ Analysis complete:", data);
  
  lastAnalysisResult = data;
  lastReportId = data.report_id;

  renderResult(data);

  // Restore button
  if (analyzeBtnText && originalText) analyzeBtnText.innerText = originalText;
  if (analyzeBtn) analyzeBtn.disabled = false;
}

/* ===============================
   RENDER RESULT
=============================== */
function renderResult(result) {
  console.log("🎨 Rendering result");
  const box = el("resultBox");
  if (!box) return;

  box.className =
    "result-box " +
    (result.status === "PASS"
      ? "result-pass"
      : result.status === "FAIL"
      ? "result-fail"
      : "result-error");

  box.innerHTML = `
    <div class="result-header">
      <h3>🧠 Analysis Report</h3>
      <span class="status-badge status-${result.status.toLowerCase()}">${result.status}</span>
    </div>
    <div class="result-content">
      <pre>${JSON.stringify(result, null, 2)}</pre>
    </div>
  `;

  // Show download buttons
  const jsonBtn = el("downloadJsonBtn");
  const pdfBtn = el("downloadPdfBtn");
  if (jsonBtn) jsonBtn.style.display = "inline-flex";
  if (pdfBtn) pdfBtn.style.display = "inline-flex";

  // Scroll to results
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ===============================
   DOWNLOADS
=============================== */
function downloadJSON() {
  console.log("📥 Downloading JSON");
  if (!lastReportId) {
    alert("Run analysis first");
    return;
  }
  window.open(`${API_BASE}/report/json/${lastReportId}`, "_blank");
}

function downloadPDF() {
  console.log("📄 Downloading PDF");
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
  console.log("🚀 CRONOS Frontend initializing...");
  
  // Analyze button
  const analyzeBtn = el("analyzeBtn");
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", e => {
      e.preventDefault();
      analyzeChange();
    });
    console.log("✅ Analyze button connected");
  } else {
    console.warn("⚠️ Analyze button not found");
  }

  // Download buttons
  const jsonBtn = el("downloadJsonBtn");
  const pdfBtn = el("downloadPdfBtn");
  
  if (jsonBtn) {
    jsonBtn.addEventListener("click", downloadJSON);
    console.log("✅ JSON download button connected");
  }
  
  if (pdfBtn) {
    pdfBtn.addEventListener("click", downloadPDF);
    console.log("✅ PDF download button connected");
  }

  // Auto-resize textareas
  document.querySelectorAll("textarea").forEach(t => {
    autoResize(t);
    t.addEventListener("input", () => autoResize(t));
  });
  console.log("✅ Textareas configured");

  console.log("✅ CRONOS Frontend initialized");
  console.log("🔗 API Base:", API_BASE);
});

/* ===============================
   GLOBAL EXPORTS (CRITICAL!)
=============================== */
window.selectMode = selectMode;
window.goBackToModeSelection = goBackToModeSelection;
window.analyzeChange = analyzeChange;
window.downloadJSON = downloadJSON;
window.downloadPDF = downloadPDF;

console.log("✅ Global functions exported to window");
