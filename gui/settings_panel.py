"""
设置面板组件
包含所有扫描参数的输入控件
"""
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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import AppConfig
from core.ocr_engines import OCREngineFactory


class SettingsPanel(QWidget):
    """参数设置面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self._setup_ui()
        self.load_from_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 目录设置组
        dir_group = QGroupBox("目录设置")
        dir_group.setStyleSheet(self._group_style())
        dir_layout = QGridLayout(dir_group)

        self.source_edit = QLineEdit()
        self.source_btn = QPushButton("浏览...")
        self.source_btn.setFixedWidth(70)
        self.source_btn.clicked.connect(self._browse_source)

        self.backup_edit = QLineEdit()
        self.backup_btn = QPushButton("浏览...")
        self.backup_btn.setFixedWidth(70)
        self.backup_btn.clicked.connect(self._browse_backup)

        dir_layout.addWidget(QLabel("源目录:"), 0, 0)
        dir_layout.addWidget(self.source_edit, 0, 1)
        dir_layout.addWidget(self.source_btn, 0, 2)
        dir_layout.addWidget(QLabel("备份目录:"), 1, 0)
        dir_layout.addWidget(self.backup_edit, 1, 1)
        dir_layout.addWidget(self.backup_btn, 1, 2)

        layout.addWidget(dir_group)

        # 扫描参数组
        scan_group = QGroupBox("扫描参数")
        scan_group.setStyleSheet(self._group_style())
        scan_layout = QGridLayout(scan_group)

        self.keywords_edit = QTextEdit()
        self.keywords_edit.setPlaceholderText("每行一个关键词，或逗号分隔")
        self.keywords_edit.setMaximumHeight(60)

        self.pages_edit = QLineEdit("-1")
        self.pages_edit.setPlaceholderText("如: 2,-1 或 2:5")

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

        scan_layout.addWidget(QLabel("关键词:"), 0, 0, Qt.AlignTop)
        scan_layout.addWidget(self.keywords_edit, 0, 1, 1, 3)
        scan_layout.addWidget(QLabel("检查页面:"), 1, 0)
        scan_layout.addWidget(self.pages_edit, 1, 1)
        scan_layout.addWidget(QLabel("搜索逻辑:"), 1, 2)
        scan_layout.addWidget(self.logic_combo, 1, 3)
        scan_layout.addWidget(QLabel("DPI:"), 2, 0)
        scan_layout.addWidget(self.dpi_spin, 2, 1)
        scan_layout.addWidget(QLabel("文件并发:"), 2, 2)
        scan_layout.addWidget(self.max_workers_spin, 2, 3)
        scan_layout.addWidget(QLabel("OCR并发:"), 3, 0)
        scan_layout.addWidget(self.ocr_workers_spin, 3, 1)

        layout.addWidget(scan_group)

        # OCR 设置组
        ocr_group = QGroupBox("OCR 设置")
        ocr_group.setStyleSheet(self._group_style())
        ocr_layout = QGridLayout(ocr_group)

        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItems(OCREngineFactory.available_modes())

        self.accuracy_combo = QComboBox()
        self.accuracy_combo.addItems(["general_basic", "accurate_basic", "general", "accurate"])

        self.lang_edit = QLineEdit("chi_sim")

        ocr_layout.addWidget(QLabel("OCR模式:"), 0, 0)
        ocr_layout.addWidget(self.ocr_mode_combo, 0, 1)
        ocr_layout.addWidget(QLabel("识别精度:"), 0, 2)
        ocr_layout.addWidget(self.accuracy_combo, 0, 3)
        ocr_layout.addWidget(QLabel("语言:"), 1, 0)
        ocr_layout.addWidget(self.lang_edit, 1, 1)

        layout.addWidget(ocr_group)

        # 选项组
        options_group = QGroupBox("选项")
        options_group.setStyleSheet(self._group_style())
        options_layout = QHBoxLayout(options_group)

        self.remove_copyright_cb = QCheckBox("删除版权页")
        self.remove_copyright_cb.setChecked(True)
        self.remove_blank_cb = QCheckBox("删除空白页")
        self.remove_blank_cb.setChecked(True)
        self.case_sensitive_cb = QCheckBox("区分大小写")
        self.filter_spaces_cb = QCheckBox("过滤空格")
        self.filter_spaces_cb.setChecked(True)
        self.fuzzy_match_cb = QCheckBox("模糊匹配")
        self.fuzzy_match_cb.setChecked(True)
        self.debug_cb = QCheckBox("调试模式")

        options_layout.addWidget(self.remove_copyright_cb)
        options_layout.addWidget(self.remove_blank_cb)
        options_layout.addWidget(self.case_sensitive_cb)
        options_layout.addWidget(self.filter_spaces_cb)
        options_layout.addWidget(self.fuzzy_match_cb)
        options_layout.addWidget(self.debug_cb)
        options_layout.addStretch()

        layout.addWidget(options_group)
        layout.addStretch()

        # 设置整体样式
        self.setStyleSheet("""
            QLabel {
                color: #F1F5F9;
                font-size: 12px;
            }
            QLineEdit, QComboBox, QSpinBox, QTextEdit {
                background-color: #1E293B;
                color: #F1F5F9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {
                border: 1px solid #3B82F6;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                color: #F1F5F9;
                border: 1px solid #334155;
                selection-background-color: #2563EB;
            }
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QCheckBox {
                color: #F1F5F9;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #334155;
                background-color: #1E293B;
            }
            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                border: 1px solid #3B82F6;
            }
        """)

    def _group_style(self):
        return """
            QGroupBox {
                color: #F1F5F9;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """

    def _browse_source(self):
        path = QFileDialog.getExistingDirectory(self, "选择源目录", str(self.config.source_dir))
        if path:
            self.source_edit.setText(path)

    def _browse_backup(self):
        path = QFileDialog.getExistingDirectory(self, "选择备份目录")
        if path:
            self.backup_edit.setText(path)

    def load_from_config(self):
        """从当前配置加载到 UI"""
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
        """从 UI 保存到配置对象"""
        config = AppConfig()
        config.source_dir = Path(self.source_edit.text() or ".")
        backup_text = self.backup_edit.text()
        config.backup_dir = Path(backup_text) if backup_text else None

        # 解析关键词
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
        """设置所有控件只读状态"""
        for widget in self.findChildren((QLineEdit, QTextEdit, QComboBox, QSpinBox, QCheckBox, QPushButton)):
            if isinstance(widget, QPushButton):
                widget.setEnabled(not readonly)
            else:
                widget.setEnabled(not readonly)
