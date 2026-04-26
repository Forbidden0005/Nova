"""
agent/core.py — Central agent decision and execution loop.
"""
from __future__ import annotations
import json
import logging
import time
from typing import Any, Callable

import ollama as ollama_sdk

from config import (
    CHAT_TEMPERATURE, LLM_MAX_TOKENS, MAX_TOOL_RETRIES,
    OLLAMA_HOST, OLLAMA_MODEL, TOP_K_SKILLS,
)
from agent.planner import TaskPlanner
from memory.store import MemoryStore
from tools.file_ops import FileOpsTool
from tools.desktop_ctrl import DesktopCtrlTool
from tools.web_tools import WebTool
from tools.code_analysis import CodeAnalysisTool

logger = logging.getLogger(__name__)

TOOL_TRIGGER_WORDS = frozenset([
    "analyse", "analyze", "scan", "open", "click", "search", "browse",
    "scrape", "find", "delete", "move", "copy", "write", "read", "run", "execute"
])

AGENT_SYSTEM_PROMPT = """You are a local AI assistant running entirely on the user's machine.
You have tools for file operations, desktop control, web browsing, and code analysis.
Be concise and precise. After using tools, summarise what you found or did."""


class AgentCore:
    """Main agent loop: conversation, planning, tool execution."""

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory
        self._client = ollama_sdk.Client(host=OLLAMA_HOST)
        self._tools: dict[str, Any] = {
            "file_ops":      FileOpsTool(),
            "desktop_ctrl":  DesktopCtrlTool(),
            "web_tools":     WebTool(),
            "code_analysis": CodeAnalysisTool(),
        }
        self._registry: dict[str, dict[str, Any]] = {
            name: tool.metadata for name, tool in self._tools.items()
        }
        self._planner = TaskPlanner(ollama_call_fn=self._call_ollama_raw)
        logger.info("AgentCore ready — model=%s tools=%s", OLLAMA_MODEL, list(self._registry.keys()))

    def handle_message(self, user_input: str, stream_callback: Callable[[str], None] | None = None) -> str:
        self.memory.add_message("user", user_input)
        if self._is_tool_request(user_input):
            reply = self._tool_execution_turn(user_input, stream_callback)
        else:
            reply = self._conversation_turn(user_input, stream_callback)
        self.memory.add_message("assistant", reply)
        return reply

    def _conversation_turn(self, user_input: str, stream_callback: Callable[[str], None] | None) -> str:
        messages = self._build_messages(user_input)
        return self._call_ollama_stream(messages, stream_callback)

    def _tool_execution_turn(self, user_input: str, stream_callback: Callable[[str], None] | None) -> str:
        available_tool_meta = list(self._registry.values())
        plan = self._planner.plan(user_input, available_tool_meta)
        steps: list[str] = plan.get("steps", [user_input])
        tools_needed: list[str] = plan.get("tools_needed", [])
        if stream_callback:
            stream_callback(f"[Agent] Planning {len(steps)} step(s)…\n")
        ranked_tools = self._planner.rank_tools(user_input, self._registry, top_k=TOP_K_SKILLS)
        active_tool_names = tools_needed if tools_needed else ranked_tools
        execution_log: list[str] = []
        result_summary: list[str] = []
        for i, step in enumerate(steps, start=1):
            if stream_callback:
                stream_callback(f"[Step {i}/{len(steps)}] {step}\n")
            step_result = self._execute_step(step, active_tool_names, stream_callback)
            execution_log.append(f"Step {i}: {step}\nResult: {step_result}")
            result_summary.append(step_result)
        synthesis_prompt = (
            f"The user asked: {user_input}\n\nI executed these steps and got:\n"
            + "\n---\n".join(result_summary[:5])
            + "\n\nSummarise what was done in 2-4 sentences."
        )
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": synthesis_prompt},
        ]
        reply = self._call_ollama_stream(messages, stream_callback)
        self.memory.log_task(task_name=user_input[:80], steps=steps, result="success", log="\n".join(execution_log))
        return reply

    def _execute_step(self, step: str, tool_names: list[str], stream_callback: Callable[[str], None] | None) -> str:
        tool_docs = {n: self._registry.get(n, {}) for n in tool_names if n in self._tools}
        dispatch_prompt = (
            f"Step: {step}\nTools: {json.dumps({n: m.get('description','') for n,m in tool_docs.items()})}\n"
            'Respond with JSON only: {"tool": "<name>", "method": "<method>", "args": {<kwargs>}}'
        )
        raw = self._call_ollama_raw(prompt=dispatch_prompt, system=AGENT_SYSTEM_PROMPT, temperature=0.05)
        dispatch = self._planner._parse_json(raw)
        tool_name = dispatch.get("tool", "")
        method_name = dispatch.get("method", "")
        args = dispatch.get("args", {})
        if not tool_name or tool_name not in self._tools:
            return f"No matching tool for: {step}"
        method = getattr(self._tools[tool_name], method_name, None)
        if method is None:
            return f"Tool '{tool_name}' has no method '{method_name}'"
        for attempt in range(1, MAX_TOOL_RETRIES + 1):
            try:
                output = method(**args)
                return self._format_output(output)
            except Exception as exc:
                logger.warning("Tool %s.%s failed attempt %d/%d: %s", tool_name, method_name, attempt, MAX_TOOL_RETRIES, exc)
                if attempt == MAX_TOOL_RETRIES:
                    return f"Error after {MAX_TOOL_RETRIES} attempts: {exc}"
                time.sleep(0.5)
        return "Tool execution failed"

    def _call_ollama_stream(self, messages: list[dict], stream_callback: Callable[[str], None] | None) -> str:
        full = []
        try:
            stream = self._client.chat(
                model=OLLAMA_MODEL, messages=messages, stream=True,
                options={"temperature": CHAT_TEMPERATURE, "num_predict": LLM_MAX_TOKENS},
            )
            for chunk in stream:
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full.append(token)
                    if stream_callback:
                        stream_callback(token)
        except Exception as exc:
            err = f"[Ollama error: {exc}]"
            if stream_callback:
                stream_callback(err)
            return err
        return "".join(full)

    def _call_ollama_raw(self, prompt: str, system: str = "", temperature: float = CHAT_TEMPERATURE) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self._client.chat(
                model=OLLAMA_MODEL, messages=messages, stream=False,
                options={"temperature": temperature, "num_predict": LLM_MAX_TOKENS},
            )
            return response["message"]["content"]
        except Exception as exc:
            logger.error("Ollama raw call failed: %s", exc)
            return "{}"

    def _build_messages(self, user_input: str) -> list[dict]:
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        messages += self.memory.get_recent_messages()
        if not messages or messages[-1].get("content") != user_input:
            messages.append({"role": "user", "content": user_input})
        return messages

    @staticmethod
    def _is_tool_request(text: str) -> bool:
        first_word = text.strip().split()[0].lower().rstrip(":") if text.strip() else ""
        return first_word in TOOL_TRIGGER_WORDS

    @staticmethod
    def _format_output(output: Any) -> str:
        if isinstance(output, str):
            return output[:2000]
        try:
            return json.dumps(output, indent=2, default=str)[:2000]
        except Exception:
            return str(output)[:2000]

    def shutdown(self) -> None:
        try:
            self._tools["web_tools"].quit()
        except Exception:
            pass
        self.memory.close()
        logger.info("AgentCore shut down")
