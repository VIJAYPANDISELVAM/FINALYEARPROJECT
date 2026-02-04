Cronos – Static Code Analysis Platform

Cronos is an intelligent static code analysis platform built to help developers validate code logic, check compliance, and assess risk using AST parsing and AI-powered semantic validation.

At its core, Cronos combines traditional static analysis with modern intelligence so you can catch issues early, understand behavioral changes during refactoring, and validate expected behaviors across different code paths.

Features

Static Code Analysis – Analyze source code for structure, semantics, and contract integrity.

AI-Powered Validation – Leverage AI (e.g., Gemini models) to validate logic modifications and expected behaviors.

Differential Analysis – Assess how code changes impact contract compliance and behavior.

Compliance Checks – Analyze control flow, contract conformity, and specification matching.

Exportable Results – Output results in JSON or PDF for reporting and audits.

Multi-Mode Analysis – Switch between change analysis and compliance verification.

Flexible Constraints – Optional strict behavior enforcement or relaxed edge-case flexibility.

 Live Demo

Check Cronos in action:
 https://cronoscodeanalyzer.vercel.app/

 How It Works:

Cronos processes your code through several analysis stages:

AST Parsing – Build an abstract syntax tree from the source.

Semantic Analysis – Understand deeper code structure beyond syntax.

Risk & Compliance Assessment – Validate contract behavior with baseline expectations.

AI Validation Layer – Use AI to reason about code changes and expected outcomes.

Tech Stack:

Frontend: Next.js (React + TypeScript)

API: FastAPI (Python)

AI Backend: Gemini / AI models for semantic analysis

Deployment: Vercel

Runs as a serverless web app with intuitive UI for submitting source code and reviewing results.

Quick Start (Local Development):

Note: Ensure Python, Node.js & npm/yarn are installed.

# 1. Clone the repo
git clone https://github.com/<your-org>/cronos-analyzer.git
cd cronos-analyzer

# 2. Install front-end deps
cd frontend
npm install

# 3. Install API deps
cd ../api
pip install -r requirements.txt

# 4. Run locally
# Frontend
npm run dev

# Backend
uvicorn main:app --reload


Your UI should now be available at http://localhost:3000 and API at http://localhost:8000.

 Usage:

Navigate to the app UI.

Select an analysis mode.

Paste your source code into the editor.

Set expected behavior or contract rules if needed.

Run analysis and review results (JSON, PDF).

Example Input / Output:

Input:

def add(a, b):
    return a + b


Expected Behavior:

No side effects

Always returns sum

Output:

{
  "analysis": "pass",
  "warnings": [],
  "contractViolations": []
}

Contributing:

If you’d like to contribute:

Fork the repository

Create a feature branch

Add tests for new features

Submit a pull request

Please follow the code style and maintain test coverage.

License:

This project is licensed under the MIT License — see LICENSE for details.
