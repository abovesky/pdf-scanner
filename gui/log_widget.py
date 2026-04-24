"""
日志显示组件
带颜色区分的 QTextEdit
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class LogWidget(QWidget):
    """实时日志显示组件"""

    COLORS = {
        "debug": QColor("#94A3B8"),
        "info": QColor("#F1F5F9"),
        "warning": QColor("#F59E0B"),
        "error": QColor("#EF4444"),
        "success": QColor("#10B981"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.text_edit.setFont(font)

        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0F172A;
                color: #F1F5F9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
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
        fmt_time.setForeground(QColor("#64748B"))
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
