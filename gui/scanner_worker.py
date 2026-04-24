"""
Scanner 工作线程
继承 QThread，包装 core.scanner，发射 Qt 信号与 GUI 通信
"""
import threading

from PySide6.QtCore import QThread, Signal

from core.config import AppConfig
from core.models import ScanResult
from core.scanner import PDFScanner


class ScannerWorker(QThread):
    """扫描后台工作线程"""

    # 信号定义
    log_signal = Signal(str, str)           # level, message
    progress_signal = Signal(int, int)      # current, total
    result_signal = Signal(object)          # ScanResult
    status_signal = Signal(str)             # running/paused/completed/cancelled/error
    current_file_signal = Signal(str)       # 当前处理的文件名
    finished_signal = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()
        self._scanner: PDFScanner | None = None

    def pause(self):
        """暂停扫描"""
        self.pause_event.set()
        self.status_signal.emit("paused")

    def resume(self):
        """继续扫描"""
        self.pause_event.clear()
        self.status_signal.emit("running")

    def cancel(self):
        """取消扫描"""
        self.cancel_event.set()
        self.status_signal.emit("cancelled")

    def is_paused(self) -> bool:
        return self.pause_event.is_set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def run(self):
        """线程主循环"""
        self.status_signal.emit("running")
        self.cancel_event.clear()
        self.pause_event.clear()

        try:
            self._scanner = PDFScanner(
                config=self.config,
                pause_event=self.pause_event,
                cancel_event=self.cancel_event,
            )

            # 绑定回调到信号
            self._scanner.log_callback = lambda level, msg: self.log_signal.emit(level, msg)
            self._scanner.progress_callback = lambda cur, tot: self.progress_signal.emit(cur, tot)
            self._scanner.result_callback = lambda result: self.result_signal.emit(result)

            results = self._scanner.run()

            if self.cancel_event.is_set():
                self.status_signal.emit("cancelled")
            else:
                self.status_signal.emit("completed")

        except Exception as e:
            self.log_signal.emit("error", f"扫描器异常: {e}")
            self.status_signal.emit("error")
        finally:
            self.finished_signal.emit()
