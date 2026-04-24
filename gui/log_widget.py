"""
日志显示组件 — 浅色现代风格
白色背景，适配浅色主题的颜色区分
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class LogWidget(QWidget):
    """实时日志显示组件 — 浅色主题"""

    COLORS = {
        "debug": QColor("#64748B"),   # slate-500
        "info": QColor("#1E293B"),    # slate-800
        "warning": QColor("#B45309"), # amber-700
        "error": QColor("#DC2626"),   # red-600
        "success": QColor("#15803D"), # green-700
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
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

        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                color: #1E293B;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout.addWidget(self.text_edit)

    def append_log(self, level: str, message: str):
        """追加一条日志"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(level, self.COLORS["info"])

        self.text_edit.moveCursor(QTextCursor.End)

        # 时间戳
        fmt_time = QTextCharFormat()
        fmt_time.setForeground(QColor("#94A3B8"))
        fmt_time.setFont(QFont("Consolas", 9))
        self.text_edit.setCurrentCharFormat(fmt_time)
        self.text_edit.insertPlainText(f"[{timestamp}] ")

        # 级别标签
        fmt_level = QTextCharFormat()
        fmt_level.setForeground(color)
        fmt_level.setFontWeight(QFont.Bold)
        fmt_level.setFont(QFont("Consolas", 9))
        self.text_edit.setCurrentCharFormat(fmt_level)
        self.text_edit.insertPlainText(f"[{level.upper()}] ")

        # 消息内容
        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(color)
        fmt_msg.setFont(QFont("Consolas", 10))
        self.text_edit.setCurrentCharFormat(fmt_msg)
        self.text_edit.insertPlainText(message + "\n")

        self.text_edit.moveCursor(QTextCursor.End)

    def clear_log(self):
        """清空日志"""
        self.text_edit.clear()
