"""skills/generator.py — Auto-extract reusable Python skills from task logs."""
from __future__ import annotations
import ast
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from config import SKILLS_DIR

logger = logging.getLogger(__name__)

SKILL_GEN_SYSTEM = """You are a Python code generator. Given a completed task description,
produce a SINGLE self-contained Python function named `run(**kwargs)`.
Requirements: descriptive docstring, type hints, try/except error handling,
return a meaningful result. Use only stdlib and common packages (os, pathlib, subprocess, json, requests).
Output ONLY the function code — no markdown, no explanation."""


class SkillGenerator:
    """Extracts reusable Python skills from task execution logs via Ollama."""

    def __init__(self, ollama_call_fn: Callable[[str, str, float], str], skills_dir: Path = SKILLS_DIR) -> None:
        self._call = ollama_call_fn
        self._skills_dir = skills_dir
        self._skills_dir.mkdir(parents=True, exist_ok=True)

    def generate_from_log(self, task_name: str, steps: list[str], execution_log: str) -> str | None:
        """Generate and save a reusable skill from a completed task. Returns skill name or None."""
        safe_name = self._sanitise_name(task_name)
        prompt = (
            f"Task: {task_name}\nSteps:\n"
            + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
            + f"\n\nLog:\n{execution_log[:1500]}\n\nGenerate a Python run(**kwargs) function."
        )
        raw_code = self._call(prompt, SKILL_GEN_SYSTEM, 0.2)
        code = self._extract_code(raw_code)
        if not code or not self._validate_python(code) or "def run" not in code:
            logger.warning("SkillGenerator: invalid or empty code for '%s'", task_name)
            return None
        (self._skills_dir / f"{safe_name}_skill.py").write_text(code, encoding="utf-8")
        meta: dict[str, Any] = {
            "name": safe_name, "description": f"Auto-generated from: {task_name}",
            "created_at": datetime.utcnow().isoformat(), "usage_count": 0,
            "success_rate": 1.0, "keywords": self._extract_keywords(task_name + " " + " ".join(steps)),
        }
        (self._skills_dir / f"{safe_name}_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("Skill saved: %s", safe_name)
        return safe_name

    @staticmethod
    def _sanitise_name(raw: str) -> str:
        return (re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_") or "skill")[:60]

    @staticmethod
    def _extract_code(raw: str) -> str:
        return re.sub(r"```(?:python)?", "", raw, flags=re.IGNORECASE).replace("```", "").strip()

    @staticmethod
    def _validate_python(code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        stop = {"the","a","an","and","or","is","in","to","of","for","with","that","this","was","are","from","by"}
        words = re.findall(r"[a-z]{3,}", text.lower())
        seen: set[str] = set()
        result = []
        for w in words:
            if w not in stop and w not in seen:
                seen.add(w)
                result.append(w)
        return result[:20]
