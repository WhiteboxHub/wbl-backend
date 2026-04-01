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
