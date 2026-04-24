"""
GUI 主题配置 — 简洁现代风格
"""

# ============================================================
# 配色方案（简洁克制）
# ============================================================

# 背景
BG_PAGE = "#F5F7FA"       # 页面主背景（浅灰蓝）
BG_CARD = "#FFFFFF"        # 卡片/弹窗背景（纯白）
BG_INPUT = "#FFFFFF"       # 输入框背景（纯白，聚焦时变色）

# 边框
BORDER = "#E5E7EB"         # 标准边框（浅灰）
BORDER_FOCUS = "#3B82F6"  # 聚焦边框（蓝色-500）

# 文字
TEXT_PRIMARY = "#111827"    # 主要文字（近黑）
TEXT_SECONDARY = "#6B7280"  # 次要文字（中灰）
TEXT_PLACEHOLDER = "#9CA3AF"  # 占位符（浅灰）
TEXT_DISABLED = "#9CA3AF"   # 禁用文字
TEXT_ON_BLUE = "#FFFFFF"   # 蓝色按钮上的文字（白色）

# 蓝色系（主强调色，只用这一个蓝）
BLUE = "#3B82F6"           # 主蓝（blue-500）
BLUE_HOVER = "#2563EB"     # 悬停（blue-600）
BLUE_ACTIVE = "#1D4ED8"    # 按下（blue-700）
BLUE_LIGHT = "#EFF6FF"     # 浅蓝背景（blue-50）
BLUE_BORDER = "#BFDBFE"     # 浅蓝边框（blue-200）
BLUE_SELECT = "#DBEAFE"     # 选中背景（blue-100）

# 灰色系（次要按钮/禁用状态）
GRAY_BG = "#F9FAFB"        # 次要按钮背景
GRAY_BORDER = "#D1D5DB"    # 次要按钮边框
GRAY_HOVER = "#F3F4F6"    # 次要按钮悬停
GRAY_ACTIVE = "#E5E7EB"     # 次要按钮按下
GRAY_DISABLED_BG = "#F3F4F6"  # 禁用背景

# 状态色
STATUS_GREEN = "#059669"     # 成功（emerald-600）
STATUS_YELLOW = "#D97706"   # 警告（amber-600）
STATUS_RED = "#DC2626"       # 错误（red-600）
STATUS_GRAY = "#6B7280"      # 信息/跳过（gray-500）

# 表格
TABLE_HEADER_BG = "#F9FAFB"  # 表头背景
TABLE_HEADER_TEXT = "#374151"  # 表头文字
TABLE_GRID = "#F3F4F6"      # 网格线
TABLE_ALT = "#FAFAFA"        # 交替行


# ============================================================
# 尺寸
# ============================================================

RADIUS = 6         # 标准圆角
RADIUS_SMALL = 4   # 小圆角
BTN_HEIGHT = 36     # 标准按钮高度
BTN_HEIGHT_LARGE = 40  # 主按钮高度
INPUT_HEIGHT = 34    # 输入框高度（原来是 28，太矮）


# ============================================================
# 样式生成函数
# ============================================================

def main_window_style():
    return f"""
        QMainWindow {{
            background-color: {BG_PAGE};
        }}
        QLabel {{
            background: transparent;
        }}
        #sidebar {{
            background-color: {BG_CARD};
            border-right: 1px solid {BORDER};
        }}
        #card {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: {RADIUS + 2}px;
        }}
        QProgressBar {{
            background-color: {BG_PAGE};
            border: none;
            border-radius: 3px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {BLUE};
            border-radius: 3px;
        }}
        QStatusBar {{
            background-color: {BG_CARD};
            color: {TEXT_SECONDARY};
            border-top: 1px solid {BORDER};
            font-size: 12px;
        }}
    """


def input_style():
    """QLineEdit / QTextEdit 通用样式"""
    return f"""
        QLineEdit, QTextEdit {{
            background-color: {BG_INPUT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS}px;
            padding: 6px 10px;
            font-size: 13px;
            selection-background-color: {BLUE_SELECT};
        }}
        QLineEdit:hover, QTextEdit:hover {{
            border: 1px solid {GRAY_BORDER};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {BORDER_FOCUS};
        }}
        QLineEdit:disabled, QTextEdit:disabled {{
            background-color: {GRAY_DISABLED_BG};
            color: {TEXT_PLACEHOLDER};
            border-color: {BORDER};
        }}
        QLineEdit::placeholder, QTextEdit::placeholder {{
            color: {TEXT_PLACEHOLDER};
        }}
    """


def combobox_style():
    """QComboBox 样式"""
    return f"""
        QComboBox {{
            background-color: {BG_INPUT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS}px;
            padding: 5px 28px 5px 10px;
            min-height: {INPUT_HEIGHT}px;
            font-size: 13px;
            combobox-popup: 0;
        }}
        QComboBox:hover {{
            border: 1px solid {GRAY_BORDER};
        }}
        QComboBox:focus {{
            border: 1px solid {BORDER_FOCUS};
        }}
        QComboBox:disabled {{
            background-color: {GRAY_DISABLED_BG};
            color: {TEXT_PLACEHOLDER};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 28px;
            border: none;
            background: transparent;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {TEXT_PLACEHOLDER};
            margin-right: 8px;
        }}
        QComboBox:hover::down-arrow {{
            border-top-color: {BLUE};
        }}
        QComboBox QAbstractItemView {{
            background-color: {BG_CARD};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_FOCUS};
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 7px 12px;
            min-height: 18px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {BLUE_LIGHT};
            color: {BLUE};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {BLUE_SELECT};
            color: {BLUE_HOVER};
        }}
    """


def spinbox_style():
    """QSpinBox 样式"""
    return f"""
        QSpinBox {{
            background-color: {BG_INPUT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS}px;
            padding: 4px 24px 4px 10px;
            min-height: {INPUT_HEIGHT}px;
            font-size: 13px;
        }}
        QSpinBox:hover {{
            border: 1px solid {GRAY_BORDER};
        }}
        QSpinBox:focus {{
            border: 1px solid {BORDER_FOCUS};
        }}
        QSpinBox:disabled {{
            background-color: {GRAY_DISABLED_BG};
            color: {TEXT_PLACEHOLDER};
        }}
        QSpinBox::up-button {{
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 22px;
            border: none;
            background: transparent;
        }}
        QSpinBox::down-button {{
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 22px;
            border: none;
            background: transparent;
        }}
        QSpinBox::up-arrow, QSpinBox::down-arrow {{
            image: none;
            width: 0;
            height: 0;
        }}
        QSpinBox::up-arrow {{
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {TEXT_PLACEHOLDER};
        }}
        QSpinBox::down-arrow {{
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {TEXT_PLACEHOLDER};
        }}
        QSpinBox::up-button:hover::up-arrow {{
            border-bottom-color: {BLUE};
        }}
        QSpinBox::down-button:hover::down-arrow {{
            border-top-color: {BLUE};
        }}
    """


def checkbox_style():
    """QCheckBox 样式"""
    return f"""
        QCheckBox {{
            color: {TEXT_PRIMARY};
            font-size: 13px;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: {RADIUS_SMALL}px;
            border: 1.5px solid {GRAY_BORDER};
            background-color: {BG_CARD};
        }}
        QCheckBox::indicator:checked {{
            background-color: {BLUE};
            border: 1.5px solid {BLUE};
        }}
        QCheckBox::indicator:disabled {{
            background-color: {GRAY_DISABLED_BG};
            border-color: {BORDER};
        }}
    """


def primary_button_style():
    """主按钮（蓝色）"""
    return f"""
        QPushButton {{
            background-color: {BLUE};
            color: {TEXT_ON_BLUE};
            border: none;
            border-radius: {RADIUS}px;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {BLUE_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {BLUE_ACTIVE};
        }}
        QPushButton:disabled {{
            background-color: {GRAY_DISABLED_BG};
            color: {TEXT_PLACEHOLDER};
        }}
    """


def secondary_button_style():
    """次要按钮（灰色边框）"""
    return f"""
        QPushButton {{
            background-color: {BG_CARD};
            color: {TEXT_PRIMARY};
            border: 1px solid {GRAY_BORDER};
            border-radius: {RADIUS}px;
            padding: 5px 14px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {GRAY_HOVER};
            border-color: {GRAY_BORDER};
        }}
        QPushButton:pressed {{
            background-color: {GRAY_ACTIVE};
        }}
        QPushButton:disabled {{
            background-color: {GRAY_DISABLED_BG};
            color: {TEXT_PLACEHOLDER};
            border-color: {BORDER};
        }}
    """


def group_style():
    """QGroupBox 样式"""
    return f"""
        QGroupBox {{
            color: {TEXT_PRIMARY};
            font-weight: 600;
            font-size: 13px;
            border: 1px solid {BORDER};
            border-radius: {RADIUS + 2}px;
            margin-top: 10px;
            padding-top: 6px;
            background-color: {BG_CARD};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: {TEXT_PRIMARY};
        }}
    """


def table_style():
    """QTableView 样式"""
    return f"""
        QTableView {{
            background-color: {BG_CARD};
            color: {TEXT_PRIMARY};
            border: none;
            border-radius: {RADIUS + 2}px;
            gridline-color: {TABLE_GRID};
            outline: none;
            font-size: 13px;
        }}
        QTableView::item {{
            padding: 8px 10px;
            border-bottom: 1px solid {TABLE_GRID};
        }}
        QTableView::item:selected {{
            background-color: {BLUE_SELECT};
            color: {TEXT_PRIMARY};
        }}
        QTableView::item:alternate {{
            background-color: {TABLE_ALT};
        }}
        QHeaderView::section {{
            background-color: {TABLE_HEADER_BG};
            color: {TABLE_HEADER_TEXT};
            padding: 10px;
            border: none;
            border-bottom: 2px solid {BORDER};
            font-weight: 600;
            font-size: 13px;
        }}
        QHeaderView::section:first {{
            border-top-left-radius: {RADIUS + 2}px;
        }}
        QHeaderView::section:last {{
            border-top-right-radius: {RADIUS + 2}px;
        }}
    """


def log_style():
    """日志 QTextEdit 样式"""
    return f"""
        QTextEdit {{
            background-color: #FAFBFC;
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER};
            border-radius: {RADIUS + 2}px;
            padding: 10px;
            font-size: 12px;
            line-height: 1.6;
        }}
    """
