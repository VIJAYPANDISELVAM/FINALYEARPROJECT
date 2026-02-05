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

# API KEYS

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
OPENROUTER_ENABLED = bool(OPENROUTER_API_KEY)


# APP SETUP

app = FastAPI(
    title="CRONOS – Dual Mode Code Analyzer",
    version="4.0.0"
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


# STORAGE

REPORT_DIR = "reports"
os.makedirs(REPORT_DIR, exist_ok=True)


# MODELS

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
    technical_depth: str = "balanced"
    enable_deep_analysis: bool = False

# AST HELPERS

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


# RISK NORMALIZATION

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
    """Determine PASS/WARN/FAIL based on fair risk thresholds"""
    if risk <= 20:
        return "PASS"
    elif risk <= 50:
        return "WARN"
    else:
        return "FAIL"


# CHANGE MODE ANALYZER (COMPREHENSIVE & FAIR)

class ChangeAnalyzer:
    """
    Analyzes behavioral changes between old and new conditions.
    Uses comprehensive AST analysis with FAIR risk scoring.
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

        # AST structural comparison
        old_ast_dump = ast.dump(old_ast)
        new_ast_dump = ast.dump(new_ast)
        ast_changed = old_ast_dump != new_ast_dump

        # Extract AST nodes for detailed analysis
        old_nodes = self._extract_node_types(old_ast)
        new_nodes = self._extract_node_types(new_ast)

        # Initialize analysis results
        findings = []
        risk_scores = []
        change_details = {}

        # 1. OPERATOR CHANGES (Priority: High-impact first)
        operator_risk, operator_findings, operator_details = self._analyze_operators(
            old, new, old_nodes, new_nodes
        )
        if operator_risk > 0:
            findings.extend(operator_findings)
            risk_scores.append(operator_risk)
            change_details.update(operator_details)

        # 2. FUNCTION CHANGES
        function_risk, function_findings, function_details = self._analyze_functions(
            old_nodes, new_nodes
        )
        if function_risk > 0:
            findings.extend(function_findings)
            risk_scores.append(function_risk)
            change_details.update(function_details)

        # 3. LOOP CHANGES
        loop_risk, loop_findings, loop_details = self._analyze_loops(
            old_nodes, new_nodes
        )
        if loop_risk > 0:
            findings.extend(loop_findings)
            risk_scores.append(loop_risk)
            change_details.update(loop_details)

        # 4. LIBRARY/IMPORT CHANGES
        library_risk, library_findings, library_details = self._analyze_imports(
            old_nodes, new_nodes
        )
        if library_risk > 0:
            findings.extend(library_findings)
            risk_scores.append(library_risk)
            change_details.update(library_details)

        # 5. DATA TYPE CHANGES
        datatype_risk, datatype_findings, datatype_details = self._analyze_datatypes(
            old_nodes, new_nodes
        )
        if datatype_risk > 0:
            findings.extend(datatype_findings)
            risk_scores.append(datatype_risk)
            change_details.update(datatype_details)

        # 6. CONTROL FLOW CHANGES
        control_risk, control_findings, control_details = self._analyze_control_flow(
            old_nodes, new_nodes
        )
        if control_risk > 0:
            findings.extend(control_findings)
            risk_scores.append(control_risk)
            change_details.update(control_details)

        # 7. STRUCTURAL AST CHANGES (only if nothing else detected)
        if ast_changed and not risk_scores:
            structural_risk, structural_findings, structural_details = self._analyze_structural(
                old_ast, new_ast, old_nodes, new_nodes
            )
            if structural_risk > 0:
                findings.extend(structural_findings)
                risk_scores.append(structural_risk)
                change_details.update(structural_details)

        # Calculate final risk (use maximum risk from all categories)
        final_risk = max(risk_scores) if risk_scores else 0

        # Build comprehensive signals
        signals = {
            "semantic_diff": ast_changed,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "ast_changed": ast_changed,
            "old_condition": old,
            "new_condition": new,
            "categories_analyzed": len([r for r in risk_scores if r > 0]),
            "total_findings": len(findings),
            **change_details
        }

        return findings, final_risk, signals

    def _extract_node_types(self, tree):
        """Extract all AST node types and their details"""
        nodes = {
            'compare_ops': [],
            'bool_ops': [],
            'functions': [],
            'calls': [],
            'loops': [],
            'returns': [],
            'constants': [],
            'names': [],
            'imports': [],
            'attributes': [],
            'assignments': [],
            'if_nodes': [],
            'try_nodes': [],
            'breaks': 0,
            'continues': 0
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    nodes['compare_ops'].append(type(op).__name__)
            elif isinstance(node, ast.BoolOp):
                nodes['bool_ops'].append(type(node.op).__name__)
            elif isinstance(node, ast.FunctionDef):
                nodes['functions'].append({
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'defaults': len(node.args.defaults),
                    'returns': ast.unparse(node.returns) if node.returns else None
                })
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    nodes['calls'].append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    nodes['calls'].append(node.func.attr)
            elif isinstance(node, (ast.For, ast.While)):
                loop_info = {'type': type(node).__name__}
                if isinstance(node, ast.For):
                    loop_info['target'] = ast.unparse(node.target) if hasattr(node, 'target') else None
                    loop_info['iter'] = ast.unparse(node.iter) if hasattr(node, 'iter') else None
                elif isinstance(node, ast.While):
                    loop_info['test'] = ast.unparse(node.test) if hasattr(node, 'test') else None
                nodes['loops'].append(loop_info)
            elif isinstance(node, ast.Return):
                nodes['returns'].append(ast.unparse(node.value) if node.value else "None")
            elif isinstance(node, ast.Constant):
                nodes['constants'].append({
                    'type': type(node.value).__name__,
                    'value': str(node.value)[:50]
                })
            elif isinstance(node, ast.Name):
                nodes['names'].append(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        nodes['imports'].append(alias.name)
                else:
                    nodes['imports'].append(node.module if node.module else 'relative_import')
            elif isinstance(node, ast.Attribute):
                nodes['attributes'].append(node.attr)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        nodes['assignments'].append(target.id)
            elif isinstance(node, ast.If):
                nodes['if_nodes'].append(ast.unparse(node.test) if hasattr(node, 'test') else 'if')
            elif isinstance(node, ast.Try):
                nodes['try_nodes'].append('try_except')
            elif isinstance(node, ast.Break):
                nodes['breaks'] += 1
            elif isinstance(node, ast.Continue):
                nodes['continues'] += 1
        
        return nodes

    def _analyze_operators(self, old_code, new_code, old_nodes, new_nodes):
        """Analyze operator changes with FAIR risk scoring"""
        findings = []
        risk = 0
        details = {}
        
        old_compare = old_nodes['compare_ops']
        new_compare = new_nodes['compare_ops']
        old_bool = old_nodes['bool_ops']
        new_bool = new_nodes['bool_ops']
        
        # BOUNDARY OPERATOR CHANGES (VERY LOW RISK: 10)
        boundary_changes = []
        if ('Gt' in old_compare and 'GtE' in new_compare) or ('GtE' in old_compare and 'Gt' in new_compare):
            boundary_changes.append('> ↔ >=')
            risk = max(risk, 10)
        if ('Lt' in old_compare and 'LtE' in new_compare) or ('LtE' in old_compare and 'Lt' in new_compare):
            boundary_changes.append('< ↔ <=')
            risk = max(risk, 10)
        
        if boundary_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Boundary operator adjustment: {', '.join(boundary_changes)} — minimal behavioral impact, likely edge-case refinement"],
                risk=10,
                details={'change_type': 'boundary_adjustment', 'changes': boundary_changes}
            ))
            details['boundary_changes'] = boundary_changes
        
        # EQUALITY OPERATOR CHANGES (HIGH RISK: 80)
        equality_changes = []
        if 'Eq' in old_compare and 'NotEq' in new_compare:
            equality_changes.append('== → !=')
            risk = max(risk, 80)
        if 'NotEq' in old_compare and 'Eq' in new_compare:
            equality_changes.append('!= → ==')
            risk = max(risk, 80)
        
        if equality_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Equality operator inversion: {', '.join(equality_changes)} — completely reverses condition logic"],
                risk=80,
                details={'change_type': 'equality_inversion', 'changes': equality_changes}
            ))
            details['equality_changes'] = equality_changes
        
        # LOGICAL OPERATOR CHANGES (CRITICAL RISK: 95)
        logical_changes = []
        if 'And' in old_bool and 'Or' in new_bool:
            logical_changes.append('AND → OR')
            risk = max(risk, 95)
        if 'Or' in old_bool and 'And' in new_bool:
            logical_changes.append('OR → AND')
            risk = max(risk, 95)
        
        if logical_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Critical logical operator change: {', '.join(logical_changes)} — fundamentally alters control flow and execution paths"],
                risk=95,
                details={'change_type': 'logical_inversion', 'changes': logical_changes}
            ))
            details['logical_changes'] = logical_changes
        
        # OTHER COMPARISON OPERATORS (MEDIUM RISK: 45)
        if set(old_compare) != set(new_compare) and not boundary_changes and not equality_changes:
            old_set = set(old_compare)
            new_set = set(new_compare)
            removed = old_set - new_set
            added = new_set - old_set
            if removed or added:
                risk = max(risk, 45)
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=["Comparison operator modified — logic potentially altered"],
                    risk=45,
                    details={'change_type': 'operator_modification', 'removed': list(removed), 'added': list(added)}
                ))
                details['operator_changes'] = {'removed': list(removed), 'added': list(added)}
        
        return risk, findings, details

    def _analyze_functions(self, old_nodes, new_nodes):
        """Analyze function changes with FAIR risk scoring"""
        findings = []
        risk = 0
        details = {}
        
        old_funcs = {f['name']: f for f in old_nodes['functions']}
        new_funcs = {f['name']: f for f in new_nodes['functions']}
        
        old_calls = set(old_nodes['calls'])
        new_calls = set(new_nodes['calls'])
        
        # Function name changes (MEDIUM RISK: 35) - e.g., is_weekday → is_business_day
        old_names = set(old_funcs.keys())
        new_names = set(new_funcs.keys())
        
        # Check if it's a pure rename (same count, different names)
        if len(old_funcs) == len(new_funcs) and old_names != new_names:
            added_funcs = new_names - old_names
            removed_funcs = old_names - new_names
            
            # If same number added and removed, likely a rename
            if len(added_funcs) == len(removed_funcs) == 1:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Function renamed: {list(removed_funcs)[0]} → {list(added_funcs)[0]} — semantic refactoring, review call sites"],
                    risk=35,
                    details={
                        'change_type': 'function_rename',
                        'old_name': list(removed_funcs)[0],
                        'new_name': list(added_funcs)[0]
                    }
                ))
                details['function_rename'] = {'old': list(removed_funcs)[0], 'new': list(added_funcs)[0]}
                risk = max(risk, 35)
        else:
            # Functions added (MEDIUM RISK: 30)
            added_funcs = new_names - old_names
            if added_funcs and not (new_names - old_names == old_names - new_names):
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"New functions added: {', '.join(list(added_funcs)[:3])}{'...' if len(added_funcs) > 3 else ''} — extends functionality"],
                    risk=30,
                    details={'change_type': 'functions_added', 'functions': list(added_funcs)}
                ))
                details['functions_added'] = list(added_funcs)
                risk = max(risk, 30)
            
            # Functions removed (HIGH RISK: 70)
            removed_funcs = old_names - new_names
            if removed_funcs and not (new_names - old_names == old_names - new_names):
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Functions removed: {', '.join(list(removed_funcs)[:3])}{'...' if len(removed_funcs) > 3 else ''} — removes functionality"],
                    risk=70,
                    details={'change_type': 'functions_removed', 'functions': list(removed_funcs)}
                ))
                details['functions_removed'] = list(removed_funcs)
                risk = max(risk, 70)
        
        # Function signature changes (HIGH RISK: 65)
        for func_name in old_names.intersection(new_names):
            old_func = old_funcs[func_name]
            new_func = new_funcs[func_name]
            
            if old_func['args'] != new_func['args'] or old_func['defaults'] != new_func['defaults']:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Function '{func_name}' signature changed — may break callers"],
                    risk=65,
                    details={
                        'change_type': 'function_signature_change',
                        'function': func_name,
                        'old_args': old_func['args'],
                        'new_args': new_func['args']
                    }
                ))
                details[f'sig_change_{func_name}'] = True
                risk = max(risk, 65)
            
            if old_func['returns'] != new_func['returns']:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Function '{func_name}' return type changed — downstream impact possible"],
                    risk=60,
                    details={
                        'change_type': 'return_type_change',
                        'function': func_name,
                        'old_return': old_func['returns'],
                        'new_return': new_func['returns']
                    }
                ))
                details[f'return_change_{func_name}'] = True
                risk = max(risk, 60)
        
        # Function call changes (MEDIUM RISK: 35)
        if old_calls != new_calls:
            added = new_calls - old_calls
            removed = old_calls - new_calls
            if added or removed:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=["Function call patterns changed — execution flow modified"],
                    risk=35,
                    details={
                        'change_type': 'call_pattern_change',
                        'added_calls': list(added)[:5],
                        'removed_calls': list(removed)[:5]
                    }
                ))
                details['call_changes'] = {'added': list(added), 'removed': list(removed)}
                risk = max(risk, 35)
        
        return risk, findings, details

    def _analyze_loops(self, old_nodes, new_nodes):
        """Analyze loop changes"""
        findings = []
        risk = 0
        details = {}
        
        old_loops = old_nodes['loops']
        new_loops = new_nodes['loops']
        
        old_types = [loop['type'] for loop in old_loops]
        new_types = [loop['type'] for loop in new_loops]
        
        old_breaks = old_nodes.get('breaks', 0)
        new_breaks = new_nodes.get('breaks', 0)
        old_continues = old_nodes.get('continues', 0)
        new_continues = new_nodes.get('continues', 0)
        
        # Loop count change (MEDIUM RISK: 40)
        if len(old_loops) != len(new_loops):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Loop count changed: {len(old_loops)} → {len(new_loops)} — iteration structure modified"],
                risk=40,
                details={
                    'change_type': 'loop_count_change',
                    'old_count': len(old_loops),
                    'new_count': len(new_loops)
                }
            ))
            details['loop_count_change'] = True
            risk = max(risk, 40)
        
        # For ↔ While conversion (HIGH RISK: 70)
        if 'For' in old_types and 'While' in new_types and 'For' not in new_types:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Loop type changed: FOR → WHILE — iteration logic fundamentally altered"],
                risk=70,
                details={'change_type': 'loop_type_for_to_while'}
            ))
            details['loop_type_change'] = 'for_to_while'
            risk = max(risk, 70)
        
        if 'While' in old_types and 'For' in new_types and 'While' not in new_types:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Loop type changed: WHILE → FOR — iteration logic fundamentally altered"],
                risk=70,
                details={'change_type': 'loop_type_while_to_for'}
            ))
            details['loop_type_change'] = 'while_to_for'
            risk = max(risk, 70)
        
        # Loop boundary/condition changes (MEDIUM RISK: 45)
        for i, (old_loop, new_loop) in enumerate(zip(old_loops, new_loops)):
            if old_loop['type'] == new_loop['type']:
                if old_loop['type'] == 'For' and old_loop.get('iter') != new_loop.get('iter'):
                    findings.append(AnalyzerResult(
                        name="ConditionShift",
                        findings=["FOR loop range modified — iteration bounds changed"],
                        risk=45,
                        details={'change_type': 'loop_boundary_change', 'loop_index': i}
                    ))
                    details[f'loop_{i}_boundary'] = True
                    risk = max(risk, 45)
                
                if old_loop['type'] == 'While' and old_loop.get('test') != new_loop.get('test'):
                    findings.append(AnalyzerResult(
                        name="ConditionShift",
                        findings=["WHILE loop condition modified — termination logic changed"],
                        risk=50,
                        details={'change_type': 'loop_condition_change', 'loop_index': i}
                    ))
                    details[f'loop_{i}_condition'] = True
                    risk = max(risk, 50)
        
        # Break/Continue changes (MEDIUM RISK: 40)
        if old_breaks != new_breaks or old_continues != new_continues:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Loop control statements changed: break({old_breaks}→{new_breaks}), continue({old_continues}→{new_continues}) — early exit logic modified"],
                risk=40,
                details={
                    'change_type': 'loop_control_change',
                    'old_breaks': old_breaks,
                    'new_breaks': new_breaks,
                    'old_continues': old_continues,
                    'new_continues': new_continues
                }
            ))
            details['loop_control_change'] = True
            risk = max(risk, 40)
        
        return risk, findings, details

    def _analyze_imports(self, old_nodes, new_nodes):
        """Analyze library/import changes"""
        findings = []
        risk = 0
        details = {}
        
        old_imports = set(old_nodes['imports'])
        new_imports = set(new_nodes['imports'])
        
        added = new_imports - old_imports
        removed = old_imports - new_imports
        
        # New imports (LOW-MEDIUM RISK: 25)
        if added:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"New dependencies added: {', '.join(list(added)[:3])}{'...' if len(added) > 3 else ''} — external dependencies introduced"],
                risk=25,
                details={'change_type': 'imports_added', 'libraries': list(added)}
            ))
            details['imports_added'] = list(added)
            risk = max(risk, 25)
        
        # Removed imports (MEDIUM-HIGH RISK: 55)
        if removed:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Dependencies removed: {', '.join(list(removed)[:3])}{'...' if len(removed) > 3 else ''} — may break dependent functionality"],
                risk=55,
                details={'change_type': 'imports_removed', 'libraries': list(removed)}
            ))
            details['imports_removed'] = list(removed)
            risk = max(risk, 55)
        
        return risk, findings, details

    def _analyze_datatypes(self, old_nodes, new_nodes):
        """Analyze data type changes"""
        findings = []
        risk = 0
        details = {}
        
        old_constants = old_nodes['constants']
        new_constants = new_nodes['constants']
        
        old_types = [c['type'] for c in old_constants]
        new_types = [c['type'] for c in new_constants]
        
        old_type_set = set(old_types)
        new_type_set = set(new_types)
        
        # Type changes (MEDIUM RISK: 50)
        type_changes = []
        if 'int' in old_type_set and 'float' in new_type_set:
            type_changes.append('int → float')
        if 'float' in old_type_set and 'int' in new_type_set:
            type_changes.append('float → int')
        if 'list' in old_type_set and 'tuple' in new_type_set:
            type_changes.append('list → tuple (mutable to immutable)')
        if 'list' in old_type_set and 'set' in new_type_set:
            type_changes.append('list → set (ordered to unordered)')
        if 'dict' in old_type_set and 'list' in new_type_set:
            type_changes.append('dict → list')
        
        if type_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Data type changes detected: {', '.join(type_changes)} — potential type compatibility issues"],
                risk=50,
                details={'change_type': 'datatype_change', 'changes': type_changes}
            ))
            details['datatype_changes'] = type_changes
            risk = max(risk, 50)
        
        # Return value changes (MEDIUM-HIGH RISK: 55)
        old_returns = [r for r in old_nodes['returns'] if r and r != "None"]
        new_returns = [r for r in new_nodes['returns'] if r and r != "None"]
        
        if set(old_returns) != set(new_returns):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Return values changed — output type or structure modified"],
                risk=55,
                details={
                    'change_type': 'return_value_change',
                    'old_returns': old_returns[:3],
                    'new_returns': new_returns[:3]
                }
            ))
            details['return_changes'] = True
            risk = max(risk, 55)
        
        return risk, findings, details

    def _analyze_control_flow(self, old_nodes, new_nodes):
        """Analyze control flow changes"""
        findings = []
        risk = 0
        details = {}
        
        old_ifs = len(old_nodes['if_nodes'])
        new_ifs = len(new_nodes['if_nodes'])
        old_trys = len(old_nodes['try_nodes'])
        new_trys = len(new_nodes['try_nodes'])
        
        # If statement changes (MEDIUM RISK: 40)
        if old_ifs != new_ifs:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Conditional branches changed: {old_ifs} → {new_ifs} if statements — decision paths modified"],
                risk=40,
                details={'change_type': 'if_count_change', 'old': old_ifs, 'new': new_ifs}
            ))
            details['if_change'] = True
            risk = max(risk, 40)
        
        # Try-except changes (MEDIUM RISK: 35)
        if old_trys != new_trys:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Exception handling changed: {old_trys} → {new_trys} try blocks — error handling modified"],
                risk=35,
                details={'change_type': 'try_count_change', 'old': old_trys, 'new': new_trys}
            ))
            details['try_change'] = True
            risk = max(risk, 35)
        
        return risk, findings, details

    def _analyze_structural(self, old_ast, new_ast, old_nodes, new_nodes):
        """Analyze structural AST changes (cosmetic/refactoring)"""
        findings = []
        risk = 0
        details = {}
        
        # Check variable name changes (VERY LOW RISK: 5)
        old_names = set(old_nodes['names'])
        new_names = set(new_nodes['names'])
        
        if old_names != new_names:
            added_names = new_names - old_names
            removed_names = old_names - new_names
            
            # If it's mostly renaming (similar counts), low risk
            if abs(len(old_names) - len(new_names)) <= 2:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=["Variable names changed — likely cosmetic refactoring"],
                    risk=5,
                    details={
                        'change_type': 'variable_rename',
                        'added': list(added_names)[:5],
                        'removed': list(removed_names)[:5]
                    }
                ))
                details['variable_rename'] = True
                risk = max(risk, 5)
            else:
                # Significant variable changes (MEDIUM RISK: 40)
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=["Significant variable structure changes detected"],
                    risk=40,
                    details={
                        'change_type': 'variable_structure_change',
                        'old_count': len(old_names),
                        'new_count': len(new_names)
                    }
                ))
                details['variable_structure_change'] = True
                risk = max(risk, 40)
        
        # Assignment changes (LOW-MEDIUM RISK: 30)
        old_assigns = set(old_nodes['assignments'])
        new_assigns = set(new_nodes['assignments'])
        
        if old_assigns != new_assigns and not details.get('variable_rename'):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Assignment patterns changed — data flow modified"],
                risk=30,
                details={'change_type': 'assignment_change'}
            ))
            details['assignment_change'] = True
            risk = max(risk, 30)
        
        # If still no risk detected but AST changed (VERY LOW RISK: 5)
        if risk == 0 and ast.dump(old_ast) != ast.dump(new_ast):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Minor structural changes detected — likely formatting or cosmetic"],
                risk=5,
                details={'change_type': 'cosmetic_change'}
            ))
            details['cosmetic_change'] = True
            risk = 5
        
        return risk, findings, details


# COMPLIANCE ANALYZER (IMPROVED)

class ComplianceAnalyzer:
    """
    Validates code against expected behavior contract.
    Uses AST structural analysis, not text matching.
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

        # Extract structural elements from code
        identifiers = extract_identifiers(tree)
        
        # Extract function names
        function_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_names.add(node.name)
        
        # Extract constants/literals
        constants = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                constants.add(str(node.value).lower())
        
        # Tokenize expected behavior (normalize)
        expected_lower = expected.lower()
        expected_words = set(expected_lower.split())
        
        # Multi-level matching
        identifier_match = bool(identifiers.intersection(expected_words))
        function_match = bool(function_names.intersection(expected_words))
        constant_match = bool(constants.intersection(expected_words))
        
        # Calculate semantic similarity score
        all_code_tokens = identifiers.union(function_names).union(constants)
        intersection = all_code_tokens.intersection(expected_words)
        
        if all_code_tokens:
            similarity = len(intersection) / max(len(expected_words), 1)
        else:
            similarity = 0.0
        
        # Determine risk based on similarity
        if similarity >= 0.5:
            risk = 0  # High match
        elif similarity >= 0.3:
            risk = 30  # Partial match
        elif similarity >= 0.1:
            risk = 50  # Low match
        else:
            risk = 70  # No match

        findings = []
        if risk > 0:
            findings.append(
                AnalyzerResult(
                    name="ContractViolation",
                    findings=[f"Expected behavior alignment: {similarity*100:.1f}% — code may not fully implement specification"],
                    risk=risk,
                    details={
                        "identifiers_found": sorted(list(identifiers))[:10],
                        "function_names": sorted(list(function_names)),
                        "expected_tokens": sorted(list(expected_words))[:10],
                        "matched_tokens": sorted(list(intersection)),
                        "similarity_score": round(similarity, 3)
                    }
                )
            )

        return findings, risk, {
            "semantic_similarity": similarity,
            "invariant_broken": risk > 50,
            "source_hash": src_hash,
            "comparison_method": "ast_structural_match",
            "identifiers_in_code": sorted(list(identifiers))[:15],
            "functions_in_code": sorted(list(function_names)),
            "expected_tokens": sorted(list(expected_words))[:15],
            "matched_tokens": sorted(list(intersection)),
            "similarity_percentage": round(similarity * 100, 2)
        }


# AI CALLS

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


# ROLE-LOCKED PROMPTS 

def technical_prompt(mode: str, signals: dict, findings: list, risk: int, depth: str = "balanced") -> str:
    """
    Role: Senior Static Analysis Engineer
    Purpose: Explain WHY the issue exists technically
    Depth: academic, balanced, or simple
    """
    
    if depth == "academic":
        return f"""You are a senior static analysis engineer presenting to academic peers.

Your task:
- Explain the issue using formal terminology
- Reference: AST parsing, semantic analysis, control flow graphs (CFG), data flow analysis (DFA), invariants, contracts
- Use precise technical language
- DO NOT simplify for non-experts
- DO NOT suggest fixes

Context:
Mode: {mode}
Signals: {json.dumps(signals, indent=2)}
Findings: {json.dumps([f.dict() if hasattr(f, 'dict') else f for f in findings], indent=2)}
Risk Score: {risk}

Explain:
- What technically caused the issue
- Which invariant or assumption was violated
- Why the risk score is justified from a static analysis perspective

Keep response under 150 words."""

    elif depth == "simple":
        return f"""You are a code reviewer explaining to a developer.

Your task:
- Explain what changed in the code
- Keep it practical and clear
- Avoid heavy academic terms (no CFG, DFA, invariants unless necessary)
- Focus on what matters for code quality

Context:
Mode: {mode}
What was detected: {json.dumps([f.dict() if hasattr(f, 'dict') else f for f in findings], indent=2)}
Risk Score: {risk}

Explain:
- What changed and why it matters
- What could go wrong
- Why this got the risk score it did

Keep response under 100 words. Be direct and practical."""

    else:  # balanced (default)
        return f"""You are a senior static analysis engineer.

Your task:
- Explain the issue in clear technical terms
- Reference code behavior, AST analysis, and semantic checks
- Balance precision with readability
- DO NOT oversimplify or use excessive jargon
- DO NOT suggest fixes

Context:
Mode: {mode}
Signals: {json.dumps(signals, indent=2)}
Findings: {json.dumps([f.dict() if hasattr(f, 'dict') else f for f in findings], indent=2)}
Risk Score: {risk}

Explain:
- What technically caused the issue
- Which assumption or contract was violated
- Why the risk score is justified

Keep response under 120 words."""

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

def comprehensive_analysis_prompt(old_code: str, new_code: str) -> str:
    """
    FIXED: Comprehensive line-by-line analysis prompt for CHANGE mode.
    Used when user wants detailed change analysis.
    """
    return f"""You are an expert Python static analysis engine performing comprehensive code comparison.

**TASK:** Analyze EVERY difference between OLD and NEW code versions.

═══════════════════════════════════════════════════
📄 OLD CODE:
═══════════════════════════════════════════════════
{old_code}

═══════════════════════════════════════════════════
📄 NEW CODE:
═══════════════════════════════════════════════════
{new_code}

═══════════════════════════════════════════════════
🔍 ANALYSIS REQUIREMENTS (MANDATORY):
═══════════════════════════════════════════════════

Analyze at these levels:

**1. SYNTAX CHANGES**
- Keywords (if/for/while/try/except/return/def/class)
- Indentation/block structure
- Decorators, type hints
- Comments with semantic meaning

**2. OPERATOR CHANGES**
- Comparison: >, >=, <, <=, ==, !=
- Logical: and, or, not
- Arithmetic: +, -, *, /, //, %, **
- Bitwise: &, |, ^, <<, >>
→ For EACH: Old → New → Impact

**3. CONTROL FLOW**
- if/elif/else conditions
- Loop types (for vs while)
- Loop bounds/ranges
- break/continue/return placement
- try/except/finally blocks
- Early exits

**4. FUNCTIONS & CLASSES**
- New/removed/renamed functions
- Parameter changes (count, names, defaults, types)
- Return type changes
- Method additions/removals
- Class hierarchy changes

**5. LIBRARIES & IMPORTS**
- New imports
- Removed imports
- Changed module names

**6. DATA TYPES**
- Variable type changes (int→float, list→dict, etc.)
- Collection changes (list→set→tuple)
- Mutability changes
- Return type modifications

**7. VARIABLES & STATE**
- New variables
- Removed variables
- Renamed variables
- Scope changes (local→global)
- Default value changes

**8. AST STRUCTURE**
- Node type changes
- Tree depth changes
- Semantic vs cosmetic

**9. RISK ASSESSMENT**
For EVERY change, classify:
- **LOW (0-20):** Cosmetic, safe refactor, formatting
- **MEDIUM (21-50):** Business logic tweak, boundary adjustment, naming
- **HIGH (51-100):** Logic inversion, breaking changes, control flow shift

═══════════════════════════════════════════════════
📋 OUTPUT FORMAT (STRICT):
═══════════════════════════════════════════════════

### 🔹 SUMMARY
Total changes: X
Critical changes: Y
Risk level: LOW/MEDIUM/HIGH

### 🔹 DETAILED CHANGES

**Change 1: [Category]**
- **Location:** Line X / Function Y
- **Old:** `code snippet`
- **New:** `code snippet`
- **Type:** [operator/function/loop/etc]
- **Risk:** [LOW/MEDIUM/HIGH] - [score]
- **Impact:** [what this means]

[Repeat for ALL changes]

### 🔹 CONTROL FLOW IMPACT
- Execution paths: [how they changed]
- Decision logic: [modifications]
- Error handling: [changes]

### 🔹 DATA & STATE IMPACT
- Variable flow: [changes]
- Type safety: [concerns]
- Side effects: [introduced/removed]

### 🔹 DEPENDENCY IMPACT
- New libraries: [list]
- Removed libraries: [list]
- API changes: [list]

### 🔹 FINAL RISK SCORE
**Overall Risk: XX/100**

Justification:
- [Key reason 1]
- [Key reason 2]
- [Key reason 3]

═══════════════════════════════════════════════════
⚠️ CRITICAL RULES:
═══════════════════════════════════════════════════
✓ Report EVERY change, no matter how small
✓ Be precise and specific
✓ Use actual code snippets
✓ Quantify risk numerically
✓ Never assume intent
✓ If uncertain about impact, say "UNCERTAIN"
✗ Do NOT summarize vaguely
✗ Do NOT skip "minor" changes
✗ Do NOT editorialize

**BEGIN ANALYSIS NOW.**"""

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


# ANALYZE ENDPOINT

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Main analysis endpoint with comprehensive AST-based logic.
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

            # Choose analysis depth
            if req.enable_deep_analysis:
                # Comprehensive line-by-line analysis
                try:
                    comprehensive, provider = ai(comprehensive_analysis_prompt(req.old_condition, req.new_condition))
                    tech = comprehensive  # Deep analysis serves as technical explanation
                except Exception as e:
                    print(f"Deep analysis failed: {e}")
                    tech, provider = ai(technical_prompt(mode, signals, findings, risk, req.technical_depth))
            else:
                # Standard technical explanation
                tech, provider = ai(technical_prompt(mode, signals, findings, risk, req.technical_depth))
            
            # Always generate human explanation
            try:
                human, _ = ai(human_prompt(findings, risk))
            except Exception as e:
                human = "Analysis completed. Please review technical findings."

            result = {
                "mode": "CHANGE",
                "status": pass_fail_from_risk(risk),
                "risk_score": risk,
                "analyzer_findings": [f.dict() for f in findings],
                "semantic_signals": signals,
                "technical_explanation": tech,
                "human_explanation": human,
                "ai_provider": provider,
                "technical_depth": req.technical_depth,
                "deep_analysis_enabled": req.enable_deep_analysis,
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

            # AI explains (does not decide) - with configurable depth
            try:
                tech, provider = ai(technical_prompt(mode, signals, findings, risk, req.technical_depth))
                solution, _ = ai(compliance_solution_prompt(signals["source_hash"], req.expected_output, risk))
            except Exception as e:
                tech = "Analysis completed. Review findings below."
                solution = "Verify code matches expected behavior specification."
                provider = "None"

            result = {
                "mode": "COMPLIANCE",
                "status": pass_fail_from_risk(risk),
                "risk_score": risk,
                "analyzer_findings": [f.dict() for f in findings],
                "semantic_signals": signals,
                "technical_explanation": tech,
                "ai_solution": solution,
                "ai_provider": provider,
                "technical_depth": req.technical_depth,
                "deep_analysis_enabled": req.enable_deep_analysis,
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


# DOWNLOAD JSON

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

# DOWNLOAD PDF

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


# HEALTH CHECK

@app.get("/")
async def health():
    """API health check and information"""
    return {
        "status": "ok",
        "service": "CRONOS API v4.0.0 - COMPREHENSIVE & FAIR AST ANALYSIS",
        "cors": "ALLOW ALL (testing mode)",
        "improvements": [
            "CHANGE mode: Comprehensive AST-based analysis with FAIR risk scoring",
            "Explicit classification: operators, functions, loops, imports, datatypes, control flow",
            "FAIR risk buckets: boundary(10), rename(35), logic change(45), inversion(80-95)",
            "AI: Explanation only (not decision-making)",
            "Role-locked prompts for distinct outputs",
            "Reasonable status: PASS(≤20), WARN(21-50), FAIL(51-100)",
            "Configurable technical depth: academic/balanced/simple",
            "Deep analysis mode: Fixed comprehensive line-by-line comparison",
            "Improved compliance: Multi-level structural matching"
        ],
        "analysis_categories": [
            "1. Operator changes (boundary/equality/logical)",
            "2. Function changes (rename/signature/calls/returns)",
            "3. Loop changes (type/boundary/body/break/continue)",
            "4. Library changes (imports/dependencies)",
            "5. Data type changes (int/float/list/dict/returns)",
            "6. Control flow (if/try/branches)",
            "7. Structural changes (variables/assignments/cosmetic)"
        ],
        "risk_levels": {
            "0-20": "PASS - Safe changes (boundary tweaks, cosmetic)",
            "21-50": "WARN - Review recommended (renames, business logic)",
            "51-100": "FAIL - High risk (inversions, breaking changes)"
        },
        "technical_depth_options": {
            "academic": "Heavy terminology (CFG, DFA, invariants) - for SIH/research/professors",
            "balanced": "Clear technical language - default, good for most users",
            "simple": "Minimal jargon - for product users/industry"
        },
        "analysis_modes": {
            "standard": "Fast analysis with smart risk scoring (enable_deep_analysis: false)",
            "deep": "Comprehensive line-by-line comparison (enable_deep_analysis: true)"
        },
        "features": {
            "gemini": gemini_client is not None,
            "openrouter": OPENROUTER_ENABLED
        },
        "endpoints": [
            "POST /analyze",
            "GET /report/json/{id}",
            "GET /report/pdf/{id}"
        ],
        "example_requests": {
            "boundary_change": {
                "mode": "CHANGE",
                "old_condition": "x > 10",
                "new_condition": "x >= 10",
                "technical_depth": "balanced",
                "enable_deep_analysis": False,
                "expected_result": "PASS (risk: 10)"
            },
            "function_rename": {
                "mode": "CHANGE",
                "old_condition": "def is_weekday(day):\n    return day in [1,2,3,4,5]",
                "new_condition": "def is_business_day(day):\n    return day in [1,2,3,4,5]",
                "expected_result": "WARN (risk: 35)"
            },
            "logical_inversion": {
                "mode": "CHANGE",
                "old_condition": "if x > 10 and y < 5:",
                "new_condition": "if x > 10 or y < 5:",
                "expected_result": "FAIL (risk: 95)"
            }
        }
    }


# STARTUP EVENT

@app.on_event("startup")
async def startup_event():
    """Print startup information"""
    print("=" * 70)
    print("✅ CRONOS v4.0.0 - COMPREHENSIVE & FAIR AST ANALYSIS")
    print("=" * 70)
    print(f"📁 Report directory: {REPORT_DIR}")
    print(f"🤖 Gemini: {'✅ Enabled' if gemini_client else '❌ Disabled'}")
    print(f"🤖 OpenRouter: {'✅ Enabled' if OPENROUTER_ENABLED else '❌ Disabled'}")
    print("🌐 CORS: ALLOW ALL (*) - TESTING MODE")
    print()
    print("🔧 ANALYSIS CATEGORIES:")
    print("  1. Operator changes (boundary/equality/logical)")
    print("  2. Function changes (rename/signature/calls/returns)")
    print("  3. Loop changes (type/boundary/body/break/continue)")
    print("  4. Library changes (imports/dependencies)")
    print("  5. Data type changes (int/float/list/dict/returns)")
    print("  6. Control flow (if/try/branches)")
    print("  7. Structural changes (variables/assignments/cosmetic)")
    print()
    print("📊 FAIR RISK LEVELS:")
    print("  • 0-20:   PASS ✅ (boundary tweaks, cosmetic, safe refactor)")
    print("  • 21-50:  WARN ⚠️  (renames, business logic, moderate changes)")
    print("  • 51-100: FAIL ❌ (inversions, breaking changes, high impact)")
    print()
    print("🎯 KEY FEATURES:")
    print("  ✓ AST-only analysis (no AI decision-making)")
    print("  ✓ FAIR risk scoring (not overly harsh)")
    print("  ✓ Function rename → WARN (not FAIL)")
    print("  ✓ Boundary change → PASS (not WARN)")
    print("  ✓ Logical inversion → FAIL (appropriate)")
    print("  ✓ Role-locked prompts for distinct outputs")
    print("  ✓ Technical depth: academic/balanced/simple")
    print("  ✓ Deep analysis: FIXED comprehensive comparison")
    print("  ✓ Improved compliance: Multi-level matching")
    print("=" * 70)
