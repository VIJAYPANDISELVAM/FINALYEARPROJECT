```python
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
    """Determine PASS/WARN/FAIL based on risk threshold"""
    if risk < 30:
        return "PASS"
    elif risk < 60:
        return "WARN"
    else:
        return "FAIL"


# CHANGE MODE ANALYZER (COMPREHENSIVE)

class ChangeAnalyzer:
    """
    Analyzes behavioral changes between old and new conditions.
    Uses comprehensive AST structural comparison with explicit classification
    of operator, function, loop, library, data-type, and structural changes.
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

        # 1. OPERATOR CHANGES
        operator_risk, operator_findings, operator_details = self._analyze_operators(
            old, new, old_ast, new_ast, old_nodes, new_nodes
        )
        if operator_risk > 0:
            findings.extend(operator_findings)
            risk_scores.append(operator_risk)
            change_details.update(operator_details)

        # 2. FUNCTION CHANGES
        function_risk, function_findings, function_details = self._analyze_functions(
            old_ast, new_ast, old_nodes, new_nodes
        )
        if function_risk > 0:
            findings.extend(function_findings)
            risk_scores.append(function_risk)
            change_details.update(function_details)

        # 3. LOOP CHANGES
        loop_risk, loop_findings, loop_details = self._analyze_loops(
            old_ast, new_ast, old_nodes, new_nodes
        )
        if loop_risk > 0:
            findings.extend(loop_findings)
            risk_scores.append(loop_risk)
            change_details.update(loop_details)

        # 4. LIBRARY/IMPORT CHANGES
        library_risk, library_findings, library_details = self._analyze_imports(
            old_ast, new_ast
        )
        if library_risk > 0:
            findings.extend(library_findings)
            risk_scores.append(library_risk)
            change_details.update(library_details)

        # 5. DATA TYPE CHANGES
        datatype_risk, datatype_findings, datatype_details = self._analyze_datatypes(
            old_ast, new_ast, old_nodes, new_nodes
        )
        if datatype_risk > 0:
            findings.extend(datatype_findings)
            risk_scores.append(datatype_risk)
            change_details.update(datatype_details)

        # 6. STRUCTURAL AST CHANGES (if not covered by above)
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
            'attributes': []
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
                    'returns': ast.unparse(node.returns) if node.returns else None
                })
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    nodes['calls'].append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    nodes['calls'].append(node.func.attr)
            elif isinstance(node, (ast.For, ast.While)):
                nodes['loops'].append({
                    'type': type(node).__name__,
                    'target': ast.unparse(node.target) if isinstance(node, ast.For) else None,
                    'iter': ast.unparse(node.iter) if isinstance(node, ast.For) else None,
                    'test': ast.unparse(node.test) if isinstance(node, ast.While) else None
                })
            elif isinstance(node, ast.Return):
                nodes['returns'].append(ast.unparse(node.value) if node.value else None)
            elif isinstance(node, ast.Constant):
                nodes['constants'].append({
                    'type': type(node.value).__name__,
                    'value': str(node.value)
                })
            elif isinstance(node, ast.Name):
                nodes['names'].append(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        nodes['imports'].append(alias.name)
                else:
                    nodes['imports'].append(node.module if node.module else 'relative')
            elif isinstance(node, ast.Attribute):
                nodes['attributes'].append(node.attr)
        
        return nodes

    def _analyze_operators(self, old_code, new_code, old_ast, new_ast, old_nodes, new_nodes):
        """Analyze operator changes"""
        findings = []
        risk = 0
        details = {}
        
        old_compare = old_nodes['compare_ops']
        new_compare = new_nodes['compare_ops']
        old_bool = old_nodes['bool_ops']
        new_bool = new_nodes['bool_ops']
        
        # BOUNDARY OPERATOR CHANGES (LOW RISK: 20)
        boundary_changes = []
        if 'Gt' in old_compare and 'GtE' in new_compare and 'Gt' not in new_compare:
            boundary_changes.append('> changed to >=')
            risk = max(risk, 20)
        if 'GtE' in old_compare and 'Gt' in new_compare and 'GtE' not in new_compare:
            boundary_changes.append('>= changed to >')
            risk = max(risk, 20)
        if 'Lt' in old_compare and 'LtE' in new_compare and 'Lt' not in new_compare:
            boundary_changes.append('< changed to <=')
            risk = max(risk, 20)
        if 'LtE' in old_compare and 'Lt' in new_compare and 'LtE' not in new_compare:
            boundary_changes.append('<= changed to <')
            risk = max(risk, 20)
        
        if boundary_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Boundary operator change detected: {', '.join(boundary_changes)} — low behavioral impact"],
                risk=20,
                details={'change_type': 'boundary_adjustment', 'changes': boundary_changes}
            ))
            details['boundary_changes'] = boundary_changes
        
        # EQUALITY OPERATOR CHANGES (HIGH RISK: 80)
        equality_changes = []
        if 'Eq' in old_compare and 'NotEq' in new_compare:
            equality_changes.append('== changed to !=')
            risk = max(risk, 80)
        if 'NotEq' in old_compare and 'Eq' in new_compare:
            equality_changes.append('!= changed to ==')
            risk = max(risk, 80)
        
        if equality_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"High-risk equality operator inversion: {', '.join(equality_changes)} — reverses condition logic"],
                risk=80,
                details={'change_type': 'equality_inversion', 'changes': equality_changes}
            ))
            details['equality_changes'] = equality_changes
        
        # LOGICAL OPERATOR CHANGES (VERY HIGH RISK: 100)
        logical_changes = []
        if 'And' in old_bool and 'Or' in new_bool:
            logical_changes.append('AND changed to OR')
            risk = max(risk, 100)
        if 'Or' in old_bool and 'And' in new_bool:
            logical_changes.append('OR changed to AND')
            risk = max(risk, 100)
        
        if logical_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Critical logical operator change: {', '.join(logical_changes)} — drastically alters control flow"],
                risk=100,
                details={'change_type': 'logical_inversion', 'changes': logical_changes}
            ))
            details['logical_changes'] = logical_changes
        
        # OTHER COMPARISON OPERATORS (MEDIUM-HIGH RISK: 60)
        other_compare_changes = []
        if set(old_compare) != set(new_compare) and not boundary_changes and not equality_changes:
            old_set = set(old_compare)
            new_set = set(new_compare)
            removed = old_set - new_set
            added = new_set - old_set
            if removed or added:
                other_compare_changes.append(f"removed: {removed}, added: {added}")
                risk = max(risk, 60)
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Comparison operator change detected — potential behavioral shift"],
                    risk=60,
                    details={'change_type': 'operator_change', 'removed': list(removed), 'added': list(added)}
                ))
                details['other_operator_changes'] = {'removed': list(removed), 'added': list(added)}
        
        return risk, findings, details

    def _analyze_functions(self, old_ast, new_ast, old_nodes, new_nodes):
        """Analyze function changes"""
        findings = []
        risk = 0
        details = {}
        
        old_funcs = {f['name']: f for f in old_nodes['functions']}
        new_funcs = {f['name']: f for f in new_nodes['functions']}
        
        # Functions added or removed
        added_funcs = set(new_funcs.keys()) - set(old_funcs.keys())
        removed_funcs = set(old_funcs.keys()) - set(new_funcs.keys())
        
        if added_funcs:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"New functions added: {', '.join(added_funcs)} — introduces new behavior"],
                risk=60,
                details={'change_type': 'function_added', 'functions': list(added_funcs)}
            ))
            details['functions_added'] = list(added_funcs)
            risk = max(risk, 60)
        
        if removed_funcs:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Functions removed: {', '.join(removed_funcs)} — removes existing behavior"],
                risk=80,
                details={'change_type': 'function_removed', 'functions': list(removed_funcs)}
            ))
            details['functions_removed'] = list(removed_funcs)
            risk = max(risk, 80)
        
        # Functions with signature changes
        for func_name in set(old_funcs.keys()).intersection(set(new_funcs.keys())):
            old_func = old_funcs[func_name]
            new_func = new_funcs[func_name]
            
            # Check argument changes (HIGH RISK: 80)
            if old_func['args'] != new_func['args']:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Function '{func_name}' signature changed: parameters modified — high risk of breaking calls"],
                    risk=80,
                    details={
                        'change_type': 'function_signature_change',
                        'function': func_name,
                        'old_args': old_func['args'],
                        'new_args': new_func['args']
                    }
                ))
                details[f'function_{func_name}_signature'] = {
                    'old': old_func['args'],
                    'new': new_func['args']
                }
                risk = max(risk, 80)
            
            # Check return type changes (HIGH RISK: 80)
            if old_func['returns'] != new_func['returns']:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Function '{func_name}' return type changed — may break dependent code"],
                    risk=80,
                    details={
                        'change_type': 'function_return_change',
                        'function': func_name,
                        'old_return': old_func['returns'],
                        'new_return': new_func['returns']
                    }
                ))
                details[f'function_{func_name}_return'] = {
                    'old': old_func['returns'],
                    'new': new_func['returns']
                }
                risk = max(risk, 80)
        
        # Function call changes (MEDIUM RISK: 40)
        old_calls = set(old_nodes['calls'])
        new_calls = set(new_nodes['calls'])
        if old_calls != new_calls:
            added_calls = new_calls - old_calls
            removed_calls = old_calls - new_calls
            if added_calls or removed_calls:
                findings.append(AnalyzerResult(
                    name="ConditionShift",
                    findings=[f"Function calls changed — execution flow modified"],
                    risk=40,
                    details={
                        'change_type': 'function_calls_change',
                        'added_calls': list(added_calls),
                        'removed_calls': list(removed_calls)
                    }
                ))
                details['call_changes'] = {
                    'added': list(added_calls),
                    'removed': list(removed_calls)
                }
                risk = max(risk, 40)
        
        return risk, findings, details

    def _analyze_loops(self, old_ast, new_ast, old_nodes, new_nodes):
        """Analyze loop changes"""
        findings = []
        risk = 0
        details = {}
        
        old_loops = old_nodes['loops']
        new_loops = new_nodes['loops']
        
        # Loop type changes (HIGH RISK: 80)
        old_loop_types = [loop['type'] for loop in old_loops]
        new_loop_types = [loop['type'] for loop in new_loops]
        
        if len(old_loops) != len(new_loops):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Loop count changed from {len(old_loops)} to {len(new_loops)} — control flow altered"],
                risk=60,
                details={
                    'change_type': 'loop_count_change',
                    'old_count': len(old_loops),
                    'new_count': len(new_loops)
                }
            ))
            details['loop_count_change'] = {'old': len(old_loops), 'new': len(new_loops)}
            risk = max(risk, 60)
        
        # Check for For <-> While conversion
        if 'For' in old_loop_types and 'While' in new_loop_types and 'For' not in new_loop_types:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Loop type changed from FOR to WHILE — iteration logic fundamentally altered"],
                risk=80,
                details={'change_type': 'loop_type_for_to_while'}
            ))
            details['loop_type_change'] = 'for_to_while'
            risk = max(risk, 80)
        
        if 'While' in old_loop_types and 'For' in new_loop_types and 'While' not in new_loop_types:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Loop type changed from WHILE to FOR — iteration logic fundamentally altered"],
                risk=80,
                details={'change_type': 'loop_type_while_to_for'}
            ))
            details['loop_type_change'] = 'while_to_for'
            risk = max(risk, 80)
        
        # Check loop boundary/condition changes (MEDIUM RISK: 60)
        for i, (old_loop, new_loop) in enumerate(zip(old_loops, new_loops)):
            if old_loop['type'] == new_loop['type']:
                if old_loop['type'] == 'For':
                    if old_loop['iter'] != new_loop['iter']:
                        findings.append(AnalyzerResult(
                            name="ConditionShift",
                            findings=[f"FOR loop iteration range changed — boundary conditions modified"],
                            risk=60,
                            details={
                                'change_type': 'loop_boundary_change',
                                'old_iter': old_loop['iter'],
                                'new_iter': new_loop['iter']
                            }
                        ))
                        details[f'loop_{i}_boundary'] = {
                            'old': old_loop['iter'],
                            'new': new_loop['iter']
                        }
                        risk = max(risk, 60)
                elif old_loop['type'] == 'While':
                    if old_loop['test'] != new_loop['test']:
                        findings.append(AnalyzerResult(
                            name="ConditionShift",
                            findings=[f"WHILE loop condition changed — termination logic altered"],
                            risk=60,
                            details={
                                'change_type': 'loop_condition_change',
                                'old_test': old_loop['test'],
                                'new_test': new_loop['test']
                            }
                        ))
                        details[f'loop_{i}_condition'] = {
                            'old': old_loop['test'],
                            'new': new_loop['test']
                        }
                        risk = max(risk, 60)
        
        return risk, findings, details

    def _analyze_imports(self, old_ast, new_ast):
        """Analyze library/import changes"""
        findings = []
        risk = 0
        details = {}
        
        old_imports = set()
        new_imports = set()
        
        for node in ast.walk(old_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    old_imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                old_imports.add(node.module if node.module else 'relative')
        
        for node in ast.walk(new_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    new_imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                new_imports.add(node.module if node.module else 'relative')
        
        added_imports = new_imports - old_imports
        removed_imports = old_imports - new_imports
        
        if added_imports:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"New libraries imported: {', '.join(added_imports)} — introduces external dependencies"],
                risk=40,
                details={
                    'change_type': 'imports_added',
                    'libraries': list(added_imports)
                }
            ))
            details['imports_added'] = list(added_imports)
            risk = max(risk, 40)
        
        if removed_imports:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Libraries removed: {', '.join(removed_imports)} — may break dependent functionality"],
                risk=60,
                details={
                    'change_type': 'imports_removed',
                    'libraries': list(removed_imports)
                }
            ))
            details['imports_removed'] = list(removed_imports)
            risk = max(risk, 60)
        
        return risk, findings, details

    def _analyze_datatypes(self, old_ast, new_ast, old_nodes, new_nodes):
        """Analyze data type changes"""
        findings = []
        risk = 0
        details = {}
        
        old_constants = old_nodes['constants']
        new_constants = new_nodes['constants']
        
        # Extract constant types
        old_types = [c['type'] for c in old_constants]
        new_types = [c['type'] for c in new_constants]
        
        old_type_set = set(old_types)
        new_type_set = set(new_types)
        
        # Check for type changes (MEDIUM-HIGH RISK: 60)
        type_changes = []
        if 'int' in old_type_set and 'float' in new_type_set:
            type_changes.append('int → float')
            risk = max(risk, 60)
        if 'float' in old_type_set and 'int' in new_type_set:
            type_changes.append('float → int')
            risk = max(risk, 60)
        if 'list' in old_type_set and 'tuple' in new_type_set:
            type_changes.append('list → tuple (mutable to immutable)')
            risk = max(risk, 60)
        if 'list' in old_type_set and 'set' in new_type_set:
            type_changes.append('list → set (ordered to unordered)')
            risk = max(risk, 60)
        if 'dict' in old_type_set and 'list' in new_type_set:
            type_changes.append('dict → list')
            risk = max(risk, 60)
        
        if type_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Data type changes detected: {', '.join(type_changes)} — potential type errors"],
                risk=60,
                details={
                    'change_type': 'datatype_change',
                    'changes': type_changes
                }
            ))
            details['datatype_changes'] = type_changes
        
        # Check return type changes (analyzed in function analysis but also check here)
        old_returns = [r for r in old_nodes['returns'] if r]
        new_returns = [r for r in new_nodes['returns'] if r]
        
        if len(old_returns) != len(new_returns) or (old_returns and new_returns and old_returns != new_returns):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Return values changed — output type or structure modified"],
                risk=80,
                details={
                    'change_type': 'return_type_change',
                    'old_returns': old_returns,
                    'new_returns': new_returns
                }
            ))
            details['return_changes'] = {
                'old': old_returns,
                'new': new_returns
            }
            risk = max(risk, 80)
        
        return risk, findings, details

    def _analyze_structural(self, old_ast, new_ast, old_nodes, new_nodes):
        """Analyze structural AST changes"""
        findings = []
        risk = 0
        details = {}
        
        # Count different node types
        old_node_counts = self._count_node_types(old_ast)
        new_node_counts = self._count_node_types(new_ast)
        
        # Detect major structural changes
        structural_changes = []
        
        # Control flow changes
        if old_node_counts.get('If', 0) != new_node_counts.get('If', 0):
            structural_changes.append(f"If statements: {old_node_counts.get('If', 0)} → {new_node_counts.get('If', 0)}")
            risk = max(risk, 60)
        
        if old_node_counts.get('Try', 0) != new_node_counts.get('Try', 0):
            structural_changes.append(f"Try-except blocks: {old_node_counts.get('Try', 0)} → {new_node_counts.get('Try', 0)}")
            risk = max(risk, 40)
        
        # Assignment changes
        if old_node_counts.get('Assign', 0) != new_node_counts.get('Assign', 0):
            structural_changes.append(f"Assignments: {old_node_counts.get('Assign', 0)} → {new_node_counts.get('Assign', 0)}")
            risk = max(risk, 40)
        
        if structural_changes:
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=[f"Structural changes detected: {'; '.join(structural_changes)} — control flow modified"],
                risk=risk if risk > 0 else 60,
                details={
                    'change_type': 'structural_change',
                    'changes': structural_changes,
                    'old_structure': old_node_counts,
                    'new_structure': new_node_counts
                }
            ))
            details['structural_changes'] = {
                'changes': structural_changes,
                'old': old_node_counts,
                'new': new_node_counts
            }
        
        # If no specific changes found but AST is different, it's a minor refactor
        if not structural_changes and ast.dump(old_ast) != ast.dump(new_ast):
            findings.append(AnalyzerResult(
                name="ConditionShift",
                findings=["Minor code refactoring detected — cosmetic or minor structural changes"],
                risk=40,
                details={'change_type': 'minor_refactor'}
            ))
            details['change_type'] = 'minor_refactor'
            risk = max(risk, 40)
        
        return risk, findings, details

    def _count_node_types(self, tree):
        """Count different AST node types"""
        counts = {}
        for node in ast.walk(tree):
            node_type = type(node).__name__
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts


# COMPLIANCE ANALYZER 

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
    Comprehensive line-by-line analysis prompt for CHANGE mode.
    Used when user wants detailed change analysis.
    """
    return f"""You are an expert Python static analysis engine.  
Your job is to perform a COMPLETE, line-by-line, structural, semantic, and behavioral comparison between two Python code versions.

You must analyze and report EVERY change — no matter how small.

INPUT

OLD CODE:
{old_code}

NEW CODE:
{new_code}

YOUR TASK (MANDATORY)

Compare OLD vs NEW code at these levels:

1) SYNTAX-LEVEL CHANGES  
- Keywords (if, for, while, try, except, return)
- Indentation or block structure
- Decorators, annotations, type hints
- Comments affecting meaning
- Formatting affecting execution

2) OPERATOR-LEVEL CHANGES  
- Comparison operators (>, >=, <, <=, ==, !=)
- Logical operators (and/or/not)
- Arithmetic operators (+, -, *, /, //, %, **)
- Bitwise operators (&, |, ^, <<, >>)
- Assignment operators (=, +=, -=)

For each: Old operator → New operator → Impact

3) CONTROL FLOW CHANGES  
- if/elif/else conditions
- Loop types (for → while)
- Loop bounds/iteration logic
- Break/continue/return behavior
- Exception handling (try/except/finally)
- Function call order

4) FUNCTION & CLASS CHANGES  
- New/removed functions
- Signature changes (parameters, defaults, types)
- Behavior changes inside functions
- New/removed classes
- Method changes
- Constructor (__init__) changes
- Inheritance changes

5) LIBRARY & IMPORT CHANGES  
- New/removed imports
- Version-specific libraries
- External dependencies

6) DATA TYPE CHANGES  
- Variable type changes (int → float, list → dict)
- Structure changes (list → tuple)
- Mutable vs immutable
- Return type changes

7) VARIABLE & STATE CHANGES  
- New/removed variables
- Scope changes (local → global)
- Default value changes
- Side effects introduced

8) AST STRUCTURAL CHANGES  
- AST structure changed?
- Which nodes changed?
- Semantic or cosmetic?

9) RISK ASSESSMENT  
For every change:
- LOW: Cosmetic/safe refactor
- MEDIUM: Possible behavior change
- HIGH: Likely breaking change

=========================================
OUTPUT FORMAT (STRICT)
=========================================

### 🔹 SUMMARY  
Brief overview of total changes.

### 🔹 DETAILED CHANGE LIST  
For each change:
- Location (line/function)
- Old behavior
- New behavior
- Type of change
- Risk level
- Why this matters

### 🔹 CONTROL FLOW IMPACT  
How execution paths changed.

### 🔹 DATA & STATE IMPACT  
How data flow changed.

### 🔹 LIBRARY IMPACT  
Dependency risks.

### 🔹 FINAL RISK SCORE (0–100)  
Overall score with justification.

RULES

- Do NOT summarize loosely
- Do NOT skip small changes
- Treat every line as important
- Be skeptical and critical
- Prefer accuracy over brevity
- Never assume intent — only analyze what you see
- If unclear, say "UNCERTAIN"

Analyze now."""

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
                comprehensive, provider = ai(comprehensive_analysis_prompt(req.old_condition, req.new_condition))
                tech = comprehensive  # Deep analysis serves as technical explanation
            else:
                # Standard technical explanation
                tech, provider = ai(technical_prompt(mode, signals, findings, risk, req.technical_depth))
            
            # Always generate human explanation
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
            tech, provider = ai(technical_prompt(mode, signals, findings, risk, req.technical_depth))
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
        "service": "CRONOS API v4.0.0 - COMPREHENSIVE AST ANALYSIS",
        "cors": "ALLOW ALL (testing mode)",
        "improvements": [
            "CHANGE mode: Comprehensive AST-based analysis",
            "Explicit classification: operators, functions, loops, imports, datatypes, structure",
            "Risk scoring: 0-20-40-60-80-100 normalized buckets",
            "AI: Explanation only (not decision-making)",
            "Role-locked prompts for distinct outputs",
            "Three-level status: PASS/WARN/FAIL",
            "Configurable technical depth: academic/balanced/simple",
            "Deep analysis mode: Comprehensive line-by-line comparison"
        ],
        "analysis_categories": [
            "1. Operator changes (boundary/equality/logical)",
            "2. Function changes (signature/calls/returns)",
            "3. Loop changes (type/boundary/body)",
            "4. Library changes (imports/dependencies)",
            "5. Data type changes (int/float/list/dict/returns)",
            "6. Structural changes (control flow/refactoring)"
        ],
        "risk_levels": {
            "0-29": "PASS - Safe changes",
            "30-59": "WARN - Review recommended",
            "60-100": "FAIL - High risk changes"
        },
        "technical_depth_options": {
            "academic": "Heavy terminology (CFG, DFA, invariants) - for SIH/research/professors",
            "balanced": "Clear technical language - default, good for most users",
            "simple": "Minimal jargon - for product users/industry"
        },
        "analysis_modes": {
            "standard": "Fast analysis with smart risk scoring (enable_deep_analysis: false)",
            "deep": "Comprehensive line-by-line comparison covering syntax, operators, control flow, functions, imports, data types, variables, AST, and detailed risk assessment (enable_deep_analysis: true)"
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
        "example_request": {
            "mode": "CHANGE",
            "old_condition": "x > 10 and y == 5",
            "new_condition": "x >= 10 or y != 5",
            "technical_depth": "balanced",
            "enable_deep_analysis": False
        }
    }


# STARTUP EVENT

@app.on_event("startup")
async def startup_event():
    """Print startup information"""
    print("=" * 60)
    print("✅ CRONOS v4.0.0 - COMPREHENSIVE AST ANALYSIS")
    print("=" * 60)
    print(f"📁 Report directory: {REPORT_DIR}")
    print(f"🤖 Gemini: {'✅ Enabled' if gemini_client else '❌ Disabled'}")
    print(f"🤖 OpenRouter: {'✅ Enabled' if OPENROUTER_ENABLED else '❌ Disabled'}")
    print("🌐 CORS: ALLOW ALL (*) - TESTING MODE")
    print()
    print("🔧 ANALYSIS CATEGORIES:")
    print("  1. Operator changes (boundary/equality/logical)")
    print("  2. Function changes (signature/calls/returns)")
    print("  3. Loop changes (type/boundary/body)")
    print("  4. Library changes (imports/dependencies)")
    print("  5. Data type changes (int/float/list/dict/returns)")
    print("  6. Structural changes (control flow/refactoring)")
    print()
    print("📊 RISK LEVELS:")
    print("  • 0-29:   PASS (Safe changes)")
    print("  • 30-59:  WARN (Review recommended)")
    print("  • 60-100: FAIL (High risk changes)")
    print()
    print("🎯 FEATURES:")
    print("  ✓ AST-only analysis (no AI decision-making)")
    print("  ✓ Role-locked prompts for distinct outputs")
    print("  ✓ Technical depth: academic/balanced/simple")
    print("  ✓ Deep analysis: Line-by-line comprehensive comparison")
    print("=" * 60)
```
