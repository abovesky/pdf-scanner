"""
设置面板组件 — 简洁浅色风格
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import AppConfig
from core.ocr_engines import OCREngineFactory
from .theme import (
    TEXT_PRIMARY,
    checkbox_style,
    combobox_style,
    group_style,
    input_style,
    secondary_button_style,
    spinbox_style,
)


class SettingsPanel(QScrollArea):
    """参数设置面板 — 可滚动侧边栏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.NoFrame)
        self._setup_ui()
        self.load_from_config()

    def _setup_ui(self):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 4, 0)

        # 目录设置组
        dir_group = self._create_group("目录设置")
        dir_layout = QVBoxLayout(dir_group)
        dir_layout.setSpacing(8)
        dir_layout.setContentsMargins(12, 12, 12, 12)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("选择包含 PDF 的文件夹")
        self.source_btn = QPushButton("浏览")
        self.source_btn.setFixedWidth(56)
        self.source_btn.setCursor(Qt.PointingHandCursor)
        self.source_btn.setStyleSheet(secondary_button_style())
        self.source_btn.clicked.connect(self._browse_source)

        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.source_btn)

        self.backup_edit = QLineEdit()
        self.backup_edit.setPlaceholderText("可选，留空则自动备份")
        self.backup_btn = QPushButton("浏览")
        self.backup_btn.setFixedWidth(56)
        self.backup_btn.setCursor(Qt.PointingHandCursor)
        self.backup_btn.setStyleSheet(secondary_button_style())
        self.backup_btn.clicked.connect(self._browse_backup)

        backup_row = QHBoxLayout()
        backup_row.setSpacing(6)
        backup_row.addWidget(self.backup_edit, 1)
        backup_row.addWidget(self.backup_btn)

        for label_text in ["源目录", "备份目录"]:
            dir_layout.addWidget(QLabel(label_text, styleSheet=f"color: {TEXT_PRIMARY};"))
        dir_layout.addLayout(source_row)
        dir_layout.addLayout(backup_row)
        layout.addWidget(dir_group)

        # 扫描与识别组
        scan_group = self._create_group("扫描与识别")
        scan_layout = QGridLayout(scan_group)
        scan_layout.setSpacing(8)
        scan_layout.setContentsMargins(12, 12, 12, 12)
        scan_layout.setColumnStretch(1, 1)
        scan_layout.setColumnStretch(3, 1)

        self.keywords_edit = QTextEdit()
        self.keywords_edit.setPlaceholderText("每行一个关键词，或逗号分隔")
        self.keywords_edit.setMaximumHeight(56)
        self.keywords_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.pages_edit = QLineEdit("-1")
        self.pages_edit.setPlaceholderText("如: 2,-1")

        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND", "OR"])

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSingleStep(50)

        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, 16)
        self.max_workers_spin.setValue(4)

        self.ocr_workers_spin = QSpinBox()
        self.ocr_workers_spin.setRange(1, 8)
        self.ocr_workers_spin.setValue(2)

        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItems(OCREngineFactory.available_modes())

        self.accuracy_combo = QComboBox()
        self.accuracy_combo.addItems(["general_basic", "accurate_basic", "general", "accurate"])

        self.lang_edit = QLineEdit("chi_sim")

        labels = ["关键词", "检查页面", "搜索逻辑", "DPI",
                  "文件并发", "OCR并发", "OCR模式", "识别精度", "语言"]
        widgets = [
            (0, 0, 1, 3, QLabel(labels[0])),
            (0, 1, 1, 3, self.keywords_edit),
            (1, 0, 1, 1, QLabel(labels[1])),
            (1, 1, 1, 1, self.pages_edit),
            (1, 2, 1, 1, QLabel(labels[2])),
            (1, 3, 1, 1, self.logic_combo),
            (2, 0, 1, 1, QLabel(labels[3])),
            (2, 1, 1, 1, self.dpi_spin),
            (2, 2, 1, 1, QLabel(labels[4])),
            (2, 3, 1, 1, self.max_workers_spin),
            (3, 0, 1, 1, QLabel(labels[5])),
            (3, 1, 1, 1, self.ocr_workers_spin),
            (3, 2, 1, 1, QLabel(labels[6])),
            (3, 3, 1, 1, self.ocr_mode_combo),
            (4, 0, 1, 1, QLabel(labels[7])),
            (4, 1, 1, 1, self.accuracy_combo),
            (4, 2, 1, 1, QLabel(labels[8])),
            (4, 3, 1, 1, self.lang_edit),
        ]
        for row, col, r_span, c_span, widget in widgets:
            scan_layout.addWidget(widget, row, col, r_span, c_span)

        layout.addWidget(scan_group)

        # 选项组
        options_group = self._create_group("选项")
        options_layout = QGridLayout(options_group)
        options_layout.setSpacing(8)
        options_layout.setContentsMargins(12, 12, 12, 12)
        options_layout.setColumnStretch(0, 1)
        options_layout.setColumnStretch(1, 1)
        options_layout.setColumnStretch(2, 1)

        self.remove_copyright_cb = QCheckBox("删除版权页", checked=True)
        self.remove_blank_cb = QCheckBox("删除空白页", checked=True)
        self.case_sensitive_cb = QCheckBox("区分大小写")
        self.filter_spaces_cb = QCheckBox("过滤空格", checked=True)
        self.fuzzy_match_cb = QCheckBox("模糊匹配", checked=True)
        self.debug_cb = QCheckBox("调试模式")

        checkboxes = [
            (0, 0, self.remove_copyright_cb),
            (0, 1, self.remove_blank_cb),
            (0, 2, self.case_sensitive_cb),
            (1, 0, self.filter_spaces_cb),
            (1, 1, self.fuzzy_match_cb),
            (1, 2, self.debug_cb),
        ]
        for row, col, cb in checkboxes:
            options_layout.addWidget(cb, row, col)

        layout.addWidget(options_group)
        layout.addStretch()

        self.setWidget(container)

        # 统一应用样式
        self.setStyleSheet(
            f'QLabel {{ color: {TEXT_PRIMARY}; font-size: 13px; }}'
            + input_style()
            + combobox_style()
            + spinbox_style()
            + checkbox_style()
            + secondary_button_style()
        )

    def _create_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(group_style())
        return group

    def _browse_source(self):
        default = str(self.config.source_dir) if self.config.source_dir.exists() else ""
        path = QFileDialog.getExistingDirectory(self.window(), "选择源目录", default)
        if path:
            self.source_edit.setText(path)

    def _browse_backup(self):
        default = str(self.config.backup_dir) if self.config.backup_dir and self.config.backup_dir.exists() else ""
        path = QFileDialog.getExistingDirectory(self.window(), "选择备份目录", default)
        if path:
            self.backup_edit.setText(path)

    def load_from_config(self):
        self.source_edit.setText(str(self.config.source_dir))
        if self.config.backup_dir:
            self.backup_edit.setText(str(self.config.backup_dir))
        self.keywords_edit.setPlainText("\n".join(self.config.keywords))
        self.pages_edit.setText(self.config.pages_to_check)
        self.logic_combo.setCurrentText(self.config.search_logic)
        self.dpi_spin.setValue(self.config.dpi)
        self.max_workers_spin.setValue(self.config.max_workers)
        self.ocr_workers_spin.setValue(self.config.ocr_max_workers)
        self.ocr_mode_combo.setCurrentText(self.config.recognition_mode)
        self.accuracy_combo.setCurrentText(self.config.ocr_accuracy)
        self.lang_edit.setText(self.config.ocr_lang)
        self.remove_copyright_cb.setChecked(self.config.remove_copyright_pages)
        self.remove_blank_cb.setChecked(self.config.remove_blank_pages)
        self.case_sensitive_cb.setChecked(self.config.case_sensitive)
        self.filter_spaces_cb.setChecked(self.config.filter_spaces)
        self.fuzzy_match_cb.setChecked(self.config.fuzzy_match)
        self.debug_cb.setChecked(self.config.debug_mode)

    def save_to_config(self) -> AppConfig:
        config = AppConfig()
        config.source_dir = Path(self.source_edit.text() or ".")
        backup_text = self.backup_edit.text()
        config.backup_dir = Path(backup_text) if backup_text else None
        kw_text = self.keywords_edit.toPlainText()
        config.keywords = [k.strip() for k in kw_text.replace(",", "\n").split("\n") if k.strip()]
        config.pages_to_check = self.pages_edit.text()
        config.search_logic = self.logic_combo.currentText()
        config.dpi = self.dpi_spin.value()
        config.max_workers = self.max_workers_spin.value()
        config.ocr_max_workers = self.ocr_workers_spin.value()
        config.recognition_mode = self.ocr_mode_combo.currentText()
        config.ocr_accuracy = self.accuracy_combo.currentText()
        config.ocr_lang = self.lang_edit.text()
        config.remove_copyright_pages = self.remove_copyright_cb.isChecked()
        config.remove_blank_pages = self.remove_blank_cb.isChecked()
        config.case_sensitive = self.case_sensitive_cb.isChecked()
        config.filter_spaces = self.filter_spaces_cb.isChecked()
        config.fuzzy_match = self.fuzzy_match_cb.isChecked()
        config.debug_mode = self.debug_cb.isChecked()
        return config

    def set_readonly(self, readonly: bool):
        target_types = (QLineEdit, QTextEdit, QComboBox, QSpinBox, QCheckBox, QPushButton)
        for widget in self.findChildren(QWidget):
            if isinstance(widget, target_types):
                widget.setEnabled(not readonly)
