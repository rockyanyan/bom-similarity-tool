"""界面主题与样式表（深色）。"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

BG = "#0F141B"
PANEL = "#161D27"
CARD = "#1B2431"
BORDER = "#2A3646"
TEXT = "#E7EDF5"
MUTED = "#8A99AD"
ACCENT = "#4F8DFD"
ACCENT_DARK = "#3A6FD1"
GREEN = "#3DDC97"
ORANGE = "#FFB020"
RED = "#FF6B6B"
PURPLE = "#B48EFF"

TYPE_COLORS = {
    "完全匹配": "#8A99AD",
    "等价替换匹配": "#4F8DFD",
    "数量变更": "#FFB020",
    "新增物料": "#3DDC97",
    "缺失物料": "#FF6B6B",
}

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI";
    font-size: 13px;
    outline: none;
}}
QMainWindow, QWidget#Root {{
    background: {BG};
    color: {TEXT};
}}
QWidget {{
    color: {TEXT};
}}
QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: #FFFFFF;
}}
QLabel#PageSubtitle, QLabel#Muted {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 700;
    color: #FFFFFF;
}}
QLabel#StatValue {{
    font-size: 24px;
    font-weight: 700;
    color: #FFFFFF;
}}
QLabel#ScoreValue {{
    font-size: 46px;
    font-weight: 800;
    color: {ACCENT};
}}
QFrame#Sidebar {{
    background: {PANEL};
    border-right: 1px solid {BORDER};
}}
QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#TopBar {{
    background: {BG};
    border-bottom: 1px solid {BORDER};
}}
QPushButton {{
    background: #232E3E;
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    min-height: 18px;
}}
QPushButton:hover {{
    background: #2B394C;
    border-color: #3B4B61;
}}
QPushButton:pressed {{
    background: #1C2634;
}}
QPushButton:disabled {{
    color: #5B6878;
    background: #1A222E;
    border-color: #232D3B;
}}
QPushButton[kind="primary"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #FFFFFF;
    font-weight: 700;
}}
QPushButton[kind="primary"]:hover {{
    background: #6A9EFE;
    border-color: #6A9EFE;
}}
QPushButton[kind="primary"]:disabled {{
    background: #2C4468;
    border-color: #2C4468;
    color: #7E93AE;
}}
QPushButton[kind="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
    padding: 5px 10px;
}}
QPushButton[kind="ghost"]:hover {{
    background: #232E3E;
    color: {TEXT};
}}
QPushButton[kind="danger"] {{
    background: transparent;
    border: 1px solid #5A3038;
    color: {RED};
}}
QPushButton[kind="danger"]:hover {{
    background: #3A1F26;
}}
QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-radius: 9px;
    color: {MUTED};
    text-align: left;
    padding: 10px 14px;
    font-size: 14px;
}}
QPushButton#NavButton:hover {{
    background: #1E2735;
    color: {TEXT};
}}
QPushButton#NavButton:checked {{
    background: #223250;
    color: #FFFFFF;
    font-weight: 700;
    border-left: 3px solid {ACCENT};
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
    background: #121A24;
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 9px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: #5B6878;
    background: #151C26;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {MUTED};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: #18212D;
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    color: {TEXT};
    outline: none;
}}
QCheckBox, QRadioButton {{
    spacing: 7px;
    color: {TEXT};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid #3B4B61;
    background: #121A24;
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QTableWidget, QTableView {{
    background: #121A24;
    alternate-background-color: #151E29;
    gridline-color: #202B39;
    border: 1px solid {BORDER};
    border-radius: 9px;
    color: {TEXT};
    selection-background-color: #26406B;
    selection-color: #FFFFFF;
}}
QTableWidget::item {{
    padding: 5px 6px;
    border: none;
}}
QHeaderView::section {{
    background: #1A2431;
    color: {MUTED};
    border: none;
    border-right: 1px solid #222E3D;
    border-bottom: 1px solid {BORDER};
    padding: 8px 6px;
    font-weight: 700;
}}
QTableCornerButton::section {{
    background: #1A2431;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #33415A;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #445570;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #33415A;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QProgressBar {{
    background: #121A24;
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    color: {TEXT};
    height: 8px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 5px;
}}
QSplitter::handle {{
    background: transparent;
    width: 10px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {CARD};
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: #FFFFFF;
    border-bottom: 2px solid {ACCENT};
}}
QDialog {{
    background: {BG};
}}
QToolTip {{
    background: #1F2A39;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px;
}}
QMenu {{
    background: #18212D;
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {ACCENT};
}}
"""


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(BG))
    palette.setColor(palette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(palette.ColorRole.Base, QColor("#121A24"))
    palette.setColor(palette.ColorRole.Text, QColor(TEXT))
    palette.setColor(palette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(palette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyleSheet(QSS)
