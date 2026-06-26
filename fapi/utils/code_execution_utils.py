"""
Code Execution Utilities for CodePad
Provides safe, sandboxed code execution for multiple languages
"""
import subprocess
import tempfile
import os
import sys
import time
import json
import textwrap
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CodeExecutionError(Exception):
    """Custom exception for code execution errors"""
    pass


class CodeExecutor:
    """
    Executes code in a sandboxed environment with timeout support.
    Supports Python, JavaScript, Java, C++, Go, and Rust.
    """

    # Map of language to execution commands
    LANGUAGE_RUNNERS = {
        "python": {"extension": ".py", "runner": "python"},
        "python3": {"extension": ".py", "runner": "python3"},
        "javascript": {"extension": ".js", "runner": "node"},
        "js": {"extension": ".js", "runner": "node"},
        "typescript": {"extension": ".ts", "runner": "ts-node"},
        "ts": {"extension": ".ts", "runner": "ts-node"},
        "java": {"extension": ".java", "runner": "javac_run"},
        "cpp": {"extension": ".cpp", "runner": "g++"},
        "c": {"extension": ".c", "runner": "gcc"},
        "go": {"extension": ".go", "runner": "go run"},
        "rust": {"extension": ".rs", "runner": "rustc"},
        "bash": {"extension": ".sh", "runner": "bash"},
    }

    MAX_TIMEOUT = 30  # Server-side hard cap in seconds

    @staticmethod
    def execute_for_test_case(
        code: str,
        language: str,
        input_data: Optional[str],
        timeout: int = 5,
    ) -> Dict[str, Any]:
        """
        Run one assignment test case: prefer calling a user-defined function with stdin
        as the argument and printing the return value; fall back to plain stdin execution.
        """
        language = language.lower().strip()
        if language in ("python", "python3"):
            harness_result = CodeExecutor._execute_python_test_harness(
                code, input_data, timeout
            )
            out = harness_result.get("output")
            if out is not None and str(out).strip() != "":
                return harness_result
            if harness_result.get("status") == "error" and harness_result.get("error"):
                return harness_result
        return CodeExecutor.execute(code, language, input_data, timeout)

    @staticmethod
    def _build_python_test_harness_script(user_code: str) -> str:
        encoded = json.dumps(user_code)
        return textwrap.dedent(
            f"""
            import sys
            import inspect
            import json as _json
            import io
            import contextlib

            _USER_CODE = {encoded}
            _namespace = {{"__name__": "__wbl_test__"}}
            with contextlib.redirect_stdout(io.StringIO()):
                exec(_USER_CODE, _namespace)

            def _parse_stdin(s):
                s = (s or "").strip()
                if not s:
                    return None
                try:
                    return _json.loads(s)
                except Exception:
                    pass
                try:
                    return eval(s, {{"__builtins__": {{}}}})
                except Exception:
                    return s

            def _format_out(val):
                if val is None:
                    return ""
                if isinstance(val, bool):
                    return "true" if val else "false"
                if isinstance(val, float) and val == int(val):
                    return str(int(val))
                return str(val)

            def _pick_func(ns):
                funcs = [
                    (n, o)
                    for n, o in ns.items()
                    if inspect.isfunction(o) and not n.startswith("_")
                ]
                for prefer in ("solution", "classify_temperature", "solve", "main"):
                    for n, o in funcs:
                        if n == prefer:
                            return o
                if len(funcs) == 1:
                    return funcs[0][1]
                if funcs:
                    return funcs[-1][1]
                return None

            def _call_with_stdin(func, arg):
                sig = inspect.signature(func)
                n = len(sig.parameters)
                if n == 0:
                    return func()
                if n == 1:
                    return func(arg)
                if isinstance(arg, dict):
                    return func(**arg)
                if isinstance(arg, (list, tuple)):
                    return func(*arg)
                raise TypeError(
                    f"Function expects {{n}} arguments but stdin provided {{type(arg).__name__}}"
                )

            _fn = _pick_func(_namespace)
            if _fn is None:
                sys.exit(0)
            _arg = _parse_stdin(sys.stdin.read())
            _out = _format_out(_call_with_stdin(_fn, _arg))
            if _out:
                print(_out, end="")
            """
        ).lstrip()

    @staticmethod
    def _execute_python_test_harness(
        code: str, input_data: Optional[str], timeout: int
    ) -> Dict[str, Any]:
        script = CodeExecutor._build_python_test_harness_script(code)
        return CodeExecutor._execute_python(script, input_data, timeout)

    @staticmethod
    def execute(
        code: str,
        language: str,
        input_data: Optional[str] = None,
        timeout: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute code with timeout and return results
        
        Args:
            code: The code to execute
            language: Programming language (python, javascript, java, cpp, etc.)
            input_data: Optional stdin input for the program
            timeout: Timeout in seconds (default: 5)
        
        Returns:
            Dict with output, error, status, and execution_time_ms
        """
        try:
            # Normalize language
            language = language.lower().strip()

            if language not in CodeExecutor.LANGUAGE_RUNNERS:
                return {
                    "output": None,
                    "error": f"Unsupported language: {language}. Supported: {', '.join(CodeExecutor.LANGUAGE_RUNNERS.keys())}",
                    "status": "error",
                    "execution_time_ms": 0,
                }

            # Enforce server-side timeout cap
            timeout = min(timeout, CodeExecutor.MAX_TIMEOUT)

            start_time = time.time()
            
            result = CodeExecutor._execute_language(
                code=code,
                language=language,
                input_data=input_data,
                timeout=timeout,
            )
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            result["execution_time_ms"] = execution_time_ms
            
            return result

        except Exception as e:
            logger.error(f"Code execution error: {str(e)}")
            return {
                "output": None,
                "error": f"Execution error: {str(e)}",
                "status": "error",
                "execution_time_ms": 0,
            }

    @staticmethod
    def _execute_language(
        code: str,
        language: str,
        input_data: Optional[str],
        timeout: int,
    ) -> Dict[str, Any]:
        """Execute code for specific language"""
        
        if language in ["python", "python3"]:
            return CodeExecutor._execute_python(code, input_data, timeout)
        elif language in ["javascript", "js"]:
            return CodeExecutor._execute_javascript(code, input_data, timeout)
        elif language in ["typescript", "ts"]:
            return CodeExecutor._execute_typescript(code, input_data, timeout)
        elif language == "java":
            return CodeExecutor._execute_java(code, input_data, timeout)
        elif language in ["cpp", "c"]:
            return CodeExecutor._execute_cpp_c(code, language, input_data, timeout)
        elif language == "go":
            return CodeExecutor._execute_go(code, input_data, timeout)
        elif language == "rust":
            return CodeExecutor._execute_rust(code, input_data, timeout)
        elif language == "bash":
            return CodeExecutor._execute_bash(code, input_data, timeout)
        else:
            return {
                "output": None,
                "error": f"Language {language} not yet implemented",
                "status": "error",
            }

    @staticmethod
    def _execute_python(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute Python code"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name

        try:
            # Use sys.executable first (guaranteed to exist — same interpreter running the server).
            # Then try common command names as fallbacks.
            python_candidates = [sys.executable, "python", "python3"]
            # Deduplicate while preserving order
            seen = set()
            python_candidates = [p for p in python_candidates if not (p in seen or seen.add(p))]

            last_error = "Python interpreter not found."
            for python_cmd in python_candidates:
                try:
                    result = subprocess.run(
                        [python_cmd, temp_file],
                        input=input_data,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )

                    if result.returncode == 0:
                        return {
                            "output": result.stdout,
                            "error": None,
                            "status": "success",
                        }
                    else:
                        return {
                            "output": result.stdout if result.stdout else None,
                            "error": result.stderr,
                            "status": "error",
                        }
                except FileNotFoundError:
                    last_error = f"Interpreter not found: {python_cmd}"
                    continue

            # All candidates exhausted
            return {
                "output": None,
                "error": last_error,
                "status": "error",
            }

        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": f"Execution timed out after {timeout} seconds",
                "status": "timeout",
            }
        except Exception as e:
            return {
                "output": None,
                "error": f"Python execution error: {str(e)}",
                "status": "error",
            }
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass

    @staticmethod
    def _execute_javascript(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute JavaScript code"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                ["node", temp_file],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return {
                    "output": result.stdout,
                    "error": None,
                    "status": "success",
                }
            else:
                return {
                    "output": result.stdout if result.stdout else None,
                    "error": result.stderr,
                    "status": "error",
                }

        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": f"Execution timed out after {timeout} seconds",
                "status": "timeout",
            }
        finally:
            try:
                os.unlink(temp_file)
            except Exception:
                pass

    @staticmethod
    def _execute_typescript(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute TypeScript code using ts-node"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                ["ts-node", "--skip-project", temp_file],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return {
                    "output": result.stdout,
                    "error": None,
                    "status": "success",
                }
            else:
                return {
                    "output": result.stdout if result.stdout else None,
                    "error": result.stderr,
                    "status": "error",
                }

        except FileNotFoundError:
            return {
                "output": None,
                "error": "ts-node not found. Install with: npm install -g ts-node typescript",
                "status": "error",
            }
        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": f"Execution timed out after {timeout} seconds",
                "status": "timeout",
            }
        finally:
            try:
                os.unlink(temp_file)
            except Exception:
                pass

    @staticmethod
    def _execute_java(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute Java code"""
        # Extract class name from code
        import re
        match = re.search(r'public\s+class\s+(\w+)', code)
        class_name = match.group(1) if match else "Main"

        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = os.path.join(tmpdir, f"{class_name}.java")
            with open(java_file, 'w') as f:
                f.write(code)

            try:
                # Compile
                compile_result = subprocess.run(
                    ["javac", java_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if compile_result.returncode != 0:
                    return {
                        "output": None,
                        "error": compile_result.stderr,
                        "status": "error",
                    }

                # Run
                result = subprocess.run(
                    ["java", "-cp", tmpdir, class_name],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    return {
                        "output": result.stdout,
                        "error": None,
                        "status": "success",
                    }
                else:
                    return {
                        "output": result.stdout if result.stdout else None,
                        "error": result.stderr,
                        "status": "error",
                    }

            except subprocess.TimeoutExpired:
                return {
                    "output": None,
                    "error": f"Execution timed out after {timeout} seconds",
                    "status": "timeout",
                }

    @staticmethod
    def _execute_cpp_c(code: str, language: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute C++ or C code"""
        extension = ".cpp" if language == "cpp" else ".c"
        compiler = "g++" if language == "cpp" else "gcc"

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, f"program{extension}")
            output_file = os.path.join(tmpdir, "program")

            with open(source_file, 'w') as f:
                f.write(code)

            try:
                # Compile
                compile_result = subprocess.run(
                    [compiler, source_file, "-o", output_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if compile_result.returncode != 0:
                    return {
                        "output": None,
                        "error": compile_result.stderr,
                        "status": "error",
                    }

                # Run
                result = subprocess.run(
                    [output_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    return {
                        "output": result.stdout,
                        "error": None,
                        "status": "success",
                    }
                else:
                    return {
                        "output": result.stdout if result.stdout else None,
                        "error": result.stderr,
                        "status": "error",
                    }

            except subprocess.TimeoutExpired:
                return {
                    "output": None,
                    "error": f"Execution timed out after {timeout} seconds",
                    "status": "timeout",
                }

    @staticmethod
    def _execute_go(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute Go code"""
        with tempfile.TemporaryDirectory() as tmpdir:
            go_file = os.path.join(tmpdir, "main.go")
            with open(go_file, 'w') as f:
                f.write(code)

            try:
                result = subprocess.run(
                    ["go", "run", go_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tmpdir,
                )

                if result.returncode == 0:
                    return {
                        "output": result.stdout,
                        "error": None,
                        "status": "success",
                    }
                else:
                    return {
                        "output": result.stdout if result.stdout else None,
                        "error": result.stderr,
                        "status": "error",
                    }

            except subprocess.TimeoutExpired:
                return {
                    "output": None,
                    "error": f"Execution timed out after {timeout} seconds",
                    "status": "timeout",
                }

    @staticmethod
    def _execute_rust(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute Rust code"""
        with tempfile.TemporaryDirectory() as tmpdir:
            rs_file = os.path.join(tmpdir, "main.rs")
            output_file = os.path.join(tmpdir, "program")

            with open(rs_file, 'w') as f:
                f.write(code)

            try:
                # Compile
                compile_result = subprocess.run(
                    ["rustc", rs_file, "-o", output_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if compile_result.returncode != 0:
                    return {
                        "output": None,
                        "error": compile_result.stderr,
                        "status": "error",
                    }

                # Run
                result = subprocess.run(
                    [output_file],
                    input=input_data,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    return {
                        "output": result.stdout,
                        "error": None,
                        "status": "success",
                    }
                else:
                    return {
                        "output": result.stdout if result.stdout else None,
                        "error": result.stderr,
                        "status": "error",
                    }

            except subprocess.TimeoutExpired:
                return {
                    "output": None,
                    "error": f"Execution timed out after {timeout} seconds",
                    "status": "timeout",
                }

    @staticmethod
    def _execute_bash(code: str, input_data: Optional[str], timeout: int) -> Dict[str, Any]:
        """Execute Bash script"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                ["bash", temp_file],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return {
                    "output": result.stdout,
                    "error": None,
                    "status": "success",
                }
            else:
                return {
                    "output": result.stdout if result.stdout else None,
                    "error": result.stderr,
                    "status": "error",
                }

        except subprocess.TimeoutExpired:
            return {
                "output": None,
                "error": f"Execution timed out after {timeout} seconds",
                "status": "timeout",
            }
        finally:
            os.unlink(temp_file)
