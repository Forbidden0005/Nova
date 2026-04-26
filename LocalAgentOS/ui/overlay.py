"""ui/overlay.py — Always-on-top persistent PyQt5 chat overlay."""
from __future__ import annotations
import logging
import subprocess
import sys
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer, QSize
from PyQt5.QtGui import QColor, QFont, QPalette, QTextCursor
from PyQt5.QtWidgets import (
    QAction, QApplication, QHBoxLayout, QLabel, QMenu,
    QPushButton, QSizeGrip, QTextEdit, QVBoxLayout, QWidget, QFrame,
)

if TYPE_CHECKING:
    from agent.core import AgentCore
    from voice.io import VoiceIO

logger = logging.getLogger(__name__)

BG_DARK = "#0f0f0f"; BG_PANEL = "#1a1a1a"; BG_INPUT = "#242424"
ACCENT = "#7c3aed"; ACCENT_HOV = "#6d28d9"
TEXT_PRI = "#e2e8f0"; TEXT_DIM = "#64748b"
USER_CLR = "#a78bfa"; BOT_CLR = "#34d399"; ERR_CLR = "#f87171"


class _WorkerThread(QThread):
    token_received = pyqtSignal(str)
    finished_reply = pyqtSignal(str)

    def __init__(self, agent: "AgentCore", message: str) -> None:
        super().__init__()
        self._agent = agent
        self._message = message

    def run(self) -> None:
        def _cb(token: str) -> None:
            self.token_received.emit(token)
        reply = self._agent.handle_message(self._message, stream_callback=_cb)
        self.finished_reply.emit(reply)


class ChatOverlay(QWidget):
    """The persistent always-on-top dark chat overlay window."""

    def __init__(self, agent: "AgentCore", voice: "VoiceIO") -> None:
        super().__init__()
        self._agent = agent
        self._voice = voice
        self._drag_pos: QPoint | None = None
        self._worker: _WorkerThread | None = None
        self._setup_window()
        self._build_ui()
        self._start_vram_timer()
        self._append_message("system", "🤖 LocalAgentOS online. Type or press 🎤 to speak.")

    def _setup_window(self) -> None:
        from config import OVERLAY_H, OVERLAY_OPACITY, OVERLAY_W, OVERLAY_X, OVERLAY_Y
        self.setWindowTitle("LocalAgentOS")
        self.setGeometry(OVERLAY_X, OVERLAY_Y, OVERLAY_W, OVERLAY_H)
        self.setMinimumSize(320, 400)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(OVERLAY_OPACITY)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        container = QFrame()
        container.setObjectName("container")
        container.setStyleSheet(f"QFrame#container {{background:{BG_DARK};border:1px solid #2d2d2d;border-radius:12px;}}")
        root.addWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)
        layout.addWidget(self._build_title_bar())
        layout.addWidget(self._build_vram_bar())
        layout.addWidget(self._build_chat_display())
        layout.addWidget(self._build_status_bar())
        layout.addWidget(self._build_input_area())
        grip = QSizeGrip(self)
        grip.setStyleSheet("background:transparent;")
        layout.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"background:{BG_PANEL};border-top-left-radius:12px;border-top-right-radius:12px;")
        bar.setCursor(Qt.SizeAllCursor)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 0, 8, 0)
        lbl = QLabel("🤖 LocalAgentOS")
        lbl.setStyleSheet(f"color:{TEXT_PRI};font-weight:600;font-size:13px;")
        h.addWidget(lbl)
        h.addStretch()
        for sym, tip, slot in [("–", "Minimise", self.showMinimized), ("✕", "Close", self.close)]:
            btn = QPushButton(sym)
            btn.setFixedSize(QSize(24, 24))
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            btn.setStyleSheet(f"QPushButton{{background:transparent;color:{TEXT_DIM};border:none;font-size:13px;}}QPushButton:hover{{color:{TEXT_PRI};}}")
            h.addWidget(btn)
        return bar

    def _build_vram_bar(self) -> QWidget:
        from PyQt5.QtWidgets import QProgressBar
        wrapper = QWidget()
        wrapper.setFixedHeight(22)
        wrapper.setStyleSheet(f"background:{BG_PANEL};")
        h = QHBoxLayout(wrapper)
        h.setContentsMargins(12, 2, 12, 2)
        lbl = QLabel("VRAM")
        lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:10px;")
        h.addWidget(lbl)
        self._vram_bar = QProgressBar()
        self._vram_bar.setRange(0, 100)
        self._vram_bar.setValue(0)
        self._vram_bar.setFixedHeight(8)
        self._vram_bar.setTextVisible(False)
        self._vram_bar.setStyleSheet(f"QProgressBar{{background:#2d2d2d;border-radius:4px;}}QProgressBar::chunk{{background:{ACCENT};border-radius:4px;}}")
        h.addWidget(self._vram_bar, 1)
        self._vram_label = QLabel("— MB")
        self._vram_label.setStyleSheet(f"color:{TEXT_DIM};font-size:10px;min-width:60px;")
        h.addWidget(self._vram_label)
        return wrapper

    def _build_chat_display(self) -> QTextEdit:
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setFont(QFont("Consolas", 10))
        self._chat_display.setStyleSheet(f"QTextEdit{{background:{BG_DARK};color:{TEXT_PRI};border:none;padding:8px 12px;}}")
        return self._chat_display

    def _build_status_bar(self) -> QLabel:
        self._status_label = QLabel("Ready")
        self._status_label.setFixedHeight(20)
        self._status_label.setStyleSheet(f"color:{TEXT_DIM};font-size:10px;padding-left:12px;background:{BG_PANEL};")
        return self._status_label

    def _build_input_area(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet(f"background:{BG_DARK};")
        h = QHBoxLayout(wrapper)
        h.setContentsMargins(8, 4, 8, 0)
        h.setSpacing(6)
        self._input_box = QTextEdit()
        self._input_box.setMaximumHeight(72)
        self._input_box.setPlaceholderText("Ask me anything, or say what to do…")
        self._input_box.setFont(QFont("Segoe UI", 10))
        self._input_box.setStyleSheet(f"QTextEdit{{background:{BG_INPUT};color:{TEXT_PRI};border:1px solid #2d2d2d;border-radius:8px;padding:6px 10px;}}")
        self._input_box.installEventFilter(self)
        h.addWidget(self._input_box, 1)
        col = QVBoxLayout()
        col.setSpacing(4)
        self._send_btn = self._action_btn("➤", "Send (Enter)", self._on_send)
        self._mic_btn  = self._action_btn("🎤", "Voice input", self._on_mic)
        col.addWidget(self._send_btn)
        col.addWidget(self._mic_btn)
        h.addLayout(col)
        return wrapper

    def _action_btn(self, sym: str, tip: str, slot) -> QPushButton:
        btn = QPushButton(sym)
        btn.setFixedSize(QSize(36, 32))
        btn.setToolTip(tip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        btn.setStyleSheet(f"QPushButton{{background:{ACCENT};color:white;border:none;border-radius:6px;font-size:14px;}}QPushButton:hover{{background:{ACCENT_HOV};}}QPushButton:disabled{{background:#3d3d3d;color:{TEXT_DIM};}}")
        return btn

    def _append_message(self, role: str, text: str) -> None:
        colours = {"user": USER_CLR, "assistant": BOT_CLR, "system": TEXT_DIM, "error": ERR_CLR}
        prefixes = {"user": "You", "assistant": "Agent", "system": "System", "error": "Error"}
        colour = colours.get(role, TEXT_PRI)
        prefix = prefixes.get(role, role.title())
        escaped = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br/>")
        html = f'<p style="margin:4px 0;"><span style="color:{colour};font-weight:600;">{prefix}</span><span style="color:{TEXT_DIM};"> › </span><span style="color:{TEXT_PRI};">{escaped}</span></p>'
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html)
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _on_send(self) -> None:
        text = self._input_box.toPlainText().strip()
        if not text or self._worker is not None:
            return
        self._input_box.clear()
        self._append_message("user", text)
        self._set_status("⚙ Thinking…")
        self._send_btn.setEnabled(False)
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(f'<p style="margin:4px 0;"><span style="color:{BOT_CLR};font-weight:600;">Agent</span><span style="color:{TEXT_DIM};"> › </span>')
        self._chat_display.setTextCursor(cursor)
        self._worker = _WorkerThread(self._agent, text)
        self._worker.token_received.connect(self._append_token)
        self._worker.finished_reply.connect(self._on_reply_done)
        self._worker.start()

    def _append_token(self, token: str) -> None:
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(token)
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _on_reply_done(self, reply: str) -> None:
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml("</p><br/>")
        self._worker = None
        self._send_btn.setEnabled(True)
        self._set_status("Ready")
        if reply and not reply.startswith("[Agent]"):
            self._voice.speak_async(reply[:300])

    def _on_mic(self) -> None:
        if self._worker:
            return
        self._set_status("🎤 Listening…")
        self._mic_btn.setEnabled(False)
        def _got(t: str) -> None:
            self._input_box.setPlainText(t)
            self._on_send()
            self._mic_btn.setEnabled(True)
        def _err(m: str) -> None:
            self._set_status(f"Voice: {m}")
            self._mic_btn.setEnabled(True)
        self._voice.listen_async(on_result=_got, on_error=_err)

    def _start_vram_timer(self) -> None:
        self._vram_timer = QTimer(self)
        self._vram_timer.timeout.connect(self._update_vram)
        self._vram_timer.start(10_000)
        self._update_vram()

    def _update_vram(self) -> None:
        used, total = self._query_vram()
        if total > 0:
            pct = int(used / total * 100)
            self._vram_bar.setValue(pct)
            self._vram_label.setText(f"{used:.0f}/{total:.0f} MB")

    @staticmethod
    def _query_vram() -> tuple[float, float]:
        try:
            out = subprocess.check_output(
                ["nvidia-smi","--query-gpu=memory.used,memory.total","--format=csv,noheader,nounits"],
                timeout=3, text=True,
            )
            parts = out.strip().split(",")
            if len(parts) == 2:
                return float(parts[0].strip()), float(parts[1].strip())
        except Exception:
            pass
        return 0.0, 0.0

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu{{background:{BG_PANEL};color:{TEXT_PRI};border:1px solid #2d2d2d;}}QMenu::item:selected{{background:{ACCENT};}}")
        menu.addAction("Clear history", self._clear_history)
        menu.addSeparator()
        for pct in (100, 90, 80, 70):
            act = QAction(f"Opacity {pct}%", self)
            act.triggered.connect(lambda _checked, p=pct: self.setWindowOpacity(p / 100))
            menu.addAction(act)
        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)
        menu.exec_(event.globalPos())

    def _clear_history(self) -> None:
        self._chat_display.clear()
        self._agent.memory.clear_history()
        self._append_message("system", "Chat history cleared.")

    def eventFilter(self, obj, event) -> bool:
        from PyQt5.QtCore import QEvent
        if obj is self._input_box and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)
