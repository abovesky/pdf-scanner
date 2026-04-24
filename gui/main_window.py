"""
主窗口
现代化浅色主题，左侧边栏 + 右侧内容区布局
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.config import AppConfig
from core.models import FileStatus
from .log_widget import LogWidget
from .result_table import ResultTable
from .scanner_worker import ScannerWorker
from .settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    """PDF Scanner 主窗口 — 浅色现代风格"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 版权页扫描工具")
        self.setMinimumSize(1280, 860)
        self.resize(1440, 920)

        self.worker: ScannerWorker | None = None
        self._setup_ui()
        self._apply_light_theme()

    def _setup_ui(self):
        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ========== 左侧边栏 ==========
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(340)
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setSpacing(16)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)

        # 侧边栏标题
        title_label = QLabel("扫描设置")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setStyleSheet("color: #1E293B; margin-bottom: 4px;")
        sidebar_layout.addWidget(title_label)

        subtitle = QLabel("配置扫描参数与 OCR 选项")
        subtitle.setStyleSheet("color: #64748B; font-size: 12px; margin-bottom: 8px;")
        sidebar_layout.addWidget(subtitle)

        # 设置面板（可滚动内部处理）
        self.settings_panel = SettingsPanel()
        sidebar_layout.addWidget(self.settings_panel, 1)

        # 控制按钮区
        control_card = QFrame()
        control_card.setObjectName("card")
        control_layout = QVBoxLayout(control_card)
        control_layout.setSpacing(10)
        control_layout.setContentsMargins(16, 16, 16, 16)

        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setFixedHeight(36)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self._on_pause)

        self.resume_btn = QPushButton("继续")
        self.resume_btn.setFixedHeight(36)
        self.resume_btn.setEnabled(False)
        self.resume_btn.setCursor(Qt.PointingHandCursor)
        self.resume_btn.clicked.connect(self._on_resume)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self._on_stop)

        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.resume_btn)
        btn_row.addWidget(self.stop_btn)

        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.setFixedHeight(36)
        self.save_config_btn.setCursor(Qt.PointingHandCursor)
        self.save_config_btn.clicked.connect(self._on_save_config)

        control_layout.addWidget(self.start_btn)
        control_layout.addLayout(btn_row)
        control_layout.addWidget(self.save_config_btn)
        sidebar_layout.addWidget(control_card)

        main_layout.addWidget(self.sidebar)

        # ========== 右侧主区域 ==========
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(16)
        right_layout.setContentsMargins(20, 20, 20, 16)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        toolbar_title = QLabel("扫描结果")
        toolbar_title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        toolbar_title.setStyleSheet("color: #1E293B;")
        toolbar.addWidget(toolbar_title)

        toolbar.addStretch()

        self.current_file_label = QLabel("就绪")
        self.current_file_label.setStyleSheet("color: #64748B; font-size: 12px;")
        toolbar.addWidget(self.current_file_label)
        right_layout.addLayout(toolbar)

        # 结果表格卡片
        result_card = QFrame()
        result_card.setObjectName("card")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(12, 12, 12, 12)
        self.result_table = ResultTable()
        result_layout.addWidget(self.result_table)
        right_layout.addWidget(result_card, 55)

        # 日志区域卡片
        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_header = QLabel("实时日志")
        log_header.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        log_header.setStyleSheet("color: #1E293B; margin-bottom: 4px;")
        log_layout.addWidget(log_header)
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        right_layout.addWidget(log_card, 45)

        # 底部进度栏
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)

        bottom_bar.addWidget(self.progress_bar, 1)
        right_layout.addLayout(bottom_bar)

        main_layout.addWidget(right_container, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_stats_label = QLabel("已扫描: 0 | 已修改: 0 | 失败: 0")
        self.status_stats_label.setStyleSheet("color: #64748B; font-size: 12px;")
        self.status_bar.addWidget(self.status_stats_label)
        self.setStatusBar(self.status_bar)

    def _apply_light_theme(self):
        """应用浅色现代主题"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F1F5F9;
            }
            QLabel {
                background: transparent;
            }
            #sidebar {
                background-color: #FFFFFF;
                border-right: 1px solid #E2E8F0;
            }
            #card {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
            }
            QPushButton:disabled {
                background-color: #CBD5E1;
                color: #94A3B8;
            }
            QProgressBar {
                background-color: #E2E8F0;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 4px;
            }
            QMessageBox {
                background-color: #FFFFFF;
            }
            QStatusBar {
                background-color: #FFFFFF;
                color: #64748B;
                border-top: 1px solid #E2E8F0;
            }
        """)

    def _on_start(self):
        """开始扫描"""
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
        """暂停扫描"""
        if self.worker:
            self.worker.pause()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)

    def _on_resume(self):
        """继续扫描"""
        if self.worker:
            self.worker.resume()
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)

    def _on_stop(self):
        """停止扫描"""
        if self.worker:
            self.worker.cancel()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.current_file_label.setText("正在停止...")

    def _on_save_config(self):
        """保存配置"""
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
            percent = int(current / total * 100)
            self.progress_bar.setValue(percent)
            self.current_file_label.setText(f"进度: {current}/{total}")

    def _on_result(self, result):
        self.result_table.add_result(result)
        self._update_stats()

    def _on_status(self, status: str):
        status_map = {
            "running": "扫描中...",
            "paused": "已暂停",
            "completed": "扫描完成",
            "cancelled": "已取消",
            "error": "发生错误",
        }
        self.current_file_label.setText(status_map.get(status, status))

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
        self.status_stats_label.setText(f"已扫描: {scanned} | 已修改: {modified} | 失败: {failed}")

    def closeEvent(self, event):
        """关闭窗口时安全停止扫描"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认退出",
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
