# ===============================
# CRONOS v3.3 – CORRECTED LOGIC
# Dual Mode Engine with Proper Separation
# ===============================
from dotenv import load_dotenv
load_dotenv()

import os, json, ast, hashlib, uuid, requests
from datetime import datetime
from typing import List, Dict, Any, Set
from io import BytesIO

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from google import genai

# ===============================
# API KEYS
# ===============================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
OPENROUTER_ENABLED = bool(OPENROUTER_API_KEY)

# ===============================
# APP SETUP
# ===============================
app = FastAPI(
    title="CRONOS – Dual Mode Code Analyzer",
    version="3.3.1"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# ===============================
# STORAGE
# ===============================
REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# ===============================
# MODELS
# ===============================
class Constraint(BaseModel):
    no_behavior_change: bool = False
    allow_boundary_change: bool = False

class AnalyzerResult(BaseModel):
    name: str
    findings: List[str]
    risk: int
    details: Dict[str, Any] = {}

class AnalyzeRequest(BaseModel):
    mode: str
    source_code: str = ""
    expected_output: str = ""
    old_condition: str = ""
    new_condition: str = ""
    constraints: Constraint = Constraint()

# ===============================
# AST HELPERS
# ===============================
def safe_ast(code: str):
    """Parse code into AST with error handling"""
    try:
        return ast.parse(code)
    except Exception as e:
        raise ValueError(f"AST Parse Error: {str(e)}")

def hash_source(code: str) -> str:
    """Generate SHA256 hash of source code"""
    return hashlib.sha256(code.encode()).hexdigest()

def extract_identifiers(tree) -> Set[str]:
    """Extract all identifier names from AST"""
    identifiers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
    return identifiers

# ===============================
# RISK NORMALIZATION
# ===============================
def normalize_risk(raw_risk: int) -> int:
    """Normalize risk to standard buckets: 0, 20, 40, 60, 80, 100"""
    if raw_risk <= 0:
        return 0
    if raw_risk <= 20:
        return 20
    if raw_risk <= 40:
        return 40
    if raw_risk <= 60:
        return 60
    if raw_risk <= 80:
        return 80
    return 100

def pass_fail_from_risk(risk: int) -> str:
    """Determine PASS/WARN/FAIL based on risk threshold"""
    if risk < 30:
        return "PASS"
    elif risk < 60:
        return "WARN"
    else:
        return "FAIL"

# ===============================
# CHANGE MODE ANALYZER (CORRECTED)
# ===============================
class ChangeAnalyzer:
    """
    Analyzes behavioral changes between old and new conditions.
    Uses AST structural comparison, not just text diff.
    Distinguishes between boundary changes (low risk) and logical changes (high risk).
    """
    
    def analyze(self, old: str, new: str):
        # Validate inputs
        if not old.strip() or not new.strip():
            return [], 0, {"error": "Empty conditions provided"}

        # Parse both conditions
        try:
            old_ast = safe_ast(old)
            new_ast = safe_ast(new)
        except ValueError as e:
            return [
                AnalyzerResult(
                    name="ParseError",
                    findings=[str(e)],
                    risk=20,
                    details={"error": str(e)}
                )
            ], 20, {"parse_error": True}

        # Hash comparison - if identical, no change
        old_hash = hash_source(old)
        new_hash = hash_source(new)
        
        if old_hash == new_hash:
            return [], 0, {
                "semantic_diff": False,
                "old_hash": old_hash,
                "new_hash": new_hash,
                "ast_changed": False
            }

        # AST structural comparison (REAL ANALYSIS)
        old_ast_dump = ast.dump(old_ast)
        new_ast_dump = ast.dump(new_ast)
        ast_changed = old_ast_dump != new_ast_dump

        # Clean versions for comparison
        old_clean = old.replace(" ", "").lower()
        new_clean = new.replace(" ", "").lower()

        # SMART RISK SCORING (distinguishes types of changes)
        change_type = "unknown"
        
        # Check for boundary changes (LOW RISK)
        if (">" in old_clean and ">=" in new_clean) or (">=" in old_clean and ">" in new_clean):
            risk = 20
            change_type = "boundary_adjustment"
        elif ("<" in old_clean and "<=" in new_clean) or ("<=" in old_clean and "<" in new_clean):
            risk = 20
            change_type = "boundary_adjustment"
        
        # Check for logical inversions (HIGH RISK)
        elif ("and" in old_clean and "or" in new_clean) or ("or" in old_clean and "and" in new_clean):
            risk = 80
            change_type = "logical_inversion"
        
        # Check for operator changes (MEDIUM-HIGH RISK)
        elif ("==" in old_clean and "!=" in new_clean) or ("!=" in old_clean and "==" in new_clean):
            risk = 70
            change_type = "equality_inversion"
        
        # Completely different logic (HIGH RISK)
        elif ast_changed:
            risk = 60
            change_type = "structural_change"
        
        # Text-only change (LOW RISK)
        else:
            risk = 30
            change_type = "minor_change"

        # Dynamic finding text based on change type
        if change_type == "boundary_adjustment":
            finding_text = "Minor boundary adjustment — behavior mostly preserved"
        elif change_type == "logical_inversion":
            finding_text = "High-risk logical operator change detected (AND/OR)"
        elif change_type == "equality_inversion":
            finding_text = "High-risk equality operator change detected (==/!=)"
        elif change_type == "structural_change":
            finding_text = "Potential behavioral shift detected — structural AST change"
        else:
            finding_text = "Minor modification detected"

        signals = {
            "semantic_diff": True,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "ast_changed": ast_changed,
            "change_type": change_type,
            "old_condition": old,
            "new_condition": new
        }

        findings = [
            AnalyzerResult(
                name="ConditionShift",
                findings=[finding_text],
                risk=risk,
                details=signals
            )
        ]

        return findings, risk, signals

# ===============================
# COMPLIANCE ANALYZER (CORRECTED)
# ===============================
class ComplianceAnalyzer:
    """
    Validates code against expected behavior contract.
    Uses AST identifier extraction, not AI guessing.
    AI is used only for explanation, not decision.
    """
    
    def analyze(self, code: str, expected: str):
        # Parse code
        try:
            tree = safe_ast(code)
        except ValueError as e:
            return [
                AnalyzerResult(
                    name="ParseError",
                    findings=[str(e)],
                    risk=20,
                    details={"error": str(e)}
                )
            ], 20, {"parse_error": True}
        
        src_hash = hash_source(code)

        # If no contract specified, pass with risk 0
        if not expected.strip():
            return [], 0, {
                "semantic_similarity": 1.0,
                "invariant_broken": False,
                "source_hash": src_hash,
                "comparison_method": "no_contract_specified"
            }

        # Extract identifiers from code (REAL ANALYSIS)
        identifiers = extract_identifiers(tree)
        
        # Tokenize expected behavior
        expected_words = set(expected.lower().split())
        
        # Check if expected tokens appear in code identifiers
        # This is a structural match, not text comparison
        matches = bool(identifiers.intersection(expected_words))

        # Determine risk
        risk = 60 if not matches else 0

        findings = []
        if not matches:
            findings.append(
                AnalyzerResult(
                    name="ContractViolation",
                    findings=["Expected behavior not aligned with code semantics"],
                    risk=60,
                    details={
                        "identifiers_found": sorted(list(identifiers)),
                        "expected_tokens": sorted(list(expected_words)),
                        "intersection": sorted(list(identifiers.intersection(expected_words)))
                    }
                )
            )

        return findings, risk, {
            "semantic_similarity": 1.0 if matches else 0.2,
            "invariant_broken": not matches,
            "source_hash": src_hash,
            "comparison_method": "ast_identifier_match",
            "identifiers_in_code": sorted(list(identifiers)),
            "expected_tokens": sorted(list(expected_words))
        }

# ===============================
# AI CALLS
# ===============================
def call_gemini(prompt: str):
    """Call Gemini API"""
    if not gemini_client:
        raise Exception("Gemini not configured")

    try:
        r = gemini_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return r.text.strip(), "Gemini"
    except Exception as e:
        raise Exception(f"Gemini API Error: {str(e)}")

def call_openrouter(prompt: str):
    """Call OpenRouter API"""
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 700
            },
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"], "OpenRouter"
    except Exception as e:
        raise Exception(f"OpenRouter API Error: {str(e)}")

def ai(prompt: str):
    """Smart AI fallback handler"""
    if gemini_client:
        try:
            return call_gemini(prompt)
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}")
    
    if OPENROUTER_ENABLED:
        try:
            return call_openrouter(prompt)
        except Exception as e:
            print(f"⚠️ OpenRouter failed: {e}")
    
    return ("AI analysis unavailable. Please check API keys.", "None")

# ===============================
# ROLE-LOCKED PROMPTS (CORRECTED)
# ===============================
def technical_prompt(mode: str, signals: dict, findings: list, risk: int) -> str:
    """
    Role: Senior Static Analysis Engineer
    Purpose: Explain WHY the issue exists technically
    """
    return f"""You are a senior static analysis engineer.

Your task:
- Explain the issue ONLY in technical terms
- Refer to code behavior, AST parsing, semantic analysis, and contracts
- DO NOT simplify language
- DO NOT give user-friendly explanations
- DO NOT suggest fixes

Context:
Mode: {mode}
Signals: {json.dumps(signals, indent=2)}
Findings: {json.dumps([f.dict() if hasattr(f, 'dict') else f for f in findings], indent=2)}
Risk Score: {risk}

Explain:
- What technically caused the issue
- Which invariant or assumption was violated
- Why the risk score is justified

Keep response under 150 words."""

def human_prompt(findings: list, risk: int) -> str:
    """
    Role: Product/QA Stakeholder
    Purpose: Explain impact to user/business
    """
    return f"""You are explaining this to a non-technical stakeholder.

Rules:
- NO programming terms
- NO AST, NO variables, NO functions
- Use simple language
- Explain consequences, not causes

Findings: {json.dumps([f.dict() if hasattr(f, 'dict') else f for f in findings], indent=2)}
Risk Score: {risk}

Explain:
- What can go wrong
- Why this matters
- What level of attention this needs

Keep response under 100 words."""

def compliance_solution_prompt(hash_code: str, expected: str, risk: int) -> str:
    """
    Role: Senior Software Architect
    Purpose: Strategic guidance, not code
    """
    return f"""You are a senior software architect.

Context:
- Code Hash: {hash_code}
- Expected Behavior: {expected}
- Risk Score: {risk}

Rules:
- Do NOT write code
- Do NOT repeat the problem
- Focus on strategy

Provide:
- What should be verified
- What should be tested
- What kind of change is required (logic, validation, contract)

Keep it high-level and actionable. Under 120 words."""

# ===============================
# ANALYZE ENDPOINT
# ===============================
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Main analysis endpoint with corrected logic.
    AI is used for EXPLANATION only, not DECISION.
    """
    mode = req.mode.upper()
    report_id = str(uuid.uuid4())

    try:
        if mode == "CHANGE":
            # CHANGE MODE: Analyze condition changes
            analyzer = ChangeAnalyzer()
            findings, raw_risk, signals = analyzer.analyze(
                req.old_condition,
                req.new_condition
            )

            risk = normalize_risk(raw_risk)

            # AI explains (does not decide)
            tech, provider = ai(technical_prompt(mode, signals, findings, risk))
            human, _ = ai(human_prompt(findings, risk))

            result = {
                "mode": "CHANGE",
                "status": pass_fail_from_risk(risk),
                "risk_score": risk,
                "analyzer_findings": [f.dict() for f in findings],
                "semantic_signals": signals,
                "technical_explanation": tech,
                "human_explanation": human,
                "ai_provider": provider,
                "report_id": report_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        elif mode == "COMPLIANCE":
            # COMPLIANCE MODE: Validate against contract
            analyzer = ComplianceAnalyzer()
            findings, raw_risk, signals = analyzer.analyze(
                req.source_code,
                req.expected_output
            )

            risk = normalize_risk(raw_risk)

            # AI explains (does not decide)
            tech, provider = ai(technical_prompt(mode, signals, findings, risk))
            solution, _ = ai(
                compliance_solution_prompt(
                    signals["source_hash"],
                    req.expected_output,
                    risk
                )
            )

            result = {
                "mode": "COMPLIANCE",
                "status": pass_fail_from_risk(risk),
                "risk_score": risk,
                "analyzer_findings": [f.dict() for f in findings],
                "semantic_signals": signals,
                "technical_explanation": tech,
                "ai_solution": solution,
                "ai_provider": provider,
                "report_id": report_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        else:
            raise HTTPException(400, "Invalid mode. Use CHANGE or COMPLIANCE")

        # Save report
        with open(f"{REPORT_DIR}/{report_id}.json", "w") as f:
            json.dump(result, f, indent=2)

        return result

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")

# ===============================
# DOWNLOAD JSON
# ===============================
@app.get("/report/json/{report_id}")
async def download_json(report_id: str):
    """Download analysis report as JSON"""
    path = f"{REPORT_DIR}/{report_id}.json"
    if not os.path.exists(path):
        raise HTTPException(404, "Report not found")

    with open(path) as f:
        return JSONResponse(
            content=json.load(f),
            headers={
                "Content-Disposition": f'attachment; filename="{report_id}.json"'
            }
        )

# ===============================
# DOWNLOAD PDF
# ===============================
@app.get("/report/pdf/{report_id}")
async def download_pdf(report_id: str):
    """Generate and download analysis report as PDF"""
    json_path = f"{REPORT_DIR}/{report_id}.json"
    if not os.path.exists(json_path):
        raise HTTPException(404, "Report not found")

    with open(json_path) as f:
        data = json.load(f)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 800, "CRONOS Analysis Report")
    
    # Metadata
    c.setFont("Helvetica", 10)
    y = 770
    
    for k, v in data.items():
        text = f"{k}: {str(v)[:80]}"
        c.drawString(40, y, text)
        y -= 14
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = 800

    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}.pdf"'
        }
    )

# ===============================
# HEALTH CHECK
# ===============================
@app.get("/")
async def health():
    """API health check and information"""
    return {
        "status": "ok",
        "service": "CRONOS API v3.3.1 - SMART RISK SCORING",
        "cors": "ALLOW ALL (testing mode)",
        "improvements": [
            "CHANGE mode: Smart risk scoring (boundary vs logical changes)",
            "COMPLIANCE mode: Identifier extraction (not AI guessing)",
            "AI: Explanation only (not decision-making)",
            "Role-locked prompts for distinct outputs",
            "Three-level status: PASS/WARN/FAIL"
        ],
        "risk_levels": {
            "0-29": "PASS - Safe changes",
            "30-59": "WARN - Review recommended",
            "60-100": "FAIL - High risk changes"
        },
        "features": {
            "gemini": gemini_client is not None,
            "openrouter": OPENROUTER_ENABLED
        },
        "endpoints": [
            "POST /analyze",
            "GET /report/json/{id}",
            "GET /report/pdf/{id}"
        ]
    }

# ===============================
# STARTUP EVENT
# ===============================
@app.on_event("startup")
async def startup_event():
    """Print startup information"""
    print("=" * 60)
    print("✅ CRONOS v3.3.1 - SMART RISK SCORING EDITION")
    print("=" * 60)
    print(f"📁 Report directory: {REPORT_DIR}")
    print(f"🤖 Gemini: {'✅ Enabled' if gemini_client else '❌ Disabled'}")
    print(f"🤖 OpenRouter: {'✅ Enabled' if OPENROUTER_ENABLED else '❌ Disabled'}")
    print("🌐 CORS: ALLOW ALL (*) - TESTING MODE")
    print()
    print("🔧 CORRECTIONS APPLIED:")
    print("  ✓ CHANGE mode: Smart risk scoring (boundary vs logical)")
    print("  ✓ COMPLIANCE mode: Identifier-based validation")
    print("  ✓ AI role separation: Explainer, not judge")
    print("  ✓ Role-locked prompts for distinct outputs")
    print("  ✓ Three-level status: PASS/WARN/FAIL")
    print()
    print("📊 RISK LEVELS:")
    print("  • 0-29:   PASS (Safe changes)")
    print("  • 30-59:  WARN (Review recommended)")
    print("  • 60-100: FAIL (High risk changes)")
    print("=" * 60)
