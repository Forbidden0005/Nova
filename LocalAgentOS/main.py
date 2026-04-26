"""
main.py — LocalAgentOS entry point.

Usage:
    python main.py            # GUI overlay (console hides once window appears)
    python main.py --debug    # GUI overlay, keep console open
    python main.py --cli      # headless REPL
    python main.py --prune    # prune weak skills and exit
"""
from __future__ import annotations
import argparse
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from config import LOG_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

from memory.store import MemoryStore
from agent.core import AgentCore
from skills.registry import SkillRegistry
from skills.generator import SkillGenerator
from voice.io import VoiceIO


def _hide_console() -> None:
    """Hide the Windows console window. No-op on non-Windows or if it fails."""
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def build_agent(memory: MemoryStore, registry: SkillRegistry) -> AgentCore:
    agent = AgentCore(memory=memory)
    generator = SkillGenerator(ollama_call_fn=agent._call_ollama_raw)
    original_log = memory.log_task

    def _patched_log(task_name, steps, result, log):
        row_id = original_log(task_name, steps, result, log)
        if result == "success":
            skill_name = generator.generate_from_log(task_name, steps, log)
            if skill_name:
                registry.reload()
                logger.info("Auto-registered new skill: %s", skill_name)
        return row_id

    memory.log_task = _patched_log  # type: ignore[method-assign]
    return agent


def run_gui(agent: AgentCore, voice: VoiceIO, debug: bool = False) -> int:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    from ui.overlay import ChatOverlay
    app = QApplication(sys.argv)
    app.setApplicationName("LocalAgentOS")
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setStyle("Fusion")
    window = ChatOverlay(agent=agent, voice=voice)
    window.show()

    # Hide the console once the overlay is on screen, unless debug mode
    if not debug:
        _hide_console()

    code = app.exec_()
    agent.shutdown()
    return code


def run_cli(agent: AgentCore) -> int:
    print("LocalAgentOS — CLI mode.  Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You > ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if user_input.lower() in {"quit", "exit", "q"}:
            break
        if not user_input:
            continue
        print("Agent > ", end="", flush=True)
        agent.handle_message(user_input, stream_callback=lambda t: print(t, end="", flush=True))
        print()
    agent.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LocalAgentOS")
    parser.add_argument("--cli",   action="store_true", help="Headless CLI REPL")
    parser.add_argument("--prune", action="store_true", help="Prune weak skills and exit")
    parser.add_argument("--debug", action="store_true", help="Keep console open (debug mode)")
    args = parser.parse_args()

    memory   = MemoryStore()
    registry = SkillRegistry()
    agent    = build_agent(memory, registry)
    voice    = VoiceIO()

    logger.info(
        "LocalAgentOS started — %d skills loaded%s",
        len(registry.get_skill_names()),
        "  [DEBUG]" if args.debug else "",
    )

    if args.prune:
        pruned = registry.prune()
        print(f"Pruned: {pruned or 'none'}")
        return 0

    if args.cli:
        return run_cli(agent)

    return run_gui(agent, voice, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
