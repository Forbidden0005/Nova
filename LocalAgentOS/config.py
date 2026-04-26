"""
config.py — Global constants and runtime configuration for LocalAgentOS.
All tunables live here.
"""
from __future__ import annotations
import os
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR: Path = Path(__file__).parent.resolve()
SKILLS_DIR: Path = Path.home() / ".agent_skills"
MEMORY_DB: Path = BASE_DIR / "memory" / "agent_memory.db"
LOG_FILE: Path = BASE_DIR / "agent.log"

SKILLS_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)

# ─── Ollama / LLM ─────────────────────────────────────────────────────────────
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
LLM_MAX_TOKENS: int = 1024
PLANNER_TEMPERATURE: float = 0.1
CHAT_TEMPERATURE: float = 0.7
OLLAMA_TIMEOUT_S: int = 120

# ─── Memory ───────────────────────────────────────────────────────────────────
CONTEXT_WINDOW_TURNS: int = 20

# ─── VRAM Budget (GTX 1080 Ti = 11 GB) ───────────────────────────────────────
VRAM_TOTAL_MB: int = 11_264
VRAM_LLM_RESERVED_MB: int = 6_000
VRAM_HEADROOM_MB: int = 512
VRAM_LOW_THRESHOLD_MB: int = VRAM_HEADROOM_MB

# ─── Desktop Control ──────────────────────────────────────────────────────────
PYAUTOGUI_PAUSE_S: float = 0.05
PYAUTOGUI_FAILSAFE: bool = True

# ─── Web / Scraping ───────────────────────────────────────────────────────────
SELENIUM_HEADLESS: bool = True
SELENIUM_TIMEOUT_S: int = 30
SELENIUM_PAGE_LOAD_TIMEOUT_S: int = 45

# ─── Skill Registry ───────────────────────────────────────────────────────────
TOP_K_SKILLS: int = 5
PRUNE_MIN_USAGE: int = 10
PRUNE_MIN_SUCCESS: float = 0.5

# ─── Voice ────────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE: str = os.getenv("ELEVENLABS_VOICE", "Bella")
USE_ELEVENLABS: bool = bool(ELEVENLABS_API_KEY)

# ─── UI ───────────────────────────────────────────────────────────────────────
OVERLAY_X: int = 1_200
OVERLAY_Y: int = 80
OVERLAY_W: int = 420
OVERLAY_H: int = 560
OVERLAY_OPACITY: float = 0.93

# ─── Agent Loop ───────────────────────────────────────────────────────────────
MAX_TOOL_RETRIES: int = 2
MAX_PLAN_STEPS: int = 10
