# review_demo.py
# Outside-Diff Impact Slicing: Find bugs by analyzing callers/callees around the diff.

import os, json, pathlib, subprocess, ast, getpass
from typing import Dict, Set, List, Tuple
from openai.types.responses import ResponseOutputMessage, ResponseOutputText

def changed_lines(repo=".") -> Dict[str, Set[int]]:
    """Extract changed line numbers from git diff."""
    diff = subprocess.check_output(
        ["git", "-C", repo, "diff", "--unified=0", "--no-color", "HEAD~1"]
    ).decode()
    current = None
    changes: Dict[str, Set[int]] = {}
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@") and current:
            parts = [p for p in line.split() if p.startswith("+")]
            if not parts:
                continue
            hunk = parts[0]
            start = int(hunk.split(",")[0][1:])
            count = int(hunk.split(",")[1]) if "," in hunk else 1
            changes.setdefault(current, set()).update(range(start, start + count))
    return changes

def symbols_containing_lines(path: str, lines: Set[int]) -> List[Tuple[str,int,int]]:
    """Find functions/classes that contain the given line numbers."""
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start, end = node.lineno, getattr(node, "end_lineno", node.lineno)
            if any(start <= ln <= end for ln in lines):
                out.append((node.name, start, end))
    return out

def symbols_with_signature_changes(path: str, lines: Set[int]) -> Set[str]:
    """Find functions/classes whose SIGNATURES were changed (def line itself changed)."""
    src = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    changed_signatures = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Check if the definition line itself was changed
            if node.lineno in lines:
                changed_signatures.add(node.name)
            # For classes, also check if __init__ signature changed
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                        if item.lineno in lines:
                            changed_signatures.add(node.name)
    return changed_signatures

def calls_in_lines(path: str, lines: Set[int]) -> Set[str]:
    """Extract function/class calls that occur within the specified line numbers."""
    src = pathlib.Path(path).read_text(encoding="utf-8")
    source_lines = src.splitlines()
    tree = ast.parse(src)

    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            # Check if this call is within the changed lines
            if hasattr(node, 'lineno') and node.lineno in lines:
                calls.add(node.func.id)
    return calls

def callgraph_for_files(files: List[str]) -> dict:
    """Build a simple call graph: which files define/call which symbols."""
    graph = {"calls": {}, "defs": {}}
    for f in files:
        try:
            src = pathlib.Path(f).read_text(encoding="utf-8")
            tree = ast.parse(src)
            defs = {n.name for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            calls = {n.func.id for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            graph["defs"][f] = sorted(defs)
            graph["calls"][f] = sorted(calls)
        except Exception:
            pass
    return graph

def one_hop_slice(changed_symbols: List[Tuple[str,str,int,int]], cg: dict) -> List[str]:
    """Find files that call or are called by the changed symbols."""
    target_names = {name for _, name, _, _ in changed_symbols}
    changed_files = {f for f, _, _, _ in changed_symbols}
    slice_files = set()

    # Callers: files that call the changed symbols
    for f, calls in cg["calls"].items():
        if f not in changed_files and any(t in calls for t in target_names):
            slice_files.add(f)

    # Callees: files defining what the changed files call
    calls_from_changed = set()
    for f in changed_files:
        calls_from_changed.update(cg["calls"].get(f, []))

    for f, defs in cg["defs"].items():
        if any(call in defs for call in calls_from_changed):
            slice_files.add(f)

    return sorted(slice_files)

def snippet(path: str, line: int, pad: int = 5) -> str:
    """Extract code snippet around a line number."""
    try:
        rows = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
        i, j = max(0, line - pad - 1), min(len(rows), line + pad)
        return "\n".join(f"{k+1:>4}  {rows[k]}" for k in range(i, j))
    except Exception:
        return ""

def group_consecutive_lines(lines: List[int], gap: int = 5) -> List[List[int]]:
    """Group consecutive lines into chunks (within 'gap' lines of each other)."""
    if not lines:
        return []
    sorted_lines = sorted(lines)
    chunks = [[sorted_lines[0]]]
    for ln in sorted_lines[1:]:
        if ln - chunks[-1][-1] <= gap:
            chunks[-1].append(ln)
        else:
            chunks.append([ln])
    return chunks

def format_context_as_markdown(changes, changed_snippets, impact_snippets, diff_text) -> str:
    """Format the review context as structured markdown with XML-style tags."""
    lines = ["# Code Review Context\n"]

    # Section 1: Git Diff
    lines.append("## 1. Git Diff (What Changed)\n")
    lines.append("<diff>")
    lines.append(diff_text)
    lines.append("</diff>\n")

    # Section 2: Changed Code Snippets
    lines.append("## 2. Changed Code (Modified Files with Context)\n")
    for item in changed_snippets:
        lines.append(f'<file name="{item["file"]}" lines="{item["lines"]}" type="changed">')
        lines.append("```python")
        lines.append(item["text"])
        lines.append("```")
        lines.append("</file>\n")

    # Section 3: Impact Code (both directions)
    lines.append("## 3. Impact Code (Contracts & Call Sites)\n")

    # Separate callees and callers
    callees = [item for item in impact_snippets if item.get("role") == "callee"]
    callers = [item for item in impact_snippets if item.get("role") == "caller"]

    # CALLEES section
    lines.append("### CALLEES: Definitions that the changed code CALLS (check if changed code respects these contracts)")
    lines.append("<callees>")
    if callees:
        for item in callees:
            lines.append(f'<file name="{item["file"]}" symbol="{item["symbol"]}">')
            lines.append("```python")
            lines.append(item["text"])
            lines.append("```")
            lines.append("</file>")
    else:
        lines.append("None")
    lines.append("</callees>\n")

    # CALLERS section
    lines.append("### CALLERS: Call sites that invoke the changed functions/classes (check if callers pass correct arguments)")
    lines.append("<callers>")
    if callers:
        for item in callers:
            lines.append(f'<file name="{item["file"]}" symbol="{item["symbol"]}">')
            lines.append("```python")
            lines.append(item["text"])
            lines.append("```")
            lines.append("</file>")
    else:
        lines.append("None")
    lines.append("</callers>\n")

    return "\n".join(lines)

def build_review_context() -> str:
    """Build the context packet for LLM review."""
    changes = changed_lines()
    changed_symbols = []
    for f, lines in changes.items():
        if f.endswith(".py") and pathlib.Path(f).exists():
            for name, start, end in symbols_containing_lines(f, lines):
                changed_symbols.append((f, name, start, end))

    # Get all Python files, excluding virtual environments
    all_py_files = pathlib.Path(".").rglob("*.py")
    repo_files = [str(p) for p in all_py_files
                  if not any(part in p.parts for part in
                             ['.venv', 'venv', 'env', '.tox', 'site-packages', 'node_modules', '__pycache__'])]

    cg = callgraph_for_files(repo_files)
    impact_files = set(one_hop_slice(changed_symbols, cg))

    # Full git diff
    diff_text = subprocess.check_output(
        ["git", "diff", "--unified=3", "--no-color", "HEAD~1"]
    ).decode()

    # Snippets of changed code (grouped by proximity)
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

    # Track shown lines to avoid duplication
    shown_lines = {}
    for item in changed_snippets:
        f = item["file"]
        if "-" in item["lines"]:
            start, end = map(int, item["lines"].split("-"))
            shown_lines.setdefault(f, set()).update(range(start, end + 1))

    # Snippets from impact files:
    # 1. CALLEES - definitions that changed lines actually call
    calls_from_changed = set()
    for f, lines in changes.items():
        if f.endswith(".py") and pathlib.Path(f).exists():
            calls_from_changed.update(calls_in_lines(f, lines))

    # 2. CALLERS - collect names of functions/classes whose SIGNATURES were changed
    # (not just any function that contains a change)
    changed_signature_names = set()
    for f, lines in changes.items():
        if f.endswith(".py") and pathlib.Path(f).exists():
            changed_signature_names.update(symbols_with_signature_changes(f, lines))

    impact_snippets = []
    for f in sorted(impact_files):
        try:
            src = pathlib.Path(f).read_text(encoding="utf-8")
            tree = ast.parse(src)

            # Show CALLEES: definitions that changed code calls
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name in calls_from_changed:
                    # Show __init__ for classes
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

            # Show CALLERS: code that calls functions/classes whose SIGNATURES changed
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Only show if calling a function whose signature actually changed
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

def run_llm(review_context: str):
    """Send context to LLM for bug detection."""
    import time
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY") or getpass.getpass("OpenAI API key: ")
    client = OpenAI(api_key=api_key)

    prompt = (
        "You are a senior code reviewer analyzing a PR for bugs. "
        "You will receive structured markdown with THREE sections:\n\n"
        "1. Git Diff: Shows what changed (in <diff> tags)\n"
        "2. Changed Code: Snippets from modified files (in <file type=\"changed\"> tags)\n"
        "3. Impact Code: Both CALLEES (definitions the changed code calls) and CALLERS (code that calls the changed symbols). "
        "These show contracts/signatures and usage patterns.\n\n"
        "YOUR TASK: Find real bugs in the CHANGED CODE (type=\"changed\" files). Look for:\n"
        "- CONTRACT MISMATCHES: Wrong number of parameters, missing arguments, signature changes where callers weren't updated\n"
        "- LOGIC ERRORS: Off-by-one errors, incorrect conditionals, wrong operators, missing edge case handling\n"
        "- CONCURRENCY ISSUES: Race conditions, deadlocks, missing synchronization, unsafe shared state access\n"
        "- RESOURCE MANAGEMENT: Leaks, missing cleanup, incorrect resource lifetimes\n"
        "- ERROR HANDLING: Unhandled exceptions, incorrect error propagation, silent failures\n"
        "- SECURITY: Injection vulnerabilities, missing validation, unsafe operations\n\n"
        "CRITICAL: Your findings MUST reference the CHANGED files (type=\"changed\"), NOT the impact files. "
        "The impact files are provided only as reference to understand contracts/signatures. "
        "Report the specific line number in the CHANGED file where the bug occurs.\n\n"
        "Focus on real bugs, not style. If nothing critical is found, return an empty bugs array. "
        "For diff_fix_suggestion, provide a unified diff format if you have a concrete fix, or empty string if not.\n\n"
        "Review the following context:\n\n" + review_context
    )

    # Define JSON schema for structured output
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
                            "description": "Path to the CHANGED file where the bug exists (must be from type='changed' files, not impact files)"
                        },
                        "changed_lines": {
                            "type": "string",
                            "description": "Line number or range in the changed file (e.g., '55' or '55-57')"
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
                            "description": "Detailed explanation with evidence from changed code and impact code. Cite specific quotes and explain the contract mismatch or issue."
                        },
                        "diff_fix_suggestion": {
                            "type": "string",
                            "description": "Unified diff format showing the fix (e.g., '--- a/file.py\\n+++ b/file.py\\n@@ -55,1 +55,1 @@\\n-old line\\n+new line'). Use empty string if no concrete fix available."
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
    response = client.responses.create(
        model="gpt-4o-mini-2024-07-18",
        #model="gpt-5-mini",
        input=prompt,
        #reasoning={"effort": "low"},
        text={
             #"verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": "bug_report",
                "schema": json_schema,
                "strict": True
            }
        }
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time

    # Extract the JSON output from the response
    output_text = ""
    for item in response.output:
        # Only process ResponseOutputMessage items (these contain the actual output)
        if isinstance(item, ResponseOutputMessage):
            if item.content is not None:
                for content in item.content:
                    if isinstance(content, ResponseOutputText):
                        output_text += content.text

    data = json.loads(output_text)
    print(json.dumps(data, indent=2))

    # Display stats
    print("\n" + "="*80)
    print("STATISTICS")
    print("="*80)
    print(f"Time taken: {elapsed_time:.2f} seconds")

    # Extract token usage from response
    if hasattr(response, 'usage'):
        usage = response.usage
        print(f"Input tokens: {usage.input_tokens if hasattr(usage, 'input_tokens') else 'N/A'}")
        print(f"Output tokens: {usage.output_tokens if hasattr(usage, 'output_tokens') else 'N/A'}")
        if hasattr(usage, 'total_tokens'):
            print(f"Total tokens: {usage.total_tokens}")

    return data

if __name__ == "__main__":
    print("Building review context from local diff…")
    rc = build_review_context()
    print(rc)
    print("\n" + "="*80)
    print("Calling the model…")
    print("="*80 + "\n")
    run_llm(rc)
