# demo_review.py
# CLI tool to demonstrate three code review approaches:
# 1. diff-only: Just the git diff (LLM likely misses bugs)
# 2. all-code: Entire codebase (finds bugs but uses many tokens)
# 3. smart: Impact slicing (finds bugs with minimal tokens)
import os
import sys
import json
import time
import io

# Force UTF-8 encoding for standard output and error to prevent crashes on Windows with emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import pathlib
import subprocess
import ast
import argparse
from typing import Dict, Set, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()



import fnmatch

def get_exclude_patterns(repo_path: str):
    yaml_path = os.path.join(repo_path, ".ai-review.yaml")
    patterns = []
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                in_excludes = False
                for line in f:
                    line = line.strip()
                    if line == "exclude_patterns:":
                        in_excludes = True
                    elif in_excludes and line.startswith("-"):
                        pat = line[1:].strip().strip('"').strip("'")
                        patterns.append(pat)
                    elif in_excludes and not line.startswith("-") and line != "" and not line.startswith("#"):
                        in_excludes = False
        except Exception:
            pass
    return patterns

def is_excluded_file(filepath: str, repo_path: str, patterns):
    filepath = filepath.replace("\\", "/")
    for p in patterns:
        p_norm = p.replace("\\", "/")
        if p_norm.startswith("**/"):
            if fnmatch.fnmatch(filepath, p_norm) or fnmatch.fnmatch(filepath, p_norm[3:]):
                return True
        elif fnmatch.fnmatch(filepath, p_norm) or fnmatch.fnmatch(filepath, f"*/{p_norm}"):
            return True
    return False

VALID_AUTH_DEPENDENCIES = ['get_current_user', 'require_admin', 'require_staff', 'staff_or_admin_required']

BUG_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "bugs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "changed_file": {"type": "string"},
                    "changed_lines": {"type": "string"},
                    "bug_category": {"type": "string"},
                    "summary": {"type": "string"},
                    "comment": {"type": "string"},
                    "diff_fix_suggestion": {"type": "string"},
                    "confidence": {"type": "number"},
                    "owasp_category": {"type": "string"},
                    "concrete_exploit_path": {"type": "string"},
                    "ast_primitive_id": {"type": "string"}
                },
                "required": ["changed_file", "changed_lines", "bug_category", "summary", "comment", "diff_fix_suggestion", "confidence", "owasp_category", "concrete_exploit_path", "ast_primitive_id"],
                "additionalProperties": False
            }
        }
    },
    "required": ["bugs"],
    "additionalProperties": False
}

def build_diff_only_context(repo_path: str) -> Tuple[str, dict]:
    target_branch = f"origin/{os.environ.get('GITHUB_BASE_REF')}" if os.environ.get('GITHUB_BASE_REF') else 'HEAD~1'
    diff = subprocess.check_output(
        ["git", "-C", repo_path, "diff", "--unified=3", "--no-color", f"{target_branch}...HEAD"],
        text=True, encoding="utf-8"
    )
    metadata = {"impact_score": "LOW", "signature_changes": 0, "architecture_violations": 0, "lines_changed": 0}
    return f"# Code Review Context\n\n## Git Diff (What Changed)\n\n```diff\n{diff}\n```\n", metadata

def build_all_code_context(repo_path: str) -> Tuple[str, dict]:
    target_branch = f"origin/{os.environ.get('GITHUB_BASE_REF')}" if os.environ.get('GITHUB_BASE_REF') else 'HEAD~1'
    diff = subprocess.check_output(
        ["git", "-C", repo_path, "diff", "--unified=3", "--no-color", f"{target_branch}...HEAD"],
        text=True, encoding="utf-8"
    )
    repo = pathlib.Path(repo_path)
    py_files = list(repo.rglob("*.py"))
    excluded_dirs = {'.venv', 'venv', 'env', '.tox', 'site-packages', 'node_modules', '__pycache__', '.git'}
    py_files = [f for f in py_files if not any(part in f.parts for part in excluded_dirs)]
    
    context_parts = [
        "# Code Review Context\n",
        "## 1. Git Diff (What Changed)\n",
        f"```diff\n{diff}\n```\n",
        "## 2. Full Codebase\n",
    ]
    for py_file in sorted(py_files):
        try:
            content = py_file.read_text(encoding="utf-8")
            rel_path = py_file.relative_to(repo)
            context_parts.append(f"### File: {rel_path}\n```python\n{content}\n```\n")
        except Exception:
            pass
    metadata = {"impact_score": "LOW", "signature_changes": 0, "architecture_violations": 0, "lines_changed": 0}
    return "".join(context_parts), metadata

import hashlib

def compute_downstream_impact(caller_counts, changed_symbols, modified_public_apis, changed_signature_names):
    impact_analysis = []
    findings = []
    for sym, callers in caller_counts.items():
        score = 0
        for ref_f in callers:
            ref_f_norm = ref_f.replace("\\", "/")
            if 'api/' in ref_f_norm or 'routes/' in ref_f_norm or 'routers/' in ref_f_norm: score += 5
            elif 'hooks/' in ref_f_norm or 'shared/' in ref_f_norm: score += 4
            elif 'components/' in ref_f_norm or 'pages/' in ref_f_norm: score += 2
            else: score += 1
        
        is_public_api = False
        for (ch_f, ch_n, _, _) in changed_symbols:
            if ch_n == sym:
                ch_f_norm = ch_f.replace("\\", "/")
                if 'api/' in ch_f_norm or 'services/' in ch_f_norm or 'routers/' in ch_f_norm:
                    is_public_api = True
                    if ch_f_norm not in modified_public_apis: modified_public_apis.append(ch_f_norm)
        
        if is_public_api: score *= 2
        det = 'HIGH' if score > 10 else ('MEDIUM' if score > 3 else 'LOW')
        is_breaking = changed_signature_names.get(sym, True)
        breaking_str = "Breaking" if is_breaking else "Non-Breaking"
        impact_analysis.append(f"- Symbol '{sym}' (Score: {score}, Downstream Impact: {det}, References: {len(callers)}, {breaking_str} Signature)")
        
        short_hash = hashlib.md5(f"IMPACT-{sym}".encode()).hexdigest()[:8].upper()
        findings.append({
            "schemaVersion": 1,
            "id": f"IMP-{short_hash}",
            "type": "api_signature",
            "source": "impact",
            "severity": "HIGH",
            "attributes": {
                "changeType": "signature_modified",
                "compatibility": "breaking" if is_breaking else "backward_compatible",
                "affectedCallers": len(callers),
                "impactScore": score
            },
            "evidence": f"Signature of '{sym}' was changed ({breaking_str}). Downstream impact score: {score}."
        })
    return impact_analysis, findings

def run_static_analysis(f, lines, modified_public_apis):
    findings = []
    import hashlib
    f_norm = f.replace("\\", "/")
    if 'api/' in f_norm or 'services/' in f_norm or 'routers/' in f_norm:
        if f_norm not in modified_public_apis: modified_public_apis.append(f_norm)
        
    def add_primitive(node_lineno, prim_type, desc):
        raw_id = f"{f_norm}:{node_lineno}:{prim_type}"
        short_hash = hashlib.md5(raw_id.encode()).hexdigest()[:6].upper()
        sec_id = f"SEC-{short_hash}"
        findings.append({
            "schemaVersion": 1,
            "id": sec_id,
            "type": "security_sink",
            "source": "ast",
            "severity": "CRITICAL",
            "attributes": {
                "sink": prim_type,
                "sanitizerDetected": False,
                "reason": desc
            },
            "evidence": f"Dangerous sink '{prim_type}' detected: {desc} at line {node_lineno}."
        })
    
    try:
        src = pathlib.Path(f).read_text(encoding="utf-8")
        tree = ast.parse(src)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = getattr(node, 'lineno', -1)
                end = getattr(node, 'end_lineno', -1)
                if start != -1 and end != -1 and any(start <= l <= end for l in lines):
                    if (end - start) > 150:
                        raw_id = f"{f_norm}:{start}:large_function"
                        smell_id = f"SMELL-{hashlib.md5(raw_id.encode()).hexdigest()[:6].upper()}"
                        findings.append({
                            "schemaVersion": 1,
                            "id": smell_id,
                            "type": "code_smell",
                            "source": "ast",
                            "severity": "MEDIUM",
                            "attributes": {
                                "smellType": "large_function",
                                "lines": end - start,
                                "reason": f"Function exceeds 150 lines"
                            },
                            "evidence": f"Function '{node.name}' exceeds 150 lines ({end-start} lines) at line {start}."
                        })
                    
                    is_endpoint = False
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in ('get', 'post', 'put', 'delete', 'patch'):
                            is_endpoint = True
                            break
                    if is_endpoint:
                        has_auth = False
                        for arg in getattr(node.args, 'args', []) + getattr(node.args, 'kwonlyargs', []):
                            if arg.arg in VALID_AUTH_DEPENDENCIES: has_auth = True
                        for d in getattr(node.args, 'defaults', []) + getattr(node.args, 'kw_defaults', []):
                            if d and isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'Depends':
                                for a in d.args:
                                    if isinstance(a, ast.Name) and a.id in VALID_AUTH_DEPENDENCIES: has_auth = True
                        if not has_auth:
                            raw_id = f"{f_norm}:{start}:auth_missing"
                            arch_id = f"ARCH-{hashlib.md5(raw_id.encode()).hexdigest()[:6].upper()}"
                            findings.append({
                                "schemaVersion": 1,
                                "id": arch_id,
                                "type": "architecture",
                                "source": "ast",
                                "severity": "HIGH",
                                "attributes": {
                                    "reason": "Missing auth dependency"
                                },
                                "evidence": f"FastAPI endpoint '{node.name}' at line {start} is missing a valid auth dependency (e.g. Depends(get_current_user))."
                            })
                            
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
                is_sql_target = False
                if isinstance(node.func.value, ast.Name) and node.func.value.id in ('cursor', 'db', 'session', 'conn'):
                    is_sql_target = True
                elif isinstance(node.func.value, ast.Attribute) and node.func.value.attr in ('cursor', 'db', 'session', 'conn'):
                    is_sql_target = True
                
                if is_sql_target:
                    if hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                        add_primitive(node.lineno, "sql_execution", "Direct SQL execution (.execute()) detected")
                        
            # Shell execution sinks
            if isinstance(node, ast.Call):
                is_shell = False
                desc = ""
                # os.system
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'os' and node.func.attr == 'system':
                    is_shell, desc = True, "os.system() call detected"
                # subprocess.run/Popen with shell=True
                elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess' and node.func.attr in ('run', 'Popen', 'check_output', 'call'):
                    for kw in node.keywords:
                        if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            is_shell, desc = True, f"subprocess.{node.func.attr}(shell=True) detected"
                
                if is_shell and hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                    add_primitive(node.lineno, "shell_execution", desc)

                # Dynamic execution sinks
                if isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
                    if hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                        add_primitive(node.lineno, "dynamic_code_execution", f"{node.func.id}() call detected")
                        
                # Template injection sinks
                if isinstance(node.func, ast.Name) and node.func.id == 'render_template_string':
                    if hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                        add_primitive(node.lineno, "html_rendering", "render_template_string() call detected")
                    
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id.lower()
                        if any(x in name for x in ['secret', 'password', 'token', 'api_key']) or target.id.isupper():
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                val = node.value.value
                                if len(val) > 5 and 'ENV_' not in val and not val.startswith('os.getenv'):
                                    if hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                                        add_primitive(node.lineno, "hardcoded_secret", f"Potential hardcoded secret assigned to '{target.id}'")
                            elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'get':
                                if len(node.value.args) == 2 and isinstance(node.value.args[1], ast.Constant) and isinstance(node.value.args[1].value, str):
                                    if len(node.value.args[1].value) > 3:
                                        if hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                                            add_primitive(node.lineno, "hardcoded_secret", "Hardcoded fallback secret detected in os.getenv or environ.get")
                            elif isinstance(node.value, ast.BoolOp) and isinstance(node.value.op, ast.Or):
                                for val in node.value.values:
                                    if isinstance(val, ast.Constant) and isinstance(val.value, str) and len(val.value) > 3:
                                        if hasattr(node, 'lineno') and any(node.lineno <= l <= getattr(node, 'end_lineno', node.lineno) for l in lines):
                                            add_primitive(node.lineno, "hardcoded_secret", "Hardcoded fallback secret detected in OR expression")
    except Exception:
        pass
    
    return findings

import json
import os

def load_registry():
    # If a remote URL is provided (e.g. raw github gist URL), fetch it dynamically
    gist_url = os.environ.get("MODEL_REGISTRY_URL")
    if gist_url:
        try:
            import requests
            res = requests.get(gist_url, timeout=3)
            data = res.json()
            if data.get("MODEL_CAPABILITIES"):
                return data
        except Exception:
            pass
            
    # Fallback to local file
    try:
        registry_path = os.path.join(os.path.dirname(__file__), "model_registry.json")
        with open(registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("MODEL_CAPABILITIES"):
                return data
    except Exception:
        pass
        
    # Ultimate fail-safe
    return {
        "MODEL_CAPABILITIES": {
            "deepseek-reasoner": ["reasoning", "coding"],
            "gemini-2.5-pro": ["reasoning", "large_context"],
            "gpt-4o": ["reasoning", "coding", "large_context"],
            "deepseek-chat": ["balanced", "coding"],
            "gemini-3.5-flash": ["fast", "large_context"],
            "gpt-4o-mini": ["fast", "balanced"],
            "gemini-3.1-flash-lite": ["fast", "cost_efficient"]
        },
        "MODEL_SCORES": {
            "deepseek-reasoner": 10,
            "gemini-2.5-pro": 9,
            "gpt-4o": 8,
            "deepseek-chat": 8,
            "gemini-3.5-flash": 7,
            "gpt-4o-mini": 6,
            "gemini-3.1-flash-lite": 5
        },
        "TAG_WEIGHTS": {"reasoning": 5, "coding": 3, "large_context": 2, "balanced": 1, "fast": 1, "cost_efficient": 0}
    }

REGISTRY = load_registry()
MODEL_CAPABILITIES = {k: set(v) for k, v in REGISTRY.get("MODEL_CAPABILITIES", {}).items()}
MODEL_SCORES = REGISTRY.get("MODEL_SCORES", {})
TAG_WEIGHTS = REGISTRY.get("TAG_WEIGHTS", {})

def determine_models(metadata: dict) -> List[str]:
    required_tags = set()
    
    if metadata.get("signature_changes", 0) > 0:
        required_tags.add("reasoning")
        
    if metadata.get("impact_score") == "HIGH":
        required_tags.add("reasoning")
        
    if metadata.get("architecture_violations", 0) > 0:
        required_tags.add("coding")
        
    if metadata.get("lines_changed", 0) >= 300:
        required_tags.add("large_context")
        
    if not required_tags:
        required_tags.add("fast")
        
    def score_model(model_name: str) -> int:
        model_tags = MODEL_CAPABILITIES[model_name]
        matched_tags = required_tags.intersection(model_tags)
        tag_score = sum(TAG_WEIGHTS.get(tag, 0) for tag in matched_tags)
        inherent_score = MODEL_SCORES.get(model_name, 0)
        return tag_score + inherent_score
        
    sorted_models = sorted(MODEL_CAPABILITIES.keys(), key=score_model, reverse=True)
    return sorted_models

def get_provider_config(model: str) -> Tuple[str, List[str]]:
    if model.startswith("gemini"):
        keys_str = os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY") or ""
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        return "https://generativelanguage.googleapis.com/v1beta/openai/", keys
    elif model.startswith("deepseek"):
        key = os.environ.get("DEEPSEEK_API_KEY") or ""
        keys = [key.strip()] if key.strip() else []
        return "https://api.deepseek.com", keys
    elif model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        key = os.environ.get("OPENAI_API_KEY") or ""
        keys = [key.strip()] if key.strip() else []
        return None, keys
    return None, []

def _format_ast_findings(findings, impact_analysis, modified_public_apis):
    final_context = "# 2. AST Findings (Facts)\n"
    if not findings:
        final_context += "None.\n\n"
    else:
        final_context += "```json\n" + json.dumps(findings, indent=2) + "\n```\n\n"
        
    final_context += "# 3. Downstream Impact Analysis\n"
    if not impact_analysis:
        final_context += "No major downstream impacts detected.\n\n"
    else:
        final_context += "\n".join(impact_analysis) + "\n\n"
        
    final_context += "# 4. Modified Public APIs\n"
    if not modified_public_apis:
        final_context += "None.\n\n"
    else:
        for api in modified_public_apis:
            final_context += f"- {api}\n"
        final_context += "\n"
    return final_context

def extract_symbol_snippet(path: str, start: int, end: int) -> str:
    try:
        rows = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
        return "\n".join(rows[max(0, start-1):end])
    except Exception:
        return ""

def build_smart_context(repo_path: str) -> Tuple[str, dict]:
    from review_demo import (
        changed_lines,
        symbols_containing_lines,
        symbols_with_signature_changes,
        calls_in_lines,
        callgraph_for_files,
        one_hop_slice,
        snippet,
        group_consecutive_lines,
        format_context_as_markdown
    )
    
    original_dir = os.getcwd()
    os.chdir(repo_path)
    
    try:
        changes = changed_lines()
        exclude_patterns = get_exclude_patterns(repo_path)
        changes = {f: lines for f, lines in changes.items() if not is_excluded_file(f, repo_path, exclude_patterns)}
        changed_symbols = []
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists():
                for name, start, end in symbols_containing_lines(f, lines):
                    changed_symbols.append((f, name, start, end))

        all_py_files = pathlib.Path(".").rglob("*.py")
        repo_files = [str(p) for p in all_py_files
                      if not any(part in p.parts for part in ['.venv', 'venv', 'env', '.tox', 'site-packages', 'node_modules', '__pycache__'])]

        cg = callgraph_for_files(repo_files)
        impact_files = set(one_hop_slice(changed_symbols, cg))

        target_branch = f"origin/{os.environ.get('GITHUB_BASE_REF')}" if os.environ.get('GITHUB_BASE_REF') else 'HEAD~1'
        diff_text = subprocess.check_output(["git", "diff", "--unified=3", "--no-color", f"{target_branch}...HEAD"], text=True, encoding="utf-8")

        changed_snippets = []
        for f, lines in changes.items():
            if not lines: continue
            covered_lines = set()
            file_symbols = [sym for sym in changed_symbols if sym[0] == f]
            for _, sym_name, start, end in file_symbols:
                if end - start < 300:
                    text = extract_symbol_snippet(f, start, end)
                    if text:
                        changed_snippets.append({"file": f, "lines": f"{start}-{end} ({sym_name})", "text": text})
                        covered_lines.update(range(start, end + 1))
                        
            uncovered_lines = [l for l in lines if l not in covered_lines]
            for chunk in group_consecutive_lines(uncovered_lines):
                center = chunk[len(chunk) // 2]
                changed_snippets.append({"file": f, "lines": f"{chunk[0]}-{chunk[-1]}", "text": snippet(f, center, pad=8)})

        shown_lines = {}
        for item in changed_snippets:
            f = item["file"]
            if "-" in item["lines"]:
                lines_str = item["lines"].split(" ")[0]
                start, end = map(int, lines_str.split("-"))
                shown_lines.setdefault(f, set()).update(range(start, end + 1))

        calls_from_changed = set()
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists():
                calls_from_changed.update(calls_in_lines(f, lines))

        added_files_out = subprocess.check_output(["git", "diff", "--name-status", f"{target_branch}...HEAD"], text=True, encoding="utf-8")
        added_files = {line.split('\t')[1].strip() for line in added_files_out.splitlines() if line.startswith('A\t')}

        changed_signature_names = {}
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists() and f not in added_files:
                changed_signature_names.update(symbols_with_signature_changes(f, lines))

        impact_snippets = []
        caller_counts = {}
        for f in sorted(impact_files):
            try:
                src = pathlib.Path(f).read_text(encoding="utf-8")
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name in calls_from_changed:
                        init_line = node.lineno
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                                init_line = item.lineno
                                break
                        snippet_range = range(max(1, init_line - 12), init_line + 13)
                        if f in shown_lines and any(ln in shown_lines[f] for ln in snippet_range): continue
                        impact_snippets.append({"file": f, "symbol": node.name, "role": "callee", "text": snippet(f, init_line, pad=12)})
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in calls_from_changed:
                        snippet_range = range(max(1, node.lineno - 10), node.lineno + 11)
                        if f in shown_lines and any(ln in shown_lines[f] for ln in snippet_range): continue
                        impact_snippets.append({"file": f, "symbol": node.name, "role": "callee", "text": snippet(f, node.lineno, pad=10)})

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in changed_signature_names:
                        sym = node.func.id
                        if sym not in caller_counts: caller_counts[sym] = []
                        caller_counts[sym].append(f)
                        if hasattr(node, 'lineno'):
                            snippet_range = range(max(1, node.lineno - 8), node.lineno + 9)
                            if f in shown_lines and any(ln in shown_lines[f] for ln in snippet_range): continue
                            impact_snippets.append({"file": f, "symbol": f"call to {node.func.id}", "role": "caller", "text": snippet(f, node.lineno, pad=8)})
            except Exception:
                pass

        from reviewer.enrichment import enrich_evidence
        from reviewer.policy import evaluate_review_policy
        from reviewer.formatter import format_review_decisions
        
        findings = []
        modified_public_apis = []
        impact_analysis = []
        
        impact_analysis, impact_findings = compute_downstream_impact(caller_counts, changed_symbols, modified_public_apis, changed_signature_names)
        findings.extend(impact_findings)
        
        for f, lines in changes.items():
            if not f.endswith('.py') or not pathlib.Path(f).exists():
                continue
            fnd = run_static_analysis(f, lines, modified_public_apis)
            findings.extend(fnd)

        # Semantic Evidence Enrichment
        enriched_findings = enrich_evidence(findings)
        
        # Review Policy Engine
        decisions = evaluate_review_policy(enriched_findings)
        
        # Deterministic Formatter for CI (CLI Output)
        ci_output = format_review_decisions(decisions)
        
        has_blocking = any(d['priority'] == 'BLOCKING' for d in decisions)
        
        if has_blocking:
            print("##    BLOCKING REVIEW DECISIONS DETECTED\n\nThe PR has been automatically failed due to blocking violations:\n\n")
            print(ci_output)
            sys.exit(1)
            
        impact_score = "HIGH" if any(len(impact) > 0 for f, impact in caller_counts.items()) else "LOW"
        signature_changes = len(changed_signature_names)
        architecture_violations = sum(1 for d in decisions if d['category'] == 'Architecture')
        lines_changed = sum(len(lns) for lns in changes.values())
        
        metadata = {
            "impact_score": impact_score,
            "signature_changes": signature_changes,
            "architecture_violations": architecture_violations,
            "lines_changed": lines_changed,
            "ci_output": ci_output,
            "security_primitives": [f for f in enriched_findings if f["type"] == "security_sink"]
        }
        
        final_context = "# 1. Code Context (Source of Truth)\n"
        final_context += format_context_as_markdown(changes, changed_snippets, impact_snippets, diff_text) + "\n\n"
        
        final_context += _format_ast_findings(enriched_findings, impact_analysis, modified_public_apis)
            
        return final_context, metadata
    
    finally:
        os.chdir(original_dir)

def _get_review_prompt(context: str) -> str:
    return f"""You are a senior staff engineer performing a rigorous code review.

{context}

CRITICAL INSTRUCTIONS:
1. DO NOT verify AST findings. Assume AST findings are 100% correct. Your AST layer is deterministic. Spend your reasoning budget on consequences, not detection.
2. DO NOT provide generic testing advice (e.g., "comprehensive testing is essential").
3. DO NOT provide generic operational risk or maintenance warnings.
4. NEVER report a risk unless you can describe a specific execution path from changed code to failure.
5. Compilation and syntax validation are handled by the deterministic CI pipeline. Do not speculate about hypothetical Python compilation errors, missing imports, or type mismatches unless they are directly supported by compiler diagnostics, deterministic analysis, or the provided code diff. Focus your review on correctness, logic, architecture, security, maintainability, and behavioral changes.

You are reviewing ONLY the changes introduced by this PR.
Do NOT report:
- Existing technical debt
- Existing architectural issues
- Existing code smells
- Existing bugs unless this PR introduces or worsens them.

When the Git Diff and Changed Code snippets appear to differ in available context, treat the Changed Code snippets as the source of truth because they contain the complete AST symbol.

Before reporting a finding, verify ALL of the following:
✓ The changed code introduces the condition.
✓ The execution path reaches the condition.
✓ The failure is user-visible or CI-visible.
✓ The failure did not already exist before this PR.

If any check fails, return no finding (empty array).

Reject findings that are:
- Generic testing recommendations
- Generic maintainability concerns
- Generic operational concerns
- Speculative risks without a concrete failure path
- Signature Changes explicitly marked as (Non-Breaking)

Never report missing variables, unresolved symbols, or unreachable code unless the complete Changed Code snippet proves they are missing.

Optional parameters, default values, widened types, and backward-compatible overloads are NOT considered breaking signature changes. Only treat (Breaking) signature changes as a regression risk.

When reporting a valid finding, you MUST force blast-radius reasoning. Your `comment` MUST follow this structure:
Changed Symbol: [Symbol]
Affected Caller: [Caller]
Failure Mode: [Explanation of failure]
User Impact: [Explanation of impact]

If the bug_category is 'security', you MUST also provide:
- owasp_category: The specific OWASP Top 10 category (e.g., 'A01:2021-Broken Access Control')
- concrete_exploit_path: A step-by-step path an attacker would take from source to sink.
- confidence: A float between 0.0 and 1.0 indicating your certainty. Only use >= 0.95 if the exploit is mathematically proven in the changed code.
- ast_primitive_id: The ID of the AST security primitive (e.g. SEC-0A1B2C) if it matches one from the context. If it does not match an AST primitive, leave this empty.
(For non-security bugs, leave owasp_category, concrete_exploit_path, and ast_primitive_id empty, and set confidence to 1.0)

Rank findings using this Severity Formula (map to bug_category):
- critical: Signature change + downstream impact > 3
- high: Architectural violation
- medium: Core logic changed without tests
- low: Concrete maintainability concerns (must have failure path)"""

def run_review(context: str, mode_name: str, metadata: dict = None, verbose: bool = True) -> dict:
    if metadata is None:
        metadata = {"impact_score": "LOW", "signature_changes": 0, "architecture_violations": 0, "lines_changed": 0}
    prompt = _get_review_prompt(context)
    
    json_schema = BUG_REPORT_SCHEMA
    
    models_to_try = determine_models(metadata)
    print(f"DEBUG: determine_models returned {len(models_to_try)} models: {models_to_try}", file=sys.stderr)
    
    start_time = time.time()
    response = None
    last_error = None
    used_model = None
    
    for model in models_to_try:
        base_url, keys = get_provider_config(model)
        print(f"DEBUG: get_provider_config for '{model}' returned {len(keys)} keys.", file=sys.stderr)
        if not keys:
            print(f"[Warning] Skipping model {model}: No API key configured for this provider.", file=sys.stderr)
            continue
            
        for idx, key in enumerate(keys):
            # max_retries=0 is CRITICAL so the client doesn't internally sleep on 429s.
            # We want it to instantly throw so our loop can switch to the next API key.
            client_args = {"api_key": key, "max_retries": 0, "timeout": 120.0}
            if base_url:
                client_args["base_url"] = base_url
            
            # Print debug for client init
            print(f"DEBUG: Initializing OpenAI client for key index {idx}", file=sys.stderr)
            try:
                client = OpenAI(**client_args)
            except Exception as init_err:
                print(f"DEBUG: OpenAI client init failed! {init_err}", file=sys.stderr)
                continue
            
            try:
                print(f"Attempting AI Review using model {model} and API Key {idx + 1} of {len(keys)}...", file=sys.stderr)
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "bug_report",
                        "schema": json_schema
                    }
                }
                
                final_prompt = prompt
                if model.startswith("deepseek"):
                    response_format = {"type": "json_object"}
                    final_prompt += f"\n\nYou MUST return your response as a JSON object matching this exact schema:\n{json.dumps(json_schema)}"
                    
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": final_prompt}],
                    response_format=response_format
                )
                used_model = model
                break
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "429" in error_str or "503" in error_str or "Too Many Requests" in error_str:
                    print(f"[Warning] Model {model} with API Key {idx + 1} hit rate limit or server busy. Switching...", file=sys.stderr)
                    continue
                else:
                    print(f"[Error] Fatal API error with Key {idx + 1}: {error_str}", file=sys.stderr)
                    continue
        
        if response:
            break
                  
    if not response:
        print("Gemini API Error: Exhausted all available API keys or hit a fatal error.", file=sys.stderr)
        
        fallback_markdown = "##  AI Reviewer Unavailable\n\n"
        if last_error:
            fallback_markdown += f"**Error Details:** `{str(last_error)}`\n\n"
        fallback_markdown += "The AI code reviewer is currently unavailable or timed out. Below are the deterministic review decisions evaluated by the Policy Engine:\n\n"
        
        if metadata and "ci_output" in metadata:
            fallback_markdown += metadata["ci_output"]
        else:
            fallback_markdown += "No deterministic decisions generated."
            
        print(fallback_markdown)
        return {
            "mode": mode_name,
            "bugs": [],
            "bug_found": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "time_seconds": time.time() - start_time,
            "context_preview": ""
        }

    elapsed_time = time.time() - start_time
    output_text = response.choices[0].message.content
    
    # Clean markdown wrappers if present
    cleaned_text = output_text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
        
    try:
        data = json.loads(cleaned_text.strip())
    except json.JSONDecodeError as e:
        print(f"[Error] Failed to parse LLM JSON: {e}", file=sys.stderr)
        data = {"bugs": []}
    
    input_tokens = getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
    output_tokens = getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0
    
    result = {
        "mode": mode_name,
        "bugs": data.get("bugs", []),
        "bug_found": len(data.get("bugs", [])) > 0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "time_seconds": elapsed_time,
        "context_preview": context[:500] + "..." if len(context) > 500 else context
    }
    
    if verbose:
        print(f"Time taken: {elapsed_time:.2f} seconds", file=sys.stderr)
        print(f"Input tokens: {input_tokens}", file=sys.stderr)
        print(f"Output tokens: {output_tokens}", file=sys.stderr)
        print(f"Total tokens: {input_tokens + output_tokens}", file=sys.stderr)
        
        if data.get("bugs"):
            markdown = f"##  AI Code Review Findings (Model: `{used_model}`)\n\n"
            has_critical_security = False
            for bug in data.get("bugs", []):
                cat = bug.get('bug_category', 'issue').upper()
                markdown += f"###    [{cat}] {bug.get('summary')}\n"
                markdown += f"**File:** `{bug.get('changed_file')}` (Lines: {bug.get('changed_lines')})\n"
                if bug.get('confidence'):
                    markdown += f"**Confidence:** {bug.get('confidence')}\n"
                if cat == 'SECURITY' and bug.get('owasp_category'):
                    markdown += f"**OWASP:** {bug.get('owasp_category')}\n"
                markdown += f"\n{bug.get('comment')}\n\n"
                
                if cat == 'SECURITY' and bug.get('concrete_exploit_path'):
                    markdown += f"**Exploit Path:**\n{bug.get('concrete_exploit_path')}\n\n"
                    
                if cat == 'SECURITY' and bug.get('ast_primitive_id'):
                    markdown += f"**AST Primitive Match:** `{bug.get('ast_primitive_id')}`\n\n"
                    
                if bug.get('diff_fix_suggestion'):
                    markdown += f"**Suggested Fix:**\n```diff\n{bug.get('diff_fix_suggestion')}\n```\n\n"
                markdown += "---\n\n"
                
                # High-confidence OWASP Gate with AST Agreement
                ast_id = bug.get("ast_primitive_id")
                is_ast_verified = False
                if ast_id:
                    # Deterministically check if the ID the LLM provided actually exists
                    valid_primitives = metadata.get("security_primitives", [])
                    if any(p.get("id") == ast_id for p in valid_primitives):
                        is_ast_verified = True
                
                if (
                    cat == "SECURITY"
                    and bug.get("confidence", 0) >= 0.95
                    and bug.get("owasp_category")
                    and bug.get("concrete_exploit_path")
                    and is_ast_verified
                ):
                    has_critical_security = True
                    
            print(markdown)
            
            if has_critical_security:
                print("\n[!] FATAL: AI Reviewer detected a high-confidence OWASP violation that perfectly matches a deterministic AST sink. Blocking merge.", file=sys.stderr)
                sys.exit(1)
        else:
            print("##  AI Code Review\n\nNo significant risks or bugs found. LGTM! ")
    
    return result

def run_comparison(repo_path: str) -> None:
    print("\n" + "="*70)
    print("RUNNING COMPARISON: diff-only vs all-code vs smart")
    print("="*70)
    print(f"Repository: {repo_path}\n")
    
    results = []
    modes = [
        ("diff-only", build_diff_only_context),
        ("all-code", build_all_code_context),
        ("smart", build_smart_context),
    ]
    
    for mode_name, build_fn in modes:
        print(f"\nBuilding context for {mode_name}...")
        context, metadata = build_fn(repo_path)
        print(f"Running review ({mode_name})...")
        result = run_review(context, mode_name, metadata=metadata, verbose=False)
        results.append(result)
        print(f"  Done. Bugs found: {len(result['bugs'])}, Tokens: {result['input_tokens']:,}")
    
    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)
    print(f"\n{'Mode':<12} {'Bug Found?':<12} {'Input Tokens':<14} {'Time (s)':<10}")
    print("-" * 50)
    for r in results:
        bug_status = "Yes" if r["bug_found"] else "No"
        print(f"{r['mode']:<12} {bug_status:<12} {r['input_tokens']:<14,} {r['time_seconds']:<10.2f}")
    print("-" * 50)
    
    print("\nSUMMARY:")
    smart_result = next(r for r in results if r["mode"] == "smart")
    all_code_result = next(r for r in results if r["mode"] == "all-code")
    
    if smart_result["bug_found"] and all_code_result["input_tokens"] > 0:
        token_savings = ((all_code_result["input_tokens"] - smart_result["input_tokens"]) / all_code_result["input_tokens"] * 100)
        print(f"  - Smart mode uses {token_savings:.1f}% fewer tokens than all-code mode")
    
    diff_result = next(r for r in results if r["mode"] == "diff-only")
    if not diff_result["bug_found"] and smart_result["bug_found"]:
        print("  - diff-only mode MISSED the bug (lacks caller/callee context)")
        print("  - smart mode FOUND the bug (includes relevant context)")


def main():
    parser = argparse.ArgumentParser(
        description="Code Review Demo: Compare diff-only, all-code, and smart review approaches"
    )
    parser.add_argument("-r", "--repo", required=True, help="Path to the git repository to review")
    parser.add_argument("-m", "--mode", choices=["diff-only", "all-code", "smart"], help="Review mode to use")
    parser.add_argument("--compare", action="store_true", help="Run all three modes and compare results")
    args = parser.parse_args()
    
    repo_path = os.path.abspath(args.repo)
    if not os.path.isdir(repo_path) or not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"Error: Not a git repository: {repo_path}")
        sys.exit(1)
    
    if not args.mode and not args.compare:
        print("Error: Must specify either --mode or --compare")
        sys.exit(1)
    
    if args.compare:
        run_comparison(repo_path)
        return
    
    print(f"Building review context ({args.mode} mode)…", file=sys.stderr)
    if args.mode == "diff-only":
        context, metadata = build_diff_only_context(repo_path)
    elif args.mode == "all-code":
        context, metadata = build_all_code_context(repo_path)
    elif args.mode == "smart":
        context, metadata = build_smart_context(repo_path)
        
    print(f"Running review ({args.mode} mode)…", file=sys.stderr)
    run_review(context, args.mode, metadata=metadata)


if __name__ == "__main__":
    main()
    