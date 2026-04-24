"""
主窗口
整合所有子组件，绑定信号槽，窗口布局管理
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
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
    """PDF Scanner 主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 版权页扫描工具")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self.worker: ScannerWorker | None = None
        self._setup_ui()
        self._apply_dark_theme()

    def _setup_ui(self):
        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 设置面板
        self.settings_panel = SettingsPanel()
        main_layout.addWidget(self.settings_panel)

        # 控制栏
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setFixedHeight(36)
        self.start_btn.setStyleSheet(self._primary_btn_style())
        self.start_btn.clicked.connect(self._on_start)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setFixedHeight(36)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause)

        self.resume_btn = QPushButton("继续")
        self.resume_btn.setFixedHeight(36)
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_resume)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFixedHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
            QPushButton:pressed {
                background-color: #B91C1C;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94A3B8;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop)

        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.setFixedHeight(36)
        self.save_config_btn.clicked.connect(self._on_save_config)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                color: #F1F5F9;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 4px;
            }
        """)

        self.current_file_label = QLabel("就绪")
        self.current_file_label.setStyleSheet("color: #94A3B8; font-size: 12px;")

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.resume_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.save_config_btn)
        control_layout.addWidget(self.progress_bar, 1)
        control_layout.addWidget(self.current_file_label)

        main_layout.addLayout(control_layout)

        # 左右分栏
        splitter = QSplitter(Qt.Horizontal)

        # 日志区域
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_header = QLabel("实时日志")
        log_header.setStyleSheet("color: #F1F5F9; font-weight: 600; font-size: 13px;")
        log_layout.addWidget(log_header)
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        splitter.addWidget(log_container)

        # 结果区域
        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_header = QLabel("扫描结果")
        result_header.setStyleSheet("color: #F1F5F9; font-weight: 600; font-size: 13px;")
        result_layout.addWidget(result_header)
        self.result_table = ResultTable()
        result_layout.addWidget(self.result_table)
        splitter.addWidget(result_container)

        splitter.setSizes([700, 500])
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #334155;
            }
        """)

        main_layout.addWidget(splitter, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #0F172A;
                color: #94A3B8;
                border-top: 1px solid #334155;
            }
        """)
        self.status_stats_label = QLabel("已扫描: 0 | 已修改: 0 | 失败: 0")
        self.status_bar.addWidget(self.status_stats_label)
        self.setStatusBar(self.status_bar)

    def _primary_btn_style(self):
        return """
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94A3B8;
            }
        """

    def _apply_dark_theme(self):
        """应用深色主题"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F172A;
            }
            QWidget {
                background-color: #0F172A;
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
