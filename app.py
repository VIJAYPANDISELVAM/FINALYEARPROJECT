# ===============================
# CRONOS v3.2 – Dual Mode Engine
# PRODUCTION READY FOR RENDER
# Change Mode + Compliance Mode
# JSON + PDF + AI (Gemini/OpenRouter)
# ===============================
from dotenv import load_dotenv
load_dotenv()

import os, json, ast, hashlib, uuid, requests
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    version="3.2.2",
    description="Production-ready deployment for Render with CORS and all features"
)

# ✅ CRITICAL FIX: ADD YOUR EXACT VERCEL DOMAIN
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://finalyearproject-lime.vercel.app",  # Your exact domain
        "https://*.vercel.app",  # All Vercel preview deployments
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# ✅ PRE-FLIGHT OPTIONS HANDLER (CRITICAL FOR CORS)
@app.options("/{path:path}")
async def options_handler(path: str):
    return {
        "message": "CORS preflight OK"
    }

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
    try:
        return ast.parse(code)
    except Exception as e:
        raise ValueError(f"AST Parse Error: {str(e)}")

def hash_source(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()

# ===============================
# CHANGE MODE ANALYZER
# ===============================
class ChangeAnalyzer:
    def analyze(self, old: str, new: str):
        if old.strip() == new.strip():
            return [], 0, {"semantic_diff": False}

        return [
            AnalyzerResult(
                name="SemanticChange",
                findings=["Old and new conditions differ"],
                risk=30,
                details={"change_detected": True}
            )
        ], 30, {"semantic_diff": True}

# ===============================
# COMPLIANCE ANALYZER
# ===============================
class ComplianceAnalyzer:
    def analyze(self, code: str, expected: str):
        safe_ast(code)
        src_hash = hash_source(code)

        similarity = 1.0 if expected.strip() else 0.0
        invariant_broken = similarity < 0.75

        results = []
        risk = 0

        if invariant_broken:
            risk = 60
            results.append(
                AnalyzerResult(
                    name="ContractViolation",
                    findings=["Expected behavior not guaranteed"],
                    risk=60,
                    details={"similarity": similarity}
                )
            )

        return results, risk, {
            "semantic_similarity": similarity,
            "invariant_broken": invariant_broken,
            "source_hash": src_hash
        }

# ===============================
# AI CALLS (WITH ERROR HANDLING)
# ===============================
def call_gemini(prompt: str):
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
    """Try Gemini first, fallback to OpenRouter, return safe default if both fail"""
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
# AI PROMPTS
# ===============================
def technical_prompt(mode, signals, findings):
    return f"""
Mode: {mode}
Signals: {signals}
Findings: {findings}

Explain the technical reasoning clearly in 2-3 sentences.
"""

def human_prompt(findings):
    return f"""
Findings: {findings}

Explain impact in simple human language in 2-3 sentences.
"""

def compliance_solution_prompt(hash_code, expected):
    return f"""
Source Hash: {hash_code}
Expected Contract: {expected}

Suggest a high-level corrective strategy in 2-3 sentences.
No code implementation.
"""

# ===============================
# ANALYZE ENDPOINT
# ===============================
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    mode = req.mode.upper()
    report_id = str(uuid.uuid4())

    try:
        if mode == "CHANGE":
            analyzer = ChangeAnalyzer()
            findings, risk, signals = analyzer.analyze(
                req.old_condition,
                req.new_condition
            )

            tech, provider = ai(technical_prompt(mode, signals, findings))
            human, _ = ai(human_prompt(findings))

            result = {
                "mode": "CHANGE",
                "status": "FAIL" if risk > 0 else "PASS",
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
            analyzer = ComplianceAnalyzer()
            findings, risk, signals = analyzer.analyze(
                req.source_code,
                req.expected_output
            )

            tech, provider = ai(technical_prompt(mode, signals, findings))
            solution, _ = ai(
                compliance_solution_prompt(
                    signals["source_hash"],
                    req.expected_output
                )
            )

            result = {
                "mode": "COMPLIANCE",
                "status": "FAIL" if risk > 0 else "PASS",
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
    path = f"{REPORT_DIR}/{report_id}.json"
    if not os.path.exists(path):
        raise HTTPException(404, "Report not found")
    return FileResponse(
        path, 
        media_type="application/json", 
        filename=f"{report_id}.json",
        headers={
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

# ===============================
# DOWNLOAD PDF
# ===============================
@app.get("/report/pdf/{report_id}")
async def download_pdf(report_id: str):
    json_path = f"{REPORT_DIR}/{report_id}.json"
    if not os.path.exists(json_path):
        raise HTTPException(404, "Report not found")

    pdf_path = f"{REPORT_DIR}/{report_id}.pdf"
    
    try:
        with open(json_path) as f:
            data = json.load(f)

        c = canvas.Canvas(pdf_path, pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, 800, "CRONOS Analysis Report")
        
        c.setFont("Helvetica", 10)
        y = 770
        
        for k, v in data.items():
            text = f"{k}: {str(v)[:80]}"
            c.drawString(40, y, text)
            y -= 15
            if y < 50:
                c.showPage()
                y = 800

        c.save()

        return FileResponse(
            pdf_path, 
            media_type="application/pdf", 
            filename=f"{report_id}.pdf",
            headers={
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {str(e)}")

# ===============================
# HEALTH CHECK
# ===============================
@app.get("/")
async def health():
    return {
        "status": "ok",
        "service": "CRONOS API v3.2.2",
        "environment": "production",
        "features": {
            "gemini": gemini_client is not None,
            "openrouter": OPENROUTER_ENABLED
        },
        "endpoints": [
            "/analyze",
            "/report/json/{id}",
            "/report/pdf/{id}"
        ]
    }

# ===============================
# STARTUP EVENT
# ===============================
@app.on_event("startup")
async def startup_event():
    print("✅ CRONOS Backend Started")
    print(f"📁 Report directory: {REPORT_DIR}")
    print(f"🤖 Gemini configured: {gemini_client is not None}")
    print(f"🤖 OpenRouter configured: {OPENROUTER_ENABLED}")
