"""通用界面组件。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .theme import ACCENT, MUTED, PANEL, RED, TEXT


def button(text: str, kind: str = "", tooltip: str = "") -> QPushButton:
    btn = QPushButton(text)
    if kind:
        btn.setProperty("kind", kind)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    return btn


class Card(QFrame):
    """带标题的卡片容器。"""

    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(16, 14, 16, 14)
        self.outer.setSpacing(10)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            self.header.addWidget(label)
            self.title_label = label
        else:
            self.title_label = None
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Muted")
            self.header.addWidget(sub)
            self.subtitle_label = sub
        else:
            self.subtitle_label = None
        self.header.addStretch(1)
        if title or subtitle:
            self.outer.addLayout(self.header)
        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self.outer.addLayout(self.body, 1)

    def add(self, widget: QWidget):
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self.body.addLayout(layout)
        return layout

    def add_header_widget(self, widget: QWidget):
        self.header.addWidget(widget)
        return widget

    def set_subtitle(self, text: str):
        if self.subtitle_label:
            self.subtitle_label.setText(text)


def make_table(headers: list[str], widths: list[int] | None = None,
               stretch_last: bool = True) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.verticalHeader().setDefaultSectionSize(30)
    if widths:
        for idx, width in enumerate(widths):
            if idx < len(headers):
                table.setColumnWidth(idx, width)
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    return table


def table_item(text, color: str | None = None, bold: bool = False,
               align=Qt.AlignLeft | Qt.AlignVCenter, bg: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem("" if text is None else str(text))
    item.setTextAlignment(align)
    if color:
        item.setForeground(QColor(color))
    if bg:
        item.setBackground(QColor(bg))
    if bold:
        font = QFont("Microsoft YaHei UI", 9)
        font.setBold(True)
        item.setFont(font)
    return item


def fill_table(table: QTableWidget, rows: list[list], colors: list[str | None] | None = None,
               bold_rows: set[int] | None = None, aligns: dict | None = None):
    table.setUpdatesEnabled(False)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table_item(
                value,
                color=(colors[r] if colors else None),
                bold=bool(bold_rows and r in bold_rows),
                align=(aligns or {}).get(c, Qt.AlignLeft | Qt.AlignVCenter),
            )
            table.setItem(r, c, cell)
    table.setUpdatesEnabled(True)


def card_stat(title: str, value: str, color: str = TEXT, note: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(2)
    caption = QLabel(title)
    caption.setObjectName("Muted")
    value_label = QLabel(value)
    value_label.setObjectName("StatValue")
    value_label.setStyleSheet(f"color: {color};")
    layout.addWidget(caption)
    layout.addWidget(value_label)
    if note:
        note_label = QLabel(note)
        note_label.setObjectName("Muted")
        layout.addWidget(note_label)
    frame.value_label = value_label
    return frame


def open_in_explorer(path: str):
    target = Path(path)
    folder = target if target.is_dir() else target.parent
    if not folder.exists():
        return
    if sys.platform.startswith("win"):
        if target.is_file():
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            os.startfile(str(folder))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])


def divider() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("background: #2A3646; border: none;")
    return line


def chip(text: str, color: str = ACCENT) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {color}; background: rgba(79,141,253,0.12);"
        f"border: 1px solid {color}; border-radius: 9px; padding: 2px 9px; font-size: 11px;"
    )
    return label
