"""
扫描结果列表组件
QTableView + 自定义模型
"""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

from core.models import FileStatus, ScanResult


class ResultTableModel(QAbstractTableModel):
    """结果表格模型"""

    HEADERS = ["文件名", "状态", "版权页", "空白页", "总页数", "耗时", "详情"]

    STATUS_COLORS = {
        FileStatus.MODIFIED: QColor("#10B981"),
        FileStatus.UNMODIFIED: QColor("#94A3B8"),
        FileStatus.FAILED: QColor("#EF4444"),
        FileStatus.SKIPPED: QColor("#F59E0B"),
    }

    STATUS_LABELS = {
        FileStatus.MODIFIED: "已修改",
        FileStatus.UNMODIFIED: "未修改",
        FileStatus.FAILED: "失败",
        FileStatus.SKIPPED: "已跳过",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[ScanResult] = []

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
            if col == 0:
                return result.file_name
            elif col == 1:
                return self.STATUS_LABELS.get(result.status, result.status)
            elif col == 2:
                return str(result.copyright_pages) if result.copyright_pages else "-"
            elif col == 3:
                return str(result.blank_pages_removed) if result.blank_pages_removed else "-"
            elif col == 4:
                return str(result.total_pages) if result.total_pages else "-"
            elif col == 5:
                return f"{result.elapsed_seconds}s" if result.elapsed_seconds else "-"
            elif col == 6:
                return result.message

        if role == Qt.ForegroundRole and col == 1:
            return self.STATUS_COLORS.get(result.status, QColor("#F1F5F9"))

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

        self.table_view = QTableView(self)
        self.model = ResultTableModel(self)
        self.table_view.setModel(self.model)

        self.table_view.setStyleSheet("""
            QTableView {
                background-color: #1E293B;
                color: #F1F5F9;
                border: 1px solid #334155;
                border-radius: 6px;
                gridline-color: #334155;
            }
            QTableView::item {
                padding: 6px;
                border-bottom: 1px solid #334155;
            }
            QTableView::item:selected {
                background-color: #2563EB;
            }
            QHeaderView::section {
                background-color: #334155;
                color: #F1F5F9;
                padding: 8px;
                border: none;
                font-weight: 600;
            }
        """)

        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)

        layout.addWidget(self.table_view)

    def add_result(self, result: ScanResult):
        self.model.add_result(result)

    def clear(self):
        self.model.clear()

    def get_results(self) -> list[ScanResult]:
        return self.model._results[:]
