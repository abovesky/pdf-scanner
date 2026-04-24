"""
扫描结果列表组件 — 简洁浅色风格
"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

from core.models import FileStatus, ScanResult
from .theme import (
    STATUS_GREEN,
    STATUS_GRAY,
    STATUS_RED,
    STATUS_YELLOW,
    table_style,
)


class ResultTableModel(QAbstractTableModel):
    """结果表格模型"""

    HEADERS = ["文件名", "状态", "版权页", "空白页", "总页数", "耗时", "详情"]

    STATUS_COLORS = {
        FileStatus.MODIFIED: QColor(STATUS_GREEN),
        FileStatus.UNMODIFIED: QColor(STATUS_GRAY),
        FileStatus.FAILED: QColor(STATUS_RED),
        FileStatus.SKIPPED: QColor(STATUS_YELLOW),
    }

    STATUS_LABELS = {
        FileStatus.MODIFIED: "已修改",
        FileStatus.UNMODIFIED: "未修改",
        FileStatus.FAILED: "失败",
        FileStatus.SKIPPED: "已跳过",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: "list[ScanResult]" = []

    def add_result(self, result: ScanResult):
        self.beginInsertRows(QModelIndex(), len(self._results), len(self._results))
        self._results.append(result)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self._results.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._results)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._results):
            return None

        result = self._results[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            return {
                0: result.file_name,
                1: self.STATUS_LABELS.get(result.status, result.status),
                2: str(result.copyright_pages) if result.copyright_pages else "-",
                3: str(result.blank_pages_removed) if result.blank_pages_removed else "-",
                4: str(result.total_pages) if result.total_pages else "-",
                5: f"{result.elapsed_seconds}s" if result.elapsed_seconds else "-",
                6: result.message,
            }.get(col)

        if role == Qt.ForegroundRole and col == 1:
            return self.STATUS_COLORS.get(result.status, QColor("#111827"))

        if role == Qt.TextAlignmentRole:
            if col in (2, 3, 4, 5):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None


class ResultTable(QWidget):
    """扫描结果列表组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.table_view = QTableView(self)
        self.model = ResultTableModel(self)
        self.table_view.setModel(self.model)

        self.table_view.setStyleSheet(table_style())
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.horizontalHeader().setDefaultSectionSize(90)
        self.table_view.horizontalHeader().setMinimumSectionSize(60)
        self.table_view.setColumnWidth(0, 320)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setShowGrid(False)

        layout.addWidget(self.table_view)

    def add_result(self, result: ScanResult):
        self.model.add_result(result)

    def clear(self):
        self.model.clear()

    def get_results(self) -> "list[ScanResult]":
        return self.model._results[:]
