/* ===============================
   CRONOS v3.2.1 – Frontend Script
=============================== */

let lastAnalysisResult = null;
let lastReportId = null;
let currentMode = null;

const API_BASE = "https://finalyearproject-3-n6x.onrender.com";

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
   ANALYZE (NO FORM SUBMIT)
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

  let res;
  try {
    res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    alert("Network error. Backend may be sleeping.");
    return;
  }

  if (!res.ok) {
    alert("Backend error. Check Render logs.");
    return;
  }

  const data = await res.json();
  lastReportId = data.report_id;

  renderResult(data);
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

  box.innerHTML = `
    <div class="result-header">
      <h3>🧠 Analysis Report</h3>
    </div>
    <pre>${JSON.stringify(result, null, 2)}</pre>
  `;

  el("downloadJsonBtn") && (el("downloadJsonBtn").style.display = "inline-flex");
  el("downloadPdfBtn") && (el("downloadPdfBtn").style.display = "inline-flex");
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
  el("analyzeBtn") &&
    el("analyzeBtn").addEventListener("click", e => {
      e.preventDefault();
      analyzeChange();
    });

  el("downloadJsonBtn")?.addEventListener("click", downloadJSON);
  el("downloadPdfBtn")?.addEventListener("click", downloadPDF);

  document.querySelectorAll("textarea").forEach(t => {
    autoResize(t);
    t.addEventListener("input", () => autoResize(t));
  });
});

/* ===============================
   GLOBAL EXPORTS
=============================== */
window.selectMode = selectMode;
