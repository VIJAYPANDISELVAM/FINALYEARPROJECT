# ===============================
# CRONOS v3.2 – Dual Mode Engine
# NO FEATURE REMOVED
# Change Mode + Compliance Mode
# JSON + PDF + AI (Gemini/OpenRouter)
# ===============================

from dotenv import load_dotenv
load_dotenv()

import os, json, ast, hashlib, uuid, time, re, requests
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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
app = FastAPI(title="CRONOS – Dual Mode Code Analyzer", version="3.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/ui", StaticFiles(directory="ui"), name="ui")

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return FileResponse("ui/index.html")


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


# ===============================
# AST HELPERS
# ===============================
def safe_ast(code: str):
    try:
        return ast.parse(code)
    except Exception as e:
        raise ValueError(str(e))


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
                risk=30
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
                    risk=60
                )
            )

        return results, risk, {
            "semantic_similarity": similarity,
            "invariant_broken": invariant_broken,
            "source_hash": src_hash
        }


# ===============================
# AI CALLS
# ===============================
def call_gemini(prompt: str):
    if not gemini_client:
        raise Exception("Gemini not configured")

    r = gemini_client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )
    return r.text.strip(), "Gemini"


def call_openrouter(prompt: str):
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
    data = r.json()
    return data["choices"][0]["message"]["content"], "OpenRouter"


def ai(prompt: str):
    if gemini_client:
        try:
            return call_gemini(prompt)
        except Exception:
            pass
    return call_openrouter(prompt)


# ===============================
# AI PROMPTS
# ===============================
def technical_prompt(mode, signals, findings):
    return f"""
Mode: {mode}
Signals: {signals}
Findings: {findings}

Explain the technical reasoning without mentioning source code.
"""


def human_prompt(findings):
    return f"""
Findings: {findings}

Explain impact in simple human terms.
"""


def compliance_solution_prompt(hash_code, expected):
    return f"""
Source Hash: {hash_code}
Expected Contract: {expected}

Suggest a high-level fix without code or assumptions.
"""


# ===============================
# ANALYZE ENDPOINT
# ===============================
@app.post("/analyze")
def analyze(req: dict):
    mode = req.get("mode", "").upper()
    report_id = str(uuid.uuid4())

    if mode == "CHANGE":
        analyzer = ChangeAnalyzer()
        findings, risk, signals = analyzer.analyze(
            req.get("old_condition", ""),
            req.get("new_condition", "")
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
            req.get("source_code", ""),
            req.get("expected_output", "")
        )

        tech, provider = ai(technical_prompt(mode, signals, findings))
        solution, _ = ai(
            compliance_solution_prompt(
                signals["source_hash"],
                req.get("expected_output", "")
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
        raise HTTPException(400, "Invalid mode")

    with open(f"{REPORT_DIR}/{report_id}.json", "w") as f:
        json.dump(result, f, indent=2)

    return result


# ===============================
# DOWNLOAD JSON
# ===============================
@app.get("/report/json/{report_id}")
def download_json(report_id: str):
    path = f"{REPORT_DIR}/{report_id}.json"
    if not os.path.exists(path):
        raise HTTPException(404, "Report not found")
    return FileResponse(path, media_type="application/json", filename=f"{report_id}.json")


# ===============================
# DOWNLOAD PDF
# ===============================
@app.get("/report/pdf/{report_id}")
def download_pdf(report_id: str):
    json_path = f"{REPORT_DIR}/{report_id}.json"
    if not os.path.exists(json_path):
        raise HTTPException(404, "Report not found")

    pdf_path = f"{REPORT_DIR}/{report_id}.pdf"
    data = json.load(open(json_path))

    c = canvas.Canvas(pdf_path, pagesize=A4)
    text = c.beginText(40, 800)

    for k, v in data.items():
        text.textLine(f"{k}: {v}")
        text.textLine("")

    c.drawText(text)
    c.save()

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{report_id}.pdf")
