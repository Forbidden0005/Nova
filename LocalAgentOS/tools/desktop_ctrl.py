"""tools/desktop_ctrl.py — Mouse, keyboard, and window automation via pyautogui."""
from __future__ import annotations
import logging
import subprocess
import sys
from typing import Any

import pyautogui
from config import PYAUTOGUI_FAILSAFE, PYAUTOGUI_PAUSE_S

logger = logging.getLogger(__name__)
pyautogui.FAILSAFE = PYAUTOGUI_FAILSAFE
pyautogui.PAUSE = PYAUTOGUI_PAUSE_S


class DesktopCtrlTool:

    @staticmethod
    def screen_size() -> tuple[int, int]:
        return pyautogui.size()

    @staticmethod
    def cursor_position() -> tuple[int, int]:
        pos = pyautogui.position()
        return (pos.x, pos.y)

    def screenshot(self, save_path: str | None = None):
        img = pyautogui.screenshot()
        if save_path:
            img.save(save_path)
        return img

    def move_to(self, x: int, y: int, duration: float = 0.2) -> None:
        self._validate(x, y)
        pyautogui.moveTo(x, y, duration=duration)

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        self._validate(x, y)
        pyautogui.click(x, y, button=button, clicks=clicks)
        logger.info("Clicked %s at (%d,%d) x%d", button, x, y, clicks)

    def drag_to(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5, button: str = "left") -> None:
        self._validate(x1, y1)
        self._validate(x2, y2)
        pyautogui.moveTo(x1, y1, duration=0.1)
        pyautogui.dragTo(x2, y2, duration=duration, button=button)

    def scroll(self, x: int, y: int, clicks: int) -> None:
        self._validate(x, y)
        pyautogui.scroll(clicks, x=x, y=y)

    def type_text(self, text: str, interval: float = 0.02) -> None:
        pyautogui.typewrite(text, interval=interval)

    def press_key(self, key: str) -> None:
        pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys)
        logger.info("Hotkey: %s", " + ".join(keys))

    @staticmethod
    def open_application(app_name: str) -> None:
        if sys.platform == "win32":
            import os
            try:
                os.startfile(app_name)  # handles spaces and special chars automatically
            except OSError:
                # fallback for named apps (e.g. "notepad") that aren't file paths
                subprocess.Popen(f'start "" "{app_name}"', shell=True)
        else:
            subprocess.Popen([app_name])

    @staticmethod
    def get_active_window_title() -> str:
        try:
            if sys.platform == "win32":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
        except Exception:
            pass
        return ""

    def _validate(self, x: int, y: int) -> None:
        w, h = self.screen_size()
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"Coordinates ({x},{y}) outside screen ({w}x{h})")

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": "desktop_ctrl",
            "description": "Control mouse (move, click, drag, scroll), type keyboard input, press hotkeys, take screenshots, open apps.",
            "keywords": ["mouse","click","keyboard","type","hotkey","screenshot","window","desktop","automation","drag","scroll","open","launch"],
        }
