/* ===============================
   CRONOS v3.2.1 – Frontend Script
   Render + Vercel Connected
=============================== */

/* ===============================
   GLOBAL STATE
=============================== */
let lastAnalysisResult = null;
let lastReportId = null;
let currentMode = null;

/* ===============================
   🔴 BACKEND API (RENDER)
   CHANGE THIS ONLY IF RENDER URL CHANGES
=============================== */
const API_BASE = "https://finalyearproject-3-n6x.onrender.com";

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

  el("modeSelectionPanel").style.display = "none";
  el("analysisForm").style.display = "block";

  if (mode === "COMPLIANCE") {
    el("oldConditionPanel").style.display = "none";
    el("newConditionPanel").style.display = "none";

    el("expectedOutputBadge").textContent = "02";
    el("constraintsBadge").textContent = "03";
    el("expectedOutputHint").textContent =
      "Describe the expected behavior (contract)";
    el("analyzeBtnText").textContent = "Check Compliance";
  } else {
    el("oldConditionPanel").style.display = "block";
    el("newConditionPanel").style.display = "block";

    el("expectedOutputBadge").textContent = "04";
    el("constraintsBadge").textContent = "05";
    el("expectedOutputHint").textContent =
      "Describe expected behavior after change";
    el("analyzeBtnText").textContent = "Analyze Change";
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ===============================
   BACK TO MODE SELECTION
=============================== */
function goBackToModeSelection() {
  currentMode = null;

  el("modeSelectionPanel").style.display = "block";
  el("analysisForm").style.display = "none";

  const box = el("resultBox");
  box.className = "result-box";
  box.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🎯</div>
      <p>Click "Analyze" to see output here.</p>
    </div>
  `;

  ["sourceCode", "oldCondition", "newCondition", "expectedOutput"].forEach(id => {
    if (el(id)) {
      el(id).value = "";
      autoResize(el(id));
    }
  });

  el("noBehaviorChange").checked = false;
  el("allowBoundaryChange").checked = false;
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
      <button class="collapse-btn" data-collapse>Collapse</button>
    </div>

    <div id="collapsibleContent" class="collapsible-content">
      <pre>${JSON.stringify(result, null, 2)}</pre>
    </div>
  `;

  setupCollapse();

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

  if (!res.ok) {
    alert("Backend error. Check Render logs.");
    return;
  }

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
   GLOBAL EXPORTS
=============================== */
window.selectMode = selectMode;
window.goBackToModeSelection = goBackToModeSelection;
