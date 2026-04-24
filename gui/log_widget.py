"""
日志显示组件 — 简洁浅色风格
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit, QVBoxLayou, QWidget

from .theme import STATUS_GREEN, STATUS_RED, STATUS_YELLOW, log_style


class LogWidget(QWidget):
    """实时日志显示组件"""

    COLORS = {
        "debug": QColor("#6B7280"),
        "info": QColor("#111827"),
        "warning": QColor(STATUS_YELLOW),
        "error": QColor(STATUS_RED),
        "success": QColor(STATUS_GREEN),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayou(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        font = QFont("JetBrains Mono", 10)
        if not QFont(font).exactMatch():
            font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_edit.setFont(font)
        self.text_edit.setStyleSheet(log_style())

        layout.addWidget(self.text_edit)

    def append_log(self, level: str, message: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(level, self.COLORS["info"])

        self.text_edit.moveCursor(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#9CA3AF"))
        fmt.setFont(QFont("Consolas", 9))
        self.text_edit.setCurrentCharFormat(fmt)
        self.text_edit.insertPlainText(f"[{ts}] ")

        fmt = QTextCharFormat()
        fmt.setForeground(color)
        fmt.setFontWeight(QFont.Bold)
        fmt.setFont(QFont("Consolas", 9))
        self.text_edit.setCurrentCharFormat(fmt)
        self.text_edit.insertPlainText(f"[{level.upper()}] ")

        fmt = QTextCharFormat()
        fmt.setForeground(color)
        fmt.setFont(QFont("Consolas", 10))
        self.text_edit.setCurrentCharFormat(fmt)
        self.text_edit.insertPlainText(message + "\n")

        self.text_edit.moveCursor(QTextCursor.End)

    def clear_log(self):
        self.text_edit.clear()
