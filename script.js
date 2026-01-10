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
   ✨ NEW: Toast Notification System
=============================== */
function showToast(message, type = 'info') {
  const container = el('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️'
  };
  
  toast.innerHTML = `
    <div class="toast-icon">${icons[type] || icons.info}</div>
    <div class="toast-message">${message}</div>
  `;
  
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ===============================
   ✨ NEW: Loading Overlay Control
=============================== */
function showLoading() {
  const overlay = el('loadingOverlay');
  if (overlay) overlay.classList.add('active');
}

function hideLoading() {
  const overlay = el('loadingOverlay');
  if (overlay) overlay.classList.remove('active');
}

/* ===============================
   ✨ NEW: Character Counter Update
=============================== */
function updateCharCounter(textareaId, counterId) {
  const textarea = el(textareaId);
  const counter = el(counterId);
  if (!textarea || !counter) return;
  
  const length = textarea.value.length;
  counter.textContent = `${length} character${length !== 1 ? 's' : ''}`;
  
  // Visual feedback for large inputs
  if (length > 1000) {
    counter.style.color = 'var(--warning)';
  } else if (length > 500) {
    counter.style.color = 'var(--text-tertiary)';
  } else {
    counter.style.color = 'var(--text-muted)';
  }
}

/* ===============================
   ✨ NEW: Progress Indicator Update
=============================== */
function updateProgress(step) {
  const steps = document.querySelectorAll('.progress-step');
  steps.forEach((s, index) => {
    if (index < step) {
      s.classList.add('completed');
      s.classList.remove('active');
    } else if (index === step - 1) {
      s.classList.add('active');
      s.classList.remove('completed');
    } else {
      s.classList.remove('active', 'completed');
    }
  });
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

  // ✨ Show toast notification
  showToast(`${mode === 'CHANGE' ? 'Change Analysis' : 'Compliance'} mode selected`, 'success');

  // ✨ Scroll to top smoothly
  window.scrollTo({ top: 0, behavior: 'smooth' });

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

  // ✨ Reset progress indicator
  updateProgress(1);
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

  // ✨ Update character counters
  updateCharCounter('sourceCode', 'sourceCodeCounter');
  updateCharCounter('oldCondition', 'oldConditionCounter');
  updateCharCounter('newCondition', 'newConditionCounter');
  updateCharCounter('expectedOutput', 'expectedOutputCounter');

  // ✨ Show toast
  showToast('Form reset - Select a mode to start', 'info');

  // ✨ Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ===============================
   ✨ NEW: Clear All Fields
=============================== */
function clearAllFields() {
  if (!confirm('Are you sure you want to clear all fields?')) return;

  el("sourceCode") && (el("sourceCode").value = "");
  el("oldCondition") && (el("oldCondition").value = "");
  el("newCondition") && (el("newCondition").value = "");
  el("expectedOutput") && (el("expectedOutput").value = "");
  
  el("noBehaviorChange") && (el("noBehaviorChange").checked = false);
  el("allowBoundaryChange") && (el("allowBoundaryChange").checked = false);

  // Update all textareas
  document.querySelectorAll('textarea').forEach(t => {
    autoResize(t);
  });

  // Update character counters
  updateCharCounter('sourceCode', 'sourceCodeCounter');
  updateCharCounter('oldCondition', 'oldConditionCounter');
  updateCharCounter('newCondition', 'newConditionCounter');
  updateCharCounter('expectedOutput', 'expectedOutputCounter');

  showToast('All fields cleared', 'success');
  updateProgress(1);
}

/* ===============================
   ANALYZE
=============================== */
async function analyzeChange() {
  if (!currentMode) {
    showToast('Please select a mode first', 'error');
    return;
  }

  /* ✅ REQUIRED FIELD VALIDATION */
  const sourceCode = el("sourceCode")?.value.trim();
  const oldCondition = el("oldCondition")?.value.trim();
  const newCondition = el("newCondition")?.value.trim();
  const expectedOutput = el("expectedOutput")?.value.trim();

  if (
    (currentMode === "COMPLIANCE" &&
      (!sourceCode || !expectedOutput)) ||
    (currentMode === "CHANGE" &&
      (!oldCondition || !newCondition || !expectedOutput))
  ) {
    showToast('Please fill all required fields before analyzing', 'error');
    return;
  }

  // ✨ Show loading overlay
  showLoading();

  // ✨ Update progress
  updateProgress(4);

  // Show loading state
  const analyzeBtn = el("analyzeBtn");
  const analyzeBtnText = el("analyzeBtnText");
  const btnSpinner = analyzeBtn?.querySelector('.btn-spinner');
  const originalText = analyzeBtnText ? analyzeBtnText.innerText : "";
  
  if (analyzeBtnText) {
    analyzeBtnText.innerText = "Analyzing";
  }
  if (btnSpinner) {
    btnSpinner.style.display = "inline-block";
  }
  if (analyzeBtn) {
    analyzeBtn.disabled = true;
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
      headers: { 
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    console.error("Network error:", e);
    showToast('Network error. Backend may be sleeping. Please wait 30s and retry.', 'error');
    hideLoading();
    
    if (analyzeBtnText) analyzeBtnText.innerText = originalText;
    if (btnSpinner) btnSpinner.style.display = "none";
    if (analyzeBtn) analyzeBtn.disabled = false;
    return;
  }

  if (!res.ok) {
    const errorText = await res.text();
    console.error("Backend error:", errorText);
    showToast(`Backend error (${res.status}): ${errorText.substring(0, 100)}`, 'error');
    hideLoading();
    
    if (analyzeBtnText) analyzeBtnText.innerText = originalText;
    if (btnSpinner) btnSpinner.style.display = "none";
    if (analyzeBtn) analyzeBtn.disabled = false;
    return;
  }

  const data = await res.json();
  lastAnalysisResult = data;
  lastReportId = data.report_id;

  renderResult(data);

  // ✨ Hide loading overlay
  hideLoading();

  // ✨ Show success toast
  showToast(`Analysis complete: ${data.status}`, data.status === 'PASS' ? 'success' : 'warning');

  if (analyzeBtnText) analyzeBtnText.innerText = originalText;
  if (btnSpinner) btnSpinner.style.display = "none";
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

  <div class="result-section">
    <h4>🔍 Analysis Findings</h4>
    ${
      result.analyzer_findings.length > 0
        ? result.analyzer_findings
            .map(
              f => `
              <div class="finding">
                <strong>${f.name}</strong> (Risk: ${f.risk})
                <ul>${f.findings.map(x => `<li>${x}</li>`).join("")}</ul>
              </div>
            `
            )
            .join("")
        : '<p style="color:#4ade80;">✅ No issues found</p>'
    }
  </div>

  ${
    result.technical_explanation
      ? `
    <div class="result-section">
      <h4>🔬 Technical Explanation</h4>
      <p id="technicalExplanationText"></p>
    </div>
  `
      : ""
  }

  ${
    result.human_explanation
      ? `
    <div class="result-section">
      <h4>💡 Human-Readable Explanation</h4>
      <p id="humanExplanationText"></p>
    </div>
  `
      : ""
  }

  ${
    result.ai_solution
      ? `
    <div class="result-section">
      <h4>🛠️ AI Solution</h4>
      <p id="aiSolutionText"></p>
    </div>
  `
      : ""
  }

  <div class="result-section">
    <h4>📊 Technical Details</h4>
    <pre style="background:#1e293b;padding:1rem;border-radius:8px;overflow-x:auto;">
${JSON.stringify(result.semantic_signals, null, 2)}
    </pre>
  </div>

  <details style="margin-top:1rem;">
    <summary style="cursor:pointer;font-weight:600;padding:0.5rem;background:#1e293b;border-radius:4px;">
      📄 View Full JSON Report
    </summary>
    <pre style="margin-top:0.5rem;background:#0f172a;padding:1rem;border-radius:8px;overflow-x:auto;max-height:400px;">
${JSON.stringify(result, null, 2)}
    </pre>
  </details>
</div>
  `;

  // Render base HTML
  box.innerHTML = formattedResult;

  // ✅ SAFE text injection
  const techEl = document.getElementById("technicalExplanationText");
  if (techEl) techEl.textContent = result.technical_explanation || "";

  const humanEl = document.getElementById("humanExplanationText");
  if (humanEl) humanEl.textContent = result.human_explanation || "";

  const aiEl = document.getElementById("aiSolutionText");
  if (aiEl) aiEl.textContent = result.ai_solution || "";

  el("downloadJsonBtn") && (el("downloadJsonBtn").style.display = "inline-flex");
  el("downloadPdfBtn") && (el("downloadPdfBtn").style.display = "inline-flex");

  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ===============================
   DOWNLOADS
=============================== */
function downloadJSON() {
  if (!lastReportId) {
    showToast('Run analysis first to download report', 'warning');
    return;
  }
  showToast('Downloading JSON report...', 'info');
  window.open(`${API_BASE}/report/json/${lastReportId}`, "_blank");
}

function downloadPDF() {
  if (!lastReportId) {
    showToast('Run analysis first to download report', 'warning');
    return;
  }
  showToast('Downloading PDF report...', 'info');
  window.open(`${API_BASE}/report/pdf/${lastReportId}`, "_blank");
}

/* ===============================
   ✨ NEW: Scroll to Top
=============================== */
function handleScroll() {
  const scrollBtn = el('scrollToTop');
  if (!scrollBtn) return;
  
  if (window.scrollY > 300) {
    scrollBtn.style.display = 'block';
  } else {
    scrollBtn.style.display = 'none';
  }
}

function scrollToTop() {
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  });
}

/* ===============================
   ✨ NEW: Form Field Tracking
=============================== */
function trackFieldCompletion() {
  const sourceCode = el("sourceCode")?.value.trim();
  const expectedOutput = el("expectedOutput")?.value.trim();
  
  if (sourceCode && !expectedOutput) {
    updateProgress(2);
  } else if (sourceCode && expectedOutput) {
    updateProgress(3);
  } else if (sourceCode) {
    updateProgress(1);
  }
}

/* ===============================
   INIT - ATTACH ALL EVENT LISTENERS
=============================== */
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ CRONOS Frontend v3.2 initializing...");
  console.log("🔗 API Base:", API_BASE);

  // ✨ Show welcome toast
  setTimeout(() => {
    showToast('Welcome to CRONOS! Select an analysis mode to begin.', 'info');
  }, 500);

  // Mode selection
  const modeButtons = document.querySelectorAll(".mode-select-btn");
  modeButtons.forEach(btn => {
    btn.addEventListener("click", function() {
      const mode = this.getAttribute("data-mode");
      selectMode(mode);
    });
  });

  // Navigation buttons
  const backBtn = el("backToModeBtn");
  backBtn && backBtn.addEventListener("click", goBackToModeSelection);

  const analyzeBtn = el("analyzeBtn");
  analyzeBtn && analyzeBtn.addEventListener("click", e => {
    e.preventDefault();
    analyzeChange();
  });

  // ✨ NEW: Clear all button
  const clearBtn = el("clearAllBtn");
  clearBtn && clearBtn.addEventListener("click", clearAllFields);

  // Download buttons
  el("downloadJsonBtn")?.addEventListener("click", downloadJSON);
  el("downloadPdfBtn")?.addEventListener("click", downloadPDF);

  // ✨ NEW: Scroll to top button
  const scrollBtn = el("scrollToTop");
  scrollBtn && scrollBtn.addEventListener("click", scrollToTop);
  window.addEventListener("scroll", handleScroll);

  // Textarea auto-resize and character counters
  document.querySelectorAll("textarea").forEach(t => {
    autoResize(t);
    
    t.addEventListener("input", () => {
      autoResize(t);
      
      // ✨ Update character counter
      const counterId = t.id + 'Counter';
      updateCharCounter(t.id, counterId);
      
      // ✨ Track progress
      trackFieldCompletion();
    });

    // ✨ Initialize character counters
    const counterId = t.id + 'Counter';
    updateCharCounter(t.id, counterId);
  });

  // ✨ NEW: Add keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to analyze
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      if (currentMode && el('analyzeBtn')) {
        e.preventDefault();
        analyzeChange();
      }
    }
    
    // Escape to go back
    if (e.key === 'Escape' && currentMode) {
      goBackToModeSelection();
    }
  });

  console.log("✅ CRONOS Frontend ready!");
  console.log("💡 Tip: Use Ctrl+Enter to analyze, Escape to go back");
});

function escapeHTML(text) {
  if (typeof text !== "string") return text;
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
