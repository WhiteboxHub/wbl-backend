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
import getpass
from typing import Dict, Set, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()


# =============================================================================
# Context Building Functions
# =============================================================================

def build_diff_only_context(repo_path: str) -> str:
    """Mode 1: Only the git diff - no additional context."""
    diff = subprocess.check_output(
        ["git", "-C", repo_path, "diff", "--unified=3", "--no-color", "HEAD~1"],
        text=True
    )
    
    context = f"""# Code Review Context

## Git Diff (What Changed)

```diff
{diff}
```

Please review this diff and identify any bugs.
"""
    return context


def build_all_code_context(repo_path: str) -> str:
    """Mode 2: Include all Python files in the repository."""
    diff = subprocess.check_output(
        ["git", "-C", repo_path, "diff", "--unified=3", "--no-color", "HEAD~1"],
        text=True
    )
    
    # Find all Python files
    repo = pathlib.Path(repo_path)
    py_files = list(repo.rglob("*.py"))
    
    # Filter out common non-essential directories
    excluded_dirs = {'.venv', 'venv', 'env', '.tox', 'site-packages', 
                     'node_modules', '__pycache__', '.git'}
    py_files = [f for f in py_files 
                if not any(part in f.parts for part in excluded_dirs)]
    
    # Build context with all file contents
    context_parts = [
        "# Code Review Context\n",
        "## 1. Git Diff (What Changed)\n",
        "```diff",
        diff,
        "```\n",
        "## 2. Full Codebase\n",
        "Below are all Python files in the repository:\n"
    ]
    
    for py_file in sorted(py_files):
        try:
            content = py_file.read_text(encoding="utf-8")
            rel_path = py_file.relative_to(repo)
            context_parts.append(f"### File: {rel_path}\n")
            context_parts.append("```python")
            context_parts.append(content)
            context_parts.append("```\n")
        except Exception:
            pass
    
    context_parts.append("\nPlease review the diff and identify any bugs, using the full codebase for context.")
    
    return "\n".join(context_parts)


def build_smart_context(repo_path: str) -> str:
    """Mode 3: Smart impact slicing - diff + callers/callees only."""
    # Import functions from review_demo.py
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
    
    # Save current directory and change to repo
    original_dir = os.getcwd()
    os.chdir(repo_path)
    
    try:
        changes = changed_lines()
        changed_symbols = []
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists():
                for name, start, end in symbols_containing_lines(f, lines):
                    changed_symbols.append((f, name, start, end))

        # Get all Python files
        all_py_files = pathlib.Path(".").rglob("*.py")
        repo_files = [str(p) for p in all_py_files
                      if not any(part in p.parts for part in
                                 ['.venv', 'venv', 'env', '.tox', 'site-packages', 
                                  'node_modules', '__pycache__'])]

        cg = callgraph_for_files(repo_files)
        impact_files = set(one_hop_slice(changed_symbols, cg))

        # Full git diff
        diff_text = subprocess.check_output(
            ["git", "diff", "--unified=3", "--no-color", "HEAD~1"],
            text=True
        )

        # Snippets of changed code
        changed_snippets = []
        for f, lines in changes.items():
            if not lines:
                continue
            for chunk in group_consecutive_lines(list(lines)):
                center = chunk[len(chunk) // 2]
                changed_snippets.append({
                    "file": f,
                    "lines": f"{chunk[0]}-{chunk[-1]}",
                    "text": snippet(f, center, pad=8)
                })

        # Track shown lines
        shown_lines = {}
        for item in changed_snippets:
            f = item["file"]
            if "-" in item["lines"]:
                start, end = map(int, item["lines"].split("-"))
                shown_lines.setdefault(f, set()).update(range(start, end + 1))

        # Get calls from changed lines
        calls_from_changed = set()
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists():
                calls_from_changed.update(calls_in_lines(f, lines))

        # Get signature changes
        changed_signature_names = set()
        for f, lines in changes.items():
            if f.endswith(".py") and pathlib.Path(f).exists():
                changed_signature_names.update(symbols_with_signature_changes(f, lines))

        # Build impact snippets
        impact_snippets = []
        for f in sorted(impact_files):
            try:
                src = pathlib.Path(f).read_text(encoding="utf-8")
                tree = ast.parse(src)

                # CALLEES
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name in calls_from_changed:
                        init_line = node.lineno
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                                init_line = item.lineno
                                break
                        snippet_range = range(max(1, init_line - 12), init_line + 13)
                        if f in shown_lines and any(ln in shown_lines[f] for ln in snippet_range):
                            continue
                        impact_snippets.append({
                            "file": f,
                            "symbol": node.name,
                            "role": "callee",
                            "text": snippet(f, init_line, pad=12)
                        })
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in calls_from_changed:
                        snippet_range = range(max(1, node.lineno - 10), node.lineno + 11)
                        if f in shown_lines and any(ln in shown_lines[f] for ln in snippet_range):
                            continue
                        impact_snippets.append({
                            "file": f,
                            "symbol": node.name,
                            "role": "callee",
                            "text": snippet(f, node.lineno, pad=10)
                        })

                # CALLERS
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in changed_signature_names:
                            if hasattr(node, 'lineno'):
                                snippet_range = range(max(1, node.lineno - 8), node.lineno + 9)
                                if f in shown_lines and any(ln in shown_lines[f] for ln in snippet_range):
                                    continue
                                impact_snippets.append({
                                    "file": f,
                                    "symbol": f"call to {node.func.id}",
                                    "role": "caller",
                                    "text": snippet(f, node.lineno, pad=8)
                                })
            except Exception:
                pass

        return format_context_as_markdown(changes, changed_snippets, impact_snippets, diff_text)
    
    finally:
        os.chdir(original_dir)


# =============================================================================
# LLM Review Function
# =============================================================================

def run_review(context: str, mode_name: str, verbose: bool = True) -> dict:
    """Send context to LLM and return results with statistics."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        sys.exit(1)
    
    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    
    prompt = (
        "You are a senior code reviewer analyzing a PR for bugs. "
        "Review the provided context and find real bugs.\n\n"
        "Look for:\n"
        "- CONTRACT MISMATCHES: Wrong number of parameters, missing arguments, signature changes where callers weren't updated\n"
        "- LOGIC ERRORS: Off-by-one errors, incorrect conditionals, wrong operators\n"
        "- ERROR HANDLING: Unhandled exceptions, incorrect error propagation\n\n"
        "Focus on real bugs, not style issues. If no bugs found, return empty bugs array.\n\n"
        + context
    )
    
    json_schema = {
        "type": "object",
        "properties": {
            "bugs": {
                "type": "array",
                "description": "Array of bug findings. Empty array if no bugs found.",
                "items": {
                    "type": "object",
                    "properties": {
                        "changed_file": {
                            "type": "string",
                            "description": "Path to the file where the bug exists"
                        },
                        "changed_lines": {
                            "type": "string",
                            "description": "Line number or range (e.g., '55' or '55-57')"
                        },
                        "bug_category": {
                            "type": "string",
                            "description": "Category of the bug",
                            "enum": ["contract-mismatch", "logic-error", "concurrency", "resource-management", "error-handling", "security"]
                        },
                        "summary": {
                            "type": "string",
                            "description": "One sentence describing the bug"
                        },
                        "comment": {
                            "type": "string",
                            "description": "Detailed explanation with evidence from the code"
                        },
                        "diff_fix_suggestion": {
                            "type": "string",
                            "description": "Unified diff format showing the fix, or empty string if no fix available"
                        }
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
    
    # Extract output
    output_text = response.choices[0].message.content
    
    data = json.loads(output_text)
    
    # Get token usage
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
        # Print full JSON output like original format
        print(json.dumps(data, indent=2))
        
        # Print statistics
        print("\n" + "="*80)
        print("STATISTICS")
        print("="*80)
        print(f"Time taken: {elapsed_time:.2f} seconds")
        print(f"Input tokens: {input_tokens}")
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {input_tokens + output_tokens}")
    
    return result


def run_comparison(repo_path: str) -> None:
    """Run all three modes and display comparison table."""
    print("\n" + "="*70)
    print("RUNNING COMPARISON: diff-only vs all-code vs smart")
    print("="*70)
    print(f"Repository: {repo_path}\n")
    
    results = []
    
    # Run each mode
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
    
    # Display comparison table
    print("\n" + "="*70)
    print("COMPARISON RESULTS")
    print("="*70)
    
    # Table header
    print(f"\n{'Mode':<12} {'Bug Found?':<12} {'Input Tokens':<14} {'Time (s)':<10}")
    print("-" * 50)
    
    for r in results:
        bug_status = "Yes" if r["bug_found"] else "No"
        print(f"{r['mode']:<12} {bug_status:<12} {r['input_tokens']:<14,} {r['time_seconds']:<10.2f}")
    
    print("-" * 50)
    
    # Summary
    print("\nSUMMARY:")
    smart_result = next(r for r in results if r["mode"] == "smart")
    all_code_result = next(r for r in results if r["mode"] == "all-code")
    
    if smart_result["bug_found"] and all_code_result["input_tokens"] > 0:
        token_savings = ((all_code_result["input_tokens"] - smart_result["input_tokens"]) 
                        / all_code_result["input_tokens"] * 100)
        print(f"  - Smart mode uses {token_savings:.1f}% fewer tokens than all-code mode")
    
    diff_result = next(r for r in results if r["mode"] == "diff-only")
    if not diff_result["bug_found"] and smart_result["bug_found"]:
        print("  - diff-only mode MISSED the bug (lacks caller/callee context)")
        print("  - smart mode FOUND the bug (includes relevant context)")


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Code Review Demo: Compare diff-only, all-code, and smart review approaches",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_review.py -r ./my-repo -m diff-only
  python demo_review.py -r ./my-repo -m all-code
  python demo_review.py -r ./my-repo -m smart
  python demo_review.py -r ./my-repo --compare
        """
    )
    
    parser.add_argument(
        "-r", "--repo",
        required=True,
        help="Path to the git repository to review"
    )
    
    parser.add_argument(
        "-m", "--mode",
        choices=["diff-only", "all-code", "smart"],
        help="Review mode to use"
    )
    
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run all three modes and compare results"
    )
    
    args = parser.parse_args()
    
    # Validate repo path
    repo_path = os.path.abspath(args.repo)
    if not os.path.isdir(repo_path):
        print(f"Error: Repository path does not exist: {repo_path}")
        sys.exit(1)
    
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"Error: Not a git repository: {repo_path}")
        sys.exit(1)
    
    # Must specify either --mode or --compare
    if not args.mode and not args.compare:
        print("Error: Must specify either --mode or --compare")
        parser.print_help()
        sys.exit(1)
    
    # Run comparison mode
    if args.compare:
        run_comparison(repo_path)
        return
    
    # Run single mode
    print(f"Building review context ({args.mode} mode)…")
    
    # Build context based on mode
    if args.mode == "diff-only":
        context = build_diff_only_context(repo_path)
    elif args.mode == "all-code":
        context = build_all_code_context(repo_path)
    elif args.mode == "smart":
        context = build_smart_context(repo_path)
    
    # Always print context for single mode (like original format)
    print(context)
    
    print("\n" + "="*80)
    print("Calling the model…")
    print("="*80 + "\n")
    
    # Run review
    run_review(context, args.mode)


if __name__ == "__main__":
    main()
