"""tools/code_analysis.py — AST-based static analysis for Python files."""
from __future__ import annotations
import ast
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeAnalysisTool:

    def analyze_file(self, filepath: str) -> dict[str, Any]:
        """Run full static analysis on a Python file."""
        fp = Path(filepath)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        source = fp.read_text(encoding="utf-8", errors="replace")
        result: dict[str, Any] = {
            "filepath": str(fp.resolve()), "loc": self._count_loc(source),
            "functions": [], "classes": [], "imports": [],
            "pyflakes_issues": [], "complexity_score": 0, "errors": [],
        }
        try:
            tree = ast.parse(source, filename=str(fp))
            result["functions"] = self._extract_functions(tree)
            result["classes"] = self._extract_classes(tree)
            result["imports"] = self._extract_imports(tree)
            result["complexity_score"] = self._cyclomatic_complexity(tree)
        except SyntaxError as exc:
            result["errors"].append(f"SyntaxError: {exc}")
            return result
        result["pyflakes_issues"] = self._run_pyflakes(fp)
        logger.info("Analysed %s: %d LOC, %d funcs, %d issues",
                    filepath, result["loc"], len(result["functions"]), len(result["pyflakes_issues"]))
        return result

    def analyze_snippet(self, code: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "loc": self._count_loc(code), "functions": [], "classes": [],
            "imports": [], "pyflakes_issues": [], "complexity_score": 0, "errors": [],
        }
        try:
            tree = ast.parse(code)
            result["functions"] = self._extract_functions(tree)
            result["classes"] = self._extract_classes(tree)
            result["imports"] = self._extract_imports(tree)
            result["complexity_score"] = self._cyclomatic_complexity(tree)
        except SyntaxError as exc:
            result["errors"].append(f"SyntaxError: {exc}")
        return result

    @staticmethod
    def _count_loc(source: str) -> int:
        return sum(1 for line in source.splitlines() if line.strip() and not line.strip().startswith("#"))

    @staticmethod
    def _extract_functions(tree: ast.AST) -> list[dict[str, Any]]:
        fns = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fns.append({
                    "name": node.name, "line": node.lineno,
                    "args": [a.arg for a in node.args.args],
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
        return fns

    @staticmethod
    def _extract_classes(tree: ast.AST) -> list[dict[str, Any]]:
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Use node.body (direct children only) to avoid picking up nested functions
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                classes.append({"name": node.name, "line": node.lineno, "methods": methods})
        return classes

    @staticmethod
    def _extract_imports(tree: ast.AST) -> list[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return imports

    @staticmethod
    def _cyclomatic_complexity(tree: ast.AST) -> int:
        branch_types = (ast.If, ast.For, ast.While, ast.With, ast.ExceptHandler, ast.BoolOp, ast.IfExp)
        return 1 + sum(1 for node in ast.walk(tree) if isinstance(node, branch_types))

    @staticmethod
    def _run_pyflakes(filepath: Path) -> list[dict[str, Any]]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pyflakes", str(filepath)],
                capture_output=True, text=True, timeout=15,
            )
            issues = []
            for line in result.stdout.splitlines():
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    try:
                        lineno = int(parts[1].strip())
                    except ValueError:
                        lineno = 0
                    issues.append({"line": lineno, "message": parts[2].strip()})
            return issues
        except Exception:
            return []

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "code_analysis",
            "description": "Analyse Python source files for syntax errors, unused imports, complexity metrics, and extract functions/classes.",
            "keywords": ["code","python","analyse","analyze","lint","error","bug","function","class","import","complexity","refactor"],
        }
