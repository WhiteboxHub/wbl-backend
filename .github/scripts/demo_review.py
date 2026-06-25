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


VALID_AUTH_DEPENDENCIES = ['get_current_user', 'require_admin', 'require_staff']

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
                    "diff_fix_suggestion": {"type": "string"}
                },
                "required": ["changed_file", "changed_lines", "bug_category", "summary", "comment", "diff_fix_suggestion"],
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
        findings.append({"severity": "HIGH", "confidence": "HIGH", "type": "Signature Change", "evidence": f"Signature of '{sym}' was changed ({breaking_str}). Downstream impact score: {score}."})
    return impact_analysis, findings

def run_static_analysis(f, lines, modified_public_apis):
    findings = []
    critical = []
    f_norm = f.replace("\\", "/")
    if 'api/' in f_norm or 'services/' in f_norm or 'routers/' in f_norm:
        if f_norm not in modified_public_apis: modified_public_apis.append(f_norm)
    
    try:
        src = pathlib.Path(f).read_text(encoding="utf-8")
        tree = ast.parse(src)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = getattr(node, 'lineno', -1)
                end = getattr(node, 'end_lineno', -1)
                if start != -1 and end != -1 and any(start <= l <= end for l in lines):
                    if (end - start) > 150:
                        findings.append({"severity": "MEDIUM", "confidence": "HIGH", "type": "Code Smell", "evidence": f"Function '{node.name}' exceeds 150 lines ({end-start} lines) at line {start}."})
                    
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
                            findings.append({"severity": "HIGH", "confidence": "HIGH", "type": "Architectural Violation", "evidence": f"FastAPI endpoint '{node.name}' at line {start} is missing a valid auth dependency (e.g. Depends(get_current_user))."})
                            
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
                if hasattr(node, 'lineno') and any(node.lineno == l for l in lines):
                    critical.append(f"[{f}] Direct SQL execution (.execute()) detected at line {node.lineno}.")
                    
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id.lower()
                        if any(x in name for x in ['secret', 'password', 'token', 'api_key']) or target.id.isupper():
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                val = node.value.value
                                if len(val) > 5 and 'ENV_' not in val and not val.startswith('os.getenv'):
                                    if hasattr(node, 'lineno') and any(node.lineno == l for l in lines):
                                        critical.append(f"[{f}] Potential hardcoded secret assigned to '{target.id}' at line {node.lineno}.")
                            elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'get':
                                if len(node.value.args) == 2 and isinstance(node.value.args[1], ast.Constant) and isinstance(node.value.args[1].value, str):
                                    if len(node.value.args[1].value) > 3:
                                        if hasattr(node, 'lineno') and any(node.lineno == l for l in lines):
                                            critical.append(f"[{f}] Hardcoded fallback secret detected in os.getenv or environ.get at line {node.lineno}.")
                            elif isinstance(node.value, ast.BoolOp) and isinstance(node.value.op, ast.Or):
                                for val in node.value.values:
                                    if isinstance(val, ast.Constant) and isinstance(val.value, str) and len(val.value) > 3:
                                        if hasattr(node, 'lineno') and any(node.lineno == l for l in lines):
                                            critical.append(f"[{f}] Hardcoded fallback secret detected in OR expression at line {node.lineno}.")
    except Exception:
        pass
    
    return critical, findings

import json
import os

def load_registry():
    # If a remote URL is provided (e.g. raw github gist URL), fetch it dynamically
    gist_url = os.environ.get("MODEL_REGISTRY_URL")
    if gist_url:
        try:
            import requests
            res = requests.get(gist_url, timeout=3)
            return res.json()
        except Exception:
            pass
            
    # Fallback to local file
    try:
        registry_path = os.path.join(os.path.dirname(__file__), "model_registry.json")
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Ultimate fail-safe
        return {
            "MODEL_CAPABILITIES": {"gemini-3.5-flash": ["fast", "large_context"]},
            "MODEL_SCORES": {"gemini-3.5-flash": 7},
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
    elif model.startswith("gpt") or model.startswith("o1"):
        key = os.environ.get("OPENAI_API_KEY") or ""
        keys = [key.strip()] if key.strip() else []
        return None, keys
    return None, []

def _format_ast_findings(findings, impact_analysis, modified_public_apis):
    final_context = "# 1. AST Findings (Facts)\n"
    if not findings:
        final_context += "None.\n\n"
    else:
        for fnd in findings:
            final_context += f"- [Severity: {fnd['severity']}] [Confidence: {fnd['confidence']}] [Type: {fnd['type']}]\n  Evidence: {fnd['evidence']}\n"
        final_context += "\n"
        
    final_context += "# 2. Downstream Impact Analysis\n"
    if not impact_analysis:
        final_context += "No major downstream impacts detected.\n\n"
    else:
        final_context += "\n".join(impact_analysis) + "\n\n"
        
    final_context += "# 3. Modified Public APIs\n"
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

        critical = []
        findings = []
        modified_public_apis = []
        impact_analysis = []
        
        impact_analysis, impact_findings = compute_downstream_impact(caller_counts, changed_symbols, modified_public_apis, changed_signature_names)
        findings.extend(impact_findings)
        
        for f, lines in changes.items():
            if not f.endswith('.py') or not pathlib.Path(f).exists():
                continue
            c, fnd = run_static_analysis(f, lines, modified_public_apis)
            critical.extend(c)
            findings.extend(fnd)

        if critical:
            critical_markdown = "##    CRITICAL AST VIOLATIONS\n\nThe PR has been automatically failed due to critical structural or security violations:\n\n"
            for c in critical:
                critical_markdown += f"- **{c}**\n"
            print(critical_markdown)
            sys.exit(1)
            
        impact_score = "HIGH" if any(len(impact) > 0 for f, impact in caller_counts.items()) else "LOW"
        signature_changes = len(changed_signature_names)
        architecture_violations = 1 if len(critical) > 0 else 0
        lines_changed = sum(len(lns) for lns in changes.values())
        
        metadata = {
            "impact_score": impact_score,
            "signature_changes": signature_changes,
            "architecture_violations": architecture_violations,
            "lines_changed": lines_changed
        }
        
        final_context = _format_ast_findings(findings, impact_analysis, modified_public_apis)
        final_context += "# 5. Code Context\n"
        final_context += format_context_as_markdown(changes, changed_snippets, impact_snippets, diff_text)
            
        return final_context, metadata
    
    finally:
        os.chdir(original_dir)

def run_review(context: str, mode_name: str, metadata: dict = None, verbose: bool = True) -> dict:
    if metadata is None:
        metadata = {"impact_score": "LOW", "signature_changes": 0, "architecture_violations": 0, "lines_changed": 0}
    prompt = f"""You are a senior staff engineer performing a rigorous code review.

{context}

CRITICAL INSTRUCTIONS:
1. DO NOT verify AST findings. Assume AST findings are 100% correct. Your AST layer is deterministic. Spend your reasoning budget on consequences, not detection.
2. DO NOT provide generic testing advice (e.g., "comprehensive testing is essential").
3. DO NOT provide generic operational risk or maintenance warnings.
4. NEVER report a risk unless you can describe a specific execution path from changed code to failure.

A finding is VALID ONLY IF:
1. A specific changed symbol is involved.
2. A concrete regression path exists.
3. A user-visible failure mode can be explained.
4. The impact is supported by AST findings.

Reject findings that are:
- Generic testing recommendations
- Generic maintainability concerns
- Generic operational concerns
- Speculative risks without a concrete failure path
- Signature Changes explicitly marked as (Non-Breaking)

Optional parameters, default values, widened types, and backward-compatible overloads are NOT considered breaking signature changes. Only treat (Breaking) signature changes as a regression risk.

If you cannot identify a concrete failure path, return no finding (empty array).

When reporting a valid finding, you MUST force blast-radius reasoning. Your `comment` MUST follow this structure:
Changed Symbol: [Symbol]
Affected Caller: [Caller]
Failure Mode: [Explanation of failure]
User Impact: [Explanation of impact]

Rank findings using this Severity Formula (map to bug_category):
- critical: Signature change + downstream impact > 3
- high: Architectural violation
- medium: Core logic changed without tests
- low: Concrete maintainability concerns (must have failure path)"""
    
    json_schema = BUG_REPORT_SCHEMA
    
    models_to_try = determine_models(metadata)
    
    start_time = time.time()
    response = None
    last_error = None
    used_model = None
    
    for model in models_to_try:
        base_url, keys = get_provider_config(model)
        if not keys:
            print(f"[Warning] Skipping model {model}: No API key configured for this provider.", file=sys.stderr)
            continue
            
        for idx, key in enumerate(keys):
            client_args = {"api_key": key, "max_retries": 1, "timeout": 180.0}
            if base_url:
                client_args["base_url"] = base_url
            client = OpenAI(**client_args)
            
            try:
                print(f"Attempting AI Review using model {model} and API Key {idx + 1} of {len(keys)}...", file=sys.stderr)
                response = client.chat.completions.create(
                    model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "bug_report",
                        "schema": json_schema
                    }
                }
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
        fallback_markdown += "The AI code reviewer is currently unavailable or timed out. Below are the deterministic AST findings and downstream impact analysis gathered by the engine:\n\n"
        
        if "##    CRITICAL AST VIOLATIONS" in context or "1. AST Findings (Facts)" in context:
            fallback_markdown += "###  AST Engine Output\n\n"
            fallback_markdown += context.split("# 5. Code Context")[0].strip()
        else:
            fallback_markdown += "No structural violations detected by the AST engine."
            
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
    data = json.loads(output_text)
    
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
            for bug in data.get("bugs", []):
                cat = bug.get('bug_category', 'issue').upper()
                markdown += f"###    [{cat}] {bug.get('summary')}\n"
                markdown += f"**File:** `{bug.get('changed_file')}` (Lines: {bug.get('changed_lines')})\n\n"
                markdown += f"{bug.get('comment')}\n\n"
                if bug.get('diff_fix_suggestion'):
                    markdown += f"**Suggested Fix:**\n```diff\n{bug.get('diff_fix_suggestion')}\n```\n\n"
                markdown += "---\n\n"
            print(markdown)
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
