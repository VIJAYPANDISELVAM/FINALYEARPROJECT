/* ===============================
   CRONOS v3.2.1 – Frontend Script
   Render + Vercel Connected (STABLE)
=============================== */
/* ===============================
   CRONOS v3.2.1 – Frontend Script
=============================== */
/* ==================================================
   CRONOS v3.2.1 — STABLE FRONTEND SCRIPT
   GUARANTEED BUTTON FUNCTIONALITY
================================================== */

/* ---------------- GLOBAL STATE ---------------- */
var lastAnalysisResult = null;
var lastReportId = null;
var currentMode = null;

/* ---------------- BACKEND ---------------- */
var API_BASE = "https://finalyearproject-3-n6x.onrender.com";

/* ---------------- HELPERS ---------------- */
function el(id) {
  return document.getElementById(id);
}

function autoResize(t) {
  if (!t) return;
  t.style.height = "auto";
  t.style.height = Math.max(t.scrollHeight, 120) + "px";
}

/* ---------------- MODE SELECTION ---------------- */
function selectMode(mode) {
  currentMode = mode;

  el("modeSelectionPanel").style.display = "none";
  el("analysisForm").style.display = "block";

  if (mode === "COMPLIANCE") {
    el("oldConditionPanel").style.display = "none";
    el("newConditionPanel").style.display = "none";
    el("expectedOutputBadge").innerText = "02";
    el("constraintsBadge").innerText = "03";
    el("expectedOutputHint").innerText =
      "Describe the expected behavior (contract)";
    el("analyzeBtnText").innerText = "Check Compliance";
  } else {
    el("oldConditionPanel").style.display = "block";
    el("newConditionPanel").style.display = "block";
    el("expectedOutputBadge").innerText = "04";
    el("constraintsBadge").innerText = "05";
    el("expectedOutputHint").innerText =
      "Describe expected behavior after change";
    el("analyzeBtnText").innerText = "Analyze Change";
  }
}

/* ---------------- BACK ---------------- */
function goBackToModeSelection() {
  currentMode = null;
  el("modeSelectionPanel").style.display = "block";
  el("analysisForm").style.display = "none";

  el("resultBox").innerHTML =
    "<div class='empty-state'><p>Click Analyze</p></div>";
}

/* ---------------- COLLAPSE ---------------- */
function toggleCollapse() {
  var content = el("collapsibleContent");
  if (!content) return;
  content.classList.toggle("collapsed");
}

/* ---------------- RENDER RESULT ---------------- */
function renderResult(result) {
  var box = el("resultBox");

  box.className =
    "result-box " +
    (result.status === "PASS"
      ? "result-pass"
      : result.status === "FAIL"
      ? "result-fail"
      : "result-error");

  box.innerHTML = `
    <div class="result-header">
      <h3>Analysis Report</h3>
      <button onclick="toggleCollapse()">Collapse</button>
    </div>
    <div id="collapsibleContent">
      <pre>${JSON.stringify(result, null, 2)}</pre>
    </div>
  `;

  el("downloadJsonBtn").style.display = "inline-block";
  el("downloadPdfBtn").style.display = "inline-block";
}

/* ---------------- ANALYZE ---------------- */
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

  const url = `${API_BASE}/analyze`;

  // 🔁 retry once after cold start
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Bad response");

      const data = await res.json();
      lastAnalysisResult = data;
      lastReportId = data.report_id;
      renderResult(data);
      return;

    } catch (err) {
      if (attempt === 1) {
        console.warn("Backend waking up… retrying");
        await new Promise(r => setTimeout(r, 3000));
      } else {
        alert("Backend still waking up. Please try again.");
      }
    }
  }
}
/* ---------------- DOWNLOADS ---------------- */
function downloadJSON() {
  if (!lastReportId) {
    alert("Run analysis first");
    return;
  }
  window.open(API_BASE + "/report/json/" + lastReportId);
}

function downloadPDF() {
  if (!lastReportId) {
    alert("Run analysis first");
    return;
  }
  window.open(API_BASE + "/report/pdf/" + lastReportId);
}

/* ---------------- INIT ---------------- */
window.onload = function () {
  console.log("CRONOS READY");

  var areas = document.getElementsByTagName("textarea");
  for (var i = 0; i < areas.length; i++) {
    autoResize(areas[i]);
    areas[i].addEventListener("input", function () {
      autoResize(this);
    });
  }
};

/* ---------------- EXPORTS ---------------- */
window.selectMode = selectMode;
window.goBackToModeSelection = goBackToModeSelection;
window.analyzeChange = analyzeChange;
window.downloadJSON = downloadJSON;
window.downloadPDF = downloadPDF;
