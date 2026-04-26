"""
agent/planner.py — LLM-backed task decomposition and tool relevance scoring.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any

from config import MAX_PLAN_STEPS, PLANNER_TEMPERATURE

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """
You are a task planning AI. Break down a user request into ordered steps.
You have access to the following tools:
{tool_list}

Respond ONLY with valid JSON — no markdown, no explanation.
Two keys required:
  "steps"        — ordered list of step strings (max {max_steps})
  "tools_needed" — list of tool names needed

Example:
{{"steps": ["Scan Downloads folder", "Find duplicates"], "tools_needed": ["file_ops"]}}
""".strip()


class TaskPlanner:
    """Breaks user requests into structured execution plans via Ollama."""

    def __init__(self, ollama_call_fn: Any) -> None:
        self._call = ollama_call_fn

    def plan(self, user_request: str, available_tools: list[dict[str, Any]]) -> dict[str, Any]:
        tool_list = "\n".join(f"  - {t['name']}: {t['description']}" for t in available_tools)
        system = PLANNER_SYSTEM_PROMPT.format(tool_list=tool_list, max_steps=MAX_PLAN_STEPS)
        raw = self._call(prompt=f"User request: {user_request}", system=system, temperature=PLANNER_TEMPERATURE)
        plan = self._parse_json(raw)
        plan.setdefault("steps", [user_request])
        plan.setdefault("tools_needed", [])
        plan["steps"] = plan["steps"][:MAX_PLAN_STEPS]
        logger.info("Plan: %d steps, tools=%s", len(plan["steps"]), plan["tools_needed"])
        return plan

    @staticmethod
    def rank_tools(task_description: str, tool_registry: dict[str, Any], top_k: int = 5) -> list[str]:
        if not tool_registry:
            return []
        documents = {
            name: " ".join(meta.get("keywords", []) + [meta.get("description", "")])
            for name, meta in tool_registry.items()
        }
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            names = list(documents.keys())
            corpus = [task_description] + [documents[n] for n in names]
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform(corpus)
            sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()
            return [names[i] for i in np.argsort(sims)[::-1][:top_k]]
        except ImportError:
            task_words = set(task_description.lower().split())
            scores = {n: len(task_words & set(doc.lower().split())) for n, doc in documents.items()}
            return sorted(scores, key=lambda n: scores[n], reverse=True)[:top_k]

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip().replace("```", "")
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON from LLM response: %s | raw: %.200s", exc, raw if 'raw' in dir() else cleaned)
            return {}
