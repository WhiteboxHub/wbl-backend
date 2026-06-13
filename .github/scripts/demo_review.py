# demo_review.py
# CLI tool to demonstrate three code review approaches:
# 1. diff-only: Just the git diff (LLM likely misses bugs)
# 2. all-code: Entire codebase (finds bugs but uses many tokens)
# 3. smart: Impact slicing (finds bugs with minimal tokens)

import os
import sys
import json
import time
import pathlib
import subprocess
import ast
import argparse
from typing import Dict, Set, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()


VALID_AUTH_DEPENDENCIES = ['get_current_user', 'require_admin', 'require_staff']

def build_diff_only_context(repo_path: str) -> str:
    target_branch = f"origin/{os.environ.get('GITHUB_BASE_REF')}" if os.environ.get('GITHUB_BASE_REF') else 'HEAD~1'
    diff = subprocess.check_output(
        ["git", "-C", repo_path, "diff", "--unified=3", "--no-color", f"{target_branch}...HEAD"],
        text=True
    )
    return f"# Code Review Context\n\n## Git Diff (What Changed)\n\n```diff\n{diff}\n```\n"

def build_all_code_context(repo_path: str) -> str:
    target_branch = f"origin/{os.environ.get('GITHUB_BASE_REF')}" if os.environ.get('GITHUB_BASE_REF') else 'HEAD~1'
    diff = subprocess.check_output(
        ["git", "-C", repo_path, "diff", "--unified=3", "--no-color", f"{target_branch}...HEAD"],
        text=True
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
    return "".join(context_parts)

def compute_downstream_impact(caller_counts, changed_symbols, modified_public_apis):
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
        impact_analysis.append(f"- Symbol '{sym}' (Score: {score}, Downstream Impact: {det}, References: {len(callers)})")
        findings.append({"severity": "HIGH", "confidence": "HIGH", "type": "Signature Change", "evidence": f"Signature of '{sym}' was changed. Downstream impact score: {score}."})
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
def build_smart_context(repo_path: str) -> str:
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
        diff_text = subprocess.check_output(["git", "diff", "--unified=3", "--no-color", f"{target_branch}...HEAD"], text=True)

        changed_snippets = []
        for f, lines in changes.items():
            if not lines: continue
            for chunk in group_consecutive_lines(list(lines)):
                center = chunk[len(chunk) // 2]
                changed_snippets.append({"file": f, "lines": f"{chunk[0]}-{chunk[-1]}", "text": snippet(f, center, pad=8)})

        shown_lines = {}
        for item in changed_snippets:
            f = item["file"]
            if "-" in item["lines"]:
                start, end = map(int, item["lines"].split("-"))
                shown_lines.setdefault(f, set()).update(range(start, end + 1))

        calls_from_changed = set()
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists():
                calls_from_changed.update(calls_in_lines(f, lines))

        target_branch = f"origin/{os.environ.get('GITHUB_BASE_REF')}" if os.environ.get('GITHUB_BASE_REF') else 'HEAD~1'
        
        # Identify newly added files so we don't flag them for "Signature Changes"
        added_files_out = subprocess.check_output(["git", "diff", "--name-status", f"{target_branch}...HEAD"], text=True)
        added_files = {line.split('\t')[1].strip() for line in added_files_out.splitlines() if line.startswith('A\t')}

        changed_signature_names = set()
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists() and f not in added_files:
                changed_signature_names.update(symbols_with_signature_changes(f, lines))

        impact_snippets = []
        caller_counts = {}
        for f in sorted(impact_files):
            try:
                src = pathlib.Path(f).read_text(encoding="utf-8")
                tree = ast.parse(src)
                
                # Callees
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

                # Callers
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

        # --- Stage 1: AST Rules Engine ---
        critical = []
        findings = []
        modified_public_apis = []
        impact_analysis = []
        
        impact_analysis, impact_findings = compute_downstream_impact(caller_counts, changed_symbols, modified_public_apis)
        findings.extend(impact_findings)
        
        # Standard Rules
        for f, lines in changes.items():
            if not f.endswith('.py') or not pathlib.Path(f).exists():
                continue
            
            c, fnd = run_static_analysis(f, lines, modified_public_apis)
            critical.extend(c)
            findings.extend(fnd)

        if critical:
            print("❌ CRITICAL AST FINDINGS DETECTED - FAILING PR IMMEDIATELY", file=sys.stderr)
            critical_markdown = "## 🚨 CRITICAL AST VIOLATIONS\n\nThe PR has been automatically failed due to critical structural or security violations:\n\n"
            for c in critical:
                print(f" - {c}", file=sys.stderr)
                critical_markdown += f"- **{c}**\n"
            print(critical_markdown)
            sys.exit(1)
            
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
            
        final_context += "# 5. Code Context\n"
        final_context += format_context_as_markdown(changes, changed_snippets, impact_snippets, diff_text)
            
        return final_context
    
    finally:
        os.chdir(original_dir)


def run_review(context: str, mode_name: str, verbose: bool = True) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        sys.exit(1)
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    
    prompt = f"""You are a senior code reviewer analyzing a PR.

{context}

INSTRUCTIONS:
Do not verify AST findings. Assume AST findings are correct.
Focus only on:
- business impact
- operational risk
- regression risk
- migration concerns
- testing recommendations

When reviewing, pay special attention to functions with HIGH Downstream Impact or Modified Public APIs.

If no bugs found, return empty bugs array."""
    
    json_schema = {
        "type": "object",
        "properties": {
            "bugs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "changed_file": {"type": "string"},
                        "changed_lines": {"type": "string"},
                        "bug_category": {"type": "string", "enum": ["contract-mismatch", "logic-error", "concurrency", "resource-management", "error-handling", "security"]},
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
    
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model="gemini-3.5-flash",
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "bug_report",
                    "schema": json_schema,
                    "strict": True
                }
            }
        )
        
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
                markdown = "## 🤖 AI Code Review Findings\n\n"
                for bug in data.bugs:
                    cat = bug.get('bug_category', 'issue').upper()
                    markdown += f"### 🚨 [{cat}] {bug.get('summary')}\n"
                    markdown += f"**File:** `{bug.get('changed_file')}` (Lines: {bug.get('changed_lines')})\n\n"
                    markdown += f"{bug.get('comment')}\n\n"
                    if bug.get('diff_fix_suggestion'):
                        markdown += f"**Suggested Fix:**\n```diff\n{bug.get('diff_fix_suggestion')}\n```\n\n"
                    markdown += "---\n\n"
                print(markdown)
            else:
                print("## 🤖 AI Code Review\n\nNo significant risks or bugs found. LGTM! ✅")
        
        return result
    except Exception as e:
        print(f"Gemini API Error: {str(e)}", file=sys.stderr)
        
        fallback_markdown = "## ⚠️ AI Reviewer Unavailable\n\n"
        fallback_markdown += "The AI code reviewer is currently unavailable or timed out. Below are the deterministic AST findings and downstream impact analysis gathered by the engine:\n\n"
        
        # Extract findings from the context string that was built by the AST engine
        if "## 🚨 CRITICAL AST VIOLATIONS" in context or "1. AST Findings (Facts)" in context:
            fallback_markdown += "### 🔍 AST Engine Output\n\n"
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
        context = build_fn(repo_path)
        print(f"Running review ({mode_name})...")
        result = run_review(context, mode_name, verbose=False)
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
        context = build_diff_only_context(repo_path)
    elif args.mode == "all-code":
        context = build_all_code_context(repo_path)
    elif args.mode == "smart":
        context = build_smart_context(repo_path)
    
    print("\n" + "="*80, file=sys.stderr)
    print("Calling the model…", file=sys.stderr)
    print("="*80 + "\n", file=sys.stderr)
    run_review(context, args.mode)


if __name__ == "__main__":
    main()
