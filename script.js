// CRONOS Professional - Production Configuration
// Version: 3.2 Professional - Vercel + Render

let lastAnalysisResult = null;
let lastReportId = null;
let currentMode = null;
let analysisInProgress = false;

// 🔥 PRODUCTION: Use your Render backend URL
const API_BASE = "https://finalyearproject-3-n6xk.onrender.com";

// ========================================
// Utility Functions
// ========================================
const $ = (id) => document.getElementById(id);
const $$ = (selector) => document.querySelectorAll(selector);

// ========================================
// Toast Notification System
// ========================================
const Toast = {
  container: null,
  
  init() {
    this.container = $('toastContainer');
  },
  
  show(message, type = 'info') {
    if (!this.container) return;
    
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'i'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${icons[type]}</div>
      <div class="toast-message">${message}</div>
    `;
    
    this.container.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'toastFadeOut 300ms ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
};

// ========================================
// Analysis Loader Control
// ========================================
const Loader = {
  element: null,
  steps: ['Parsing AST', 'Semantic Analysis', 'Risk Assessment', 'AI Validation'],
  currentStep: 0,
  stepInterval: null,
  
  init() {
    this.element = $('analysisLoader');
  },
  
  show() {
    if (!this.element) return;
    this.element.classList.add('active');
    this.currentStep = 0;
    this.updateSteps();
    this.startStepAnimation();
  },
  
  hide() {
    if (!this.element) return;
    this.stopStepAnimation();
    this.element.classList.remove('active');
  },
  
  startStepAnimation() {
    this.stopStepAnimation();
    this.stepInterval = setInterval(() => {
      this.currentStep = (this.currentStep + 1) % this.steps.length;
      this.updateSteps();
    }, 800);
  },
  
  stopStepAnimation() {
    if (this.stepInterval) {
      clearInterval(this.stepInterval);
      this.stepInterval = null;
    }
  },
  
  updateSteps() {
    const stepElements = $$('.status-steps .step');
    stepElements.forEach((el, index) => {
      el.classList.toggle('active', index === this.currentStep);
    });
  }
};

// ========================================
// Progress Tracker
// ========================================
const ProgressTracker = {
  update(step) {
    const steps = $$('.tracker-step');
    steps.forEach((el, index) => {
      if (index < step) {
        el.classList.add('completed');
        el.classList.remove('active');
      } else if (index === step - 1) {
        el.classList.add('active');
        el.classList.remove('completed');
      } else {
        el.classList.remove('active', 'completed');
      }
    });
  },
  
  reset() {
    const steps = $$('.tracker-step');
    steps.forEach(el => {
      el.classList.remove('active', 'completed');
    });
    if (steps[0]) steps[0].classList.add('active');
  }
};

// ========================================
// Character Counter
// ========================================
const CharCounter = {
  update(textareaId) {
    const textarea = $(textareaId);
    const counter = $(textareaId + 'Counter');
    if (!textarea || !counter) return;
    
    const length = textarea.value.length;
    counter.textContent = `${length} char${length !== 1 ? 's' : ''}`;
  },
  
  initAll() {
    ['sourceCode', 'oldCondition', 'newCondition', 'expectedOutput'].forEach(id => {
      this.update(id);
    });
  }
};

// ========================================
// Auto Resize Textareas
// ========================================
function autoResize(textarea) {
  if (!textarea) return;
  textarea.style.height = 'auto';
  textarea.style.height = Math.max(textarea.scrollHeight, 120) + 'px';
}

// ========================================
// Mode Selection
// ========================================
function selectMode(mode) {
  currentMode = mode;
  
  $('modeSelectionPanel').style.display = 'none';
  $('analysisForm').style.display = 'block';
  
  Toast.show(`${mode === 'CHANGE' ? 'Change Analysis' : 'Compliance Check'} mode activated`, 'success');
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
  
  if (mode === 'COMPLIANCE') {
    $('oldConditionPanel').style.display = 'none';
    $('newConditionPanel').style.display = 'none';
    $('expectedOutputLabel').textContent = 'Expected Behavior Contract';
  } else {
    $('oldConditionPanel').style.display = 'block';
    $('newConditionPanel').style.display = 'block';
    $('expectedOutputLabel').textContent = 'Expected Behavior';
  }
  
  ProgressTracker.reset();
}

// ========================================
// Back to Mode Selection
// ========================================
function goBackToModeSelection() {
  currentMode = null;
  
  $('modeSelectionPanel').style.display = 'block';
  $('analysisForm').style.display = 'none';
  $('resultsSection').style.display = 'none';
  
  clearAllFields();
  Toast.show('Form reset - Select a mode to begin', 'info');
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ========================================
// Clear All Fields
// ========================================
function clearAllFields() {
  ['sourceCode', 'oldCondition', 'newCondition', 'expectedOutput'].forEach(id => {
    const el = $(id);
    if (el) {
      el.value = '';
      autoResize(el);
    }
  });
  
  ['noBehaviorChange', 'allowBoundaryChange'].forEach(id => {
    const el = $(id);
    if (el) el.checked = false;
  });
  
  CharCounter.initAll();
  ProgressTracker.reset();
  
  $('resultsSection').style.display = 'none';
}

// ========================================
// Backend Connection Test
// ========================================
async function testBackendConnection() {
  try {
    console.log('🔍 Testing backend connection to:', API_BASE);
    
    const response = await fetch(`${API_BASE}/`, {
      method: 'GET',
      headers: { 
        'Accept': 'application/json'
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('✓ Backend connected:', data);
      Toast.show('Backend connection established', 'success');
      return true;
    } else {
      console.error('✕ Backend error:', response.status);
      Toast.show('Backend connection failed - Render may be sleeping. Please wait 30s and retry.', 'warning');
      return false;
    }
  } catch (e) {
    console.error('✕ Cannot reach backend:', e);
    Toast.show('Backend is waking up... Please wait 30 seconds for Render.', 'warning');
    return false;
  }
}

// ========================================
// Field Validation
// ========================================
function validateFields() {
  const sourceCode = $('sourceCode')?.value.trim();
  const oldCondition = $('oldCondition')?.value.trim();
  const newCondition = $('newCondition')?.value.trim();
  const expectedOutput = $('expectedOutput')?.value.trim();
  
  if (currentMode === 'COMPLIANCE') {
    if (!sourceCode || !expectedOutput) {
      Toast.show('Please fill in Source Code and Expected Output', 'warning');
      return false;
    }
  } else if (currentMode === 'CHANGE') {
    if (!oldCondition || !newCondition || !expectedOutput) {
      Toast.show('Please fill in all required fields', 'warning');
      return false;
    }
  }
  
  return true;
}

// ========================================
// Run Analysis
// ========================================
async function runAnalysis() {
  if (!currentMode) {
    Toast.show('Please select an analysis mode first', 'error');
    return;
  }
  
  if (!validateFields()) return;
  
  if (analysisInProgress) {
    Toast.show('Analysis already in progress', 'warning');
    return;
  }
  
  analysisInProgress = true;
  
  // Show loader
  Loader.show();
  
  // Update button state
  const analyzeBtn = $('analyzeBtn');
  const analyzeBtnText = $('analyzeBtnText');
  const originalText = analyzeBtnText.textContent;
  
  analyzeBtnText.textContent = 'Analyzing...';
  analyzeBtn.disabled = true;
  
  // Update progress
  ProgressTracker.update(4);
  
  // Build payload
  const payload = {
    mode: currentMode,
    source_code: $('sourceCode')?.value || '',
    expected_output: $('expectedOutput')?.value || '',
    constraints: {
      no_behavior_change: $('noBehaviorChange')?.checked || false,
      allow_boundary_change: $('allowBoundaryChange')?.checked || false
    }
  };
  
  if (currentMode === 'CHANGE') {
    payload.old_condition = $('oldCondition')?.value || '';
    payload.new_condition = $('newCondition')?.value || '';
  }
  
  try {
    console.log('→ Sending analysis request to:', `${API_BASE}/analyze`);
    console.log('  Payload:', payload);
    
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    console.log('  Response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('  Error response:', errorText);
      throw new Error(`Backend error (${response.status}): ${errorText.substring(0, 200)}`);
    }
    
    const data = await response.json();
    console.log('✓ Analysis complete:', data);
    
    lastAnalysisResult = data;
    lastReportId = data.report_id;
    
    // Hide loader before showing results
    Loader.hide();
    
    // Render results
    renderResults(data);
    
    // Show success toast
    Toast.show(`Analysis complete: ${data.status}`, data.status === 'PASS' ? 'success' : 'warning');
    
  } catch (error) {
    console.error('✕ Analysis error:', error);
    Loader.hide();
    
    // Check if it's a network error (Render sleeping)
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      Toast.show('Backend is sleeping on Render. Please wait 30 seconds and try again.', 'error');
    } else {
      Toast.show(error.message || 'Analysis failed', 'error');
    }
  } finally {
    // Reset button state
    analyzeBtnText.textContent = originalText;
    analyzeBtn.disabled = false;
    analysisInProgress = false;
  }
}

// ========================================
// Render Results
// ========================================
function renderResults(data) {
  const resultsSection = $('resultsSection');
  const resultBox = $('resultBox');
  
  if (!resultBox || !resultsSection) return;
  
  resultsSection.style.display = 'block';
  
  // Set status class
  resultBox.className = `result-container status-${data.status.toLowerCase()}`;
  
  // Build result HTML
  const html = `
    <div class="result-status-header">
      <h3 style="font-size: 1.5rem; margin-bottom: 0.5rem;">Analysis Complete</h3>
      <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 2rem; flex-wrap: wrap;">
        <span style="display: inline-block; padding: 0.5rem 1rem; background: ${data.status === 'PASS' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}; border: 1px solid ${data.status === 'PASS' ? 'var(--color-success)' : 'var(--color-error)'}; border-radius: 20px; font-weight: 700; color: ${data.status === 'PASS' ? 'var(--color-success)' : 'var(--color-error)'}; letter-spacing: 0.05em;">${data.status}</span>
        <span style="color: var(--color-text-tertiary); font-size: 0.875rem;">Risk Score: <strong style="color: var(--color-text-primary);">${data.risk_score}/100</strong></span>
        <span style="color: var(--color-text-tertiary); font-size: 0.875rem;">Provider: <strong style="color: var(--color-text-primary);">${data.ai_provider}</strong></span>
      </div>
    </div>
    
    ${data.analyzer_findings && data.analyzer_findings.length > 0 ? `
      <div style="margin-bottom: 2rem;">
        <h4 style="font-size: 1.125rem; font-weight: 600; margin-bottom: 1rem; color: var(--color-text-primary);">Analysis Findings</h4>
        ${data.analyzer_findings.map(f => `
          <div style="background: var(--color-bg-primary); border: 1px solid var(--color-border); border-radius: 10px; padding: 1rem; margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
              <strong style="color: var(--color-text-primary);">${escapeHtml(f.name)}</strong>
              <span style="padding: 0.25rem 0.75rem; background: rgba(239, 68, 68, 0.1); border: 1px solid var(--color-error); border-radius: 12px; font-size: 0.75rem; color: var(--color-error); font-weight: 600;">Risk: ${f.risk}</span>
            </div>
            <ul style="margin: 0; padding-left: 1.5rem; color: var(--color-text-secondary);">
              ${f.findings.map(finding => `<li style="margin: 0.5rem 0;">${escapeHtml(finding)}</li>`).join('')}
            </ul>
          </div>
        `).join('')}
      </div>
    ` : `
      <div style="margin-bottom: 2rem; padding: 1.5rem; background: rgba(16, 185, 129, 0.1); border: 1px solid var(--color-success); border-radius: 10px; text-align: center;">
        <p style="color: var(--color-success); font-weight: 600;">✓ No issues detected</p>
      </div>
    `}
    
    ${data.technical_explanation ? `
      <div style="margin-bottom: 2rem;">
        <h4 style="font-size: 1.125rem; font-weight: 600; margin-bottom: 1rem; color: var(--color-text-primary);">Technical Explanation</h4>
        <div style="background: var(--color-bg-primary); border: 1px solid var(--color-border); border-radius: 10px; padding: 1.5rem;">
          <p style="color: var(--color-text-secondary); line-height: 1.8; white-space: pre-wrap;">${escapeHtml(data.technical_explanation)}</p>
        </div>
      </div>
    ` : ''}
    
    ${data.human_explanation ? `
      <div style="margin-bottom: 2rem;">
        <h4 style="font-size: 1.125rem; font-weight: 600; margin-bottom: 1rem; color: var(--color-text-primary);">Human-Readable Explanation</h4>
        <div style="background: var(--color-bg-primary); border: 1px solid var(--color-border); border-radius: 10px; padding: 1.5rem;">
          <p style="color: var(--color-text-secondary); line-height: 1.8; white-space: pre-wrap;">${escapeHtml(data.human_explanation)}</p>
        </div>
      </div>
    ` : ''}
    
    ${data.ai_solution ? `
      <div style="margin-bottom: 2rem;">
        <h4 style="font-size: 1.125rem; font-weight: 600; margin-bottom: 1rem; color: var(--color-text-primary);">AI Recommendations</h4>
        <div style="background: var(--color-bg-primary); border: 1px solid var(--color-border); border-radius: 10px; padding: 1.5rem;">
          <p style="color: var(--color-text-secondary); line-height: 1.8; white-space: pre-wrap;">${escapeHtml(data.ai_solution)}</p>
        </div>
      </div>
    ` : ''}
    
    <details style="margin-top: 2rem;">
      <summary style="cursor: pointer; font-weight: 600; padding: 1rem; background: var(--color-bg-primary); border: 1px solid var(--color-border); border-radius: 10px; color: var(--color-text-primary);">
        View Technical Details
      </summary>
      <pre style="margin-top: 1rem; padding: 1.5rem; background: var(--color-bg-primary); border: 1px solid var(--color-border); border-radius: 10px; overflow-x: auto; font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-tertiary); white-space: pre-wrap; word-wrap: break-word;">${JSON.stringify(data.semantic_signals || {}, null, 2)}</pre>
    </details>
  `;
  
  resultBox.innerHTML = html;
  
  // Show download buttons
  $('downloadJsonBtn').style.display = 'flex';
  $('downloadPdfBtn').style.display = 'flex';
  
  // Scroll to results
  setTimeout(() => {
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 100);
}

// ========================================
// Download Reports
// ========================================
function downloadJSON() {
  if (!lastReportId) {
    Toast.show('No analysis report available', 'warning');
    return;
  }
  Toast.show('Downloading JSON report...', 'info');
  window.open(`${API_BASE}/report/json/${lastReportId}`, '_blank');
}

function downloadPDF() {
  if (!lastReportId) {
    Toast.show('No analysis report available', 'warning');
    return;
  }
  Toast.show('Downloading PDF report...', 'info');
  window.open(`${API_BASE}/report/pdf/${lastReportId}`, '_blank');
}

// ========================================
// Utility Functions
// ========================================
function escapeHtml(text) {
  if (typeof text !== 'string') return text;
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ========================================
// Initialize Application
// ========================================
document.addEventListener('DOMContentLoaded', () => {
  console.log('═'.repeat(60));
  console.log('CRONOS Professional v3.2 - Initializing');
  console.log('Environment: PRODUCTION (Vercel + Render)');
  console.log('API Base:', API_BASE);
  console.log('═'.repeat(60));
  
  // Initialize components
  Toast.init();
  Loader.init();
  CharCounter.initAll();
  
  // Test backend connection
  setTimeout(() => {
    testBackendConnection();
  }, 1500);
  
  // Mode selection buttons
  $$('.mode-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      const mode = this.getAttribute('data-mode');
      selectMode(mode);
    });
  });
  
  // Navigation buttons
  $('backToModeBtn')?.addEventListener('click', goBackToModeSelection);
  $('clearAllBtn')?.addEventListener('click', () => {
    if (confirm('Clear all fields?')) {
      clearAllFields();
      Toast.show('All fields cleared', 'success');
    }
  });
  
  // Analysis button
  $('analyzeBtn')?.addEventListener('click', (e) => {
    e.preventDefault();
    runAnalysis();
  });
  
  // Download buttons
  $('downloadJsonBtn')?.addEventListener('click', downloadJSON);
  $('downloadPdfBtn')?.addEventListener('click', downloadPDF);
  
  // Textarea auto-resize and character counting
  $$('textarea.code-input').forEach(textarea => {
    autoResize(textarea);
    
    textarea.addEventListener('input', () => {
      autoResize(textarea);
      CharCounter.update(textarea.id);
      
      // Update progress based on filled fields
      const sourceCode = $('sourceCode')?.value.trim();
      const expectedOutput = $('expectedOutput')?.value.trim();
      
      if (sourceCode && expectedOutput) {
        ProgressTracker.update(3);
      } else if (sourceCode) {
        ProgressTracker.update(2);
      } else {
        ProgressTracker.update(1);
      }
    });
  });
  
  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Enter to analyze
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      if (currentMode && $('analyzeBtn')) {
        e.preventDefault();
        runAnalysis();
      }
    }
    
    // Escape to go back
    if (e.key === 'Escape' && currentMode) {
      goBackToModeSelection();
    }
  });
  
  console.log('✓ CRONOS initialized successfully');
  console.log('  Keyboard shortcuts:');
  console.log('  • Ctrl+Enter - Run analysis');
  console.log('  • Escape - Return to mode selection');
  console.log('═'.repeat(60));
});
