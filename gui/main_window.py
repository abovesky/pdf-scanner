"""
主窗口
简洁浅色主题，左侧边栏 + 右侧内容区布局
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayou,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayou,
    QWidget,
)

from core.config import AppConfig
from core.models import FileStatus
from .log_widget import LogWidget
from .result_table import ResultTable
from .scanner_worker import ScannerWorker
from .settings_panel import SettingsPanel
from .theme import (
    BG_PAGE,
    BLUE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    main_window_style,
    primary_button_style,
    secondary_button_style,
)


class MainWindow(QMainWindow):
    """PDF Scanner 主窗口 — 简洁浅色风格"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 版权页扫描工具")
        self.setMinimumSize(1280, 860)
        self.resize(1440, 920)

        self.worker: "ScannerWorker | None" = None
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayou(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ========== 左侧边栏 ==========
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(360)
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayou(self.sidebar)
        sidebar_layout.setSpacing(14)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)

        # 侧边栏标题
        title_label = QLabel("扫描设置")
        title_label.setFont(QFont("Microsoft YaHe", 14, QFont.Bold))
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        sidebar_layout.addWidget(title_label)

        # 设置面板
        self.settings_panel = SettingsPanel()
        sidebar_layout.addWidget(self.settings_panel, 1)

        # 控制按钮区（卡片）
        control_card = QFrame()
        control_card.setObjectName("card")
        control_layout = QVBoxLayou(control_card)
        control_layout.setSpacing(8)
        control_layout.setContentsMargins(14, 14, 14, 14)

        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet(primary_button_style())
        self.start_btn.clicked.connect(self._on_start)

        btn_row = QHBoxLayou()
        btn_row.setSpacing(6)

        for text in ["暂停", "继续", "停止"]:
            btn = QPushButton(text)
            btn.setFixedHeight(34)
            btn.setEnabled(False)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(secondary_button_style())
            btn_row.addWidget(btn)
            setattr(self, f"{text[0]}tn", btn)

        self.pause_btn.clicked.connect(self._on_pause)
        self.resume_btn.clicked.connect(self._on_resume)
        self.stop_btn.clicked.connect(self._on_stop)

        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.setFixedHeight(34)
        self.save_config_btn.setCursor(Qt.PointingHandCursor)
        self.save_config_btn.setStyleSheet(secondary_button_style())
        self.save_config_btn.clicked.connect(self._on_save_config)

        control_layout.addWidget(self.start_btn)
        control_layout.addLayout(btn_row)
        control_layout.addWidget(self.save_config_btn)
        sidebar_layout.addWidget(control_card)

        main_layout.addWidget(self.sidebar)

        # ========== 右侧主区域 ==========
        right_container = QWidget()
        right_layout = QVBoxLayou(right_container)
        right_layout.setSpacing(14)
        right_layout.setContentsMargins(16, 16, 16, 12)

        # 顶部工具栏
        toolbar = QHBoxLayou()
        toolbar.setSpacing(12)

        toolbar_title = QLabel("扫描结果")
        toolbar_title.setFont(QFont("Microsoft YaHe", 14, QFont.Bold))
        toolbar_title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        toolbar.addWidget(toolbar_title)
        toolbar.addStretch()

        self.current_file_label = QLabel("就绪")
        self.current_file_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        toolbar.addWidget(self.current_file_label)
        right_layout.addLayout(toolbar)

        # 结果表格卡片
        result_card = QFrame()
        result_card.setObjectName("card")
        result_layout = QVBoxLayou(result_card)
        result_layout.setContentsMargins(10, 10, 10, 10)
        self.result_table = ResultTable()
        result_layout.addWidget(self.result_table)
        right_layout.addWidget(result_card, 55)

        # 日志区域卡片
        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayou(log_card)
        log_layout.setContentsMargins(10, 10, 10, 10)
        log_header = QLabel("实时日志")
        log_header.setFont(QFont("Microsoft YaHe", 12, QFont.Bold))
        log_header.setStyleSheet(f"color: {TEXT_PRIMARY}; margin-bottom: 4px;")
        log_layout.addWidget(log_header)
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        right_layout.addWidget(log_card, 45)

        # 底部进度栏
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        right_layout.addWidget(self.progress_bar, 0)

        main_layout.addWidget(right_container, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_stats_label = QLabel("已扫描: 0 | 已修改: 0 | 失败: 0")
        self.status_stats_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.status_bar.addWidget(self.status_stats_label)
        self.setStatusBar(self.status_bar)

    def _apply_theme(self):
        self.setStyleSheet(main_window_style())

    # ---- 信号槽 ----

    def _on_start(self):
        config = self.settings_panel.save_to_config()
        errors = config.validate()
        if errors:
            QMessageBox.warning(self, "配置错误", "\n".join(errors))
            return

        self.result_table.clear()
        self.log_widget.clear_log()
        self.progress_bar.setValue(0)
        self.current_file_label.setText("准备扫描...")

        self.settings_panel.set_readonly(True)
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.save_config_btn.setEnabled(False)

        self.worker = ScannerWorker(config, parent=self)
        self.worker.log_signal.connect(self._on_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.result_signal.connect(self._on_result)
        self.worker.status_signal.connect(self._on_status)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_pause(self):
        if self.worker:
            self.worker.pause()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)

    def _on_resume(self):
        if self.worker:
            self.worker.resume()
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)

    def _on_stop(self):
        if self.worker:
            self.worker.cancel()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.current_file_label.setText("正在停止...")

    def _on_save_config(self):
        config = self.settings_panel.save_to_config()
        try:
            config.save_settings()
            QMessageBox.information(self, "成功", "配置已保存到 settings.json")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"保存配置失败: {e}")

    def _on_log(self, level: str, message: str):
        self.log_widget.append_log(level, message)

    def _on_progress(self, current: int, total: int):
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
            self.current_file_label.setText(f"进度: {current}/{total}")

    def _on_result(self, result):
        self.result_table.add_result(result)
        self._update_stats()

    def _on_status(self, status: str):
        mapping = {
            "running": "扫描中...",
            "paused": "已暂停",
            "completed": "扫描完成",
            "cancelled": "已取消",
            "error": "发生错误",
        }
        self.current_file_label.setText(mapping.get(status, status))

    def _on_finished(self):
        self.settings_panel.set_readonly(False)
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.save_config_btn.setEnabled(True)
        self.worker = None

    def _update_stats(self):
        results = self.result_table.get_results()
        scanned = len(results)
        modified = sum(1 for r in results if r.status == FileStatus.MODIFIED)
        failed = sum(1 for r in results if r.status == FileStatus.FAILED)
        self.status_stats_label.setText(
            f"已扫描: {scanned} | 已修改: {modified} | 失败: {failed}"
        )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "扫描正在进行中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self.worker.wait(3000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
