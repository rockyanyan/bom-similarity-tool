"""主窗口与导航。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.db import DB_PATH
from .common import button, open_in_explorer
from .page_alt import AltGroupPage
from .page_compare import ComparePage
from .page_import import ImportPage
from .page_library import LibraryPage
from .page_settings import SettingsPage
from .theme import ACCENT, MUTED

NAV_ITEMS = [
    ("library", "方案库"),
    ("import", "导入 BOM"),
    ("compare", "相似度对比"),
    ("alt", "替代物料组"),
    ("settings", "参数设置"),
]


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("BOM 相似度对比工具")
        self.resize(1460, 920)
        self.setMinimumSize(1180, 740)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.library_page = LibraryPage(db, self)
        self.import_page = ImportPage(db, self)
        self.compare_page = ComparePage(db, self)
        self.alt_page = AltGroupPage(db, self)
        self.settings_page = SettingsPage(db, self)
        self.pages = {
            "library": self.library_page,
            "import": self.import_page,
            "compare": self.compare_page,
            "alt": self.alt_page,
            "settings": self.settings_page,
        }
        for key, _ in NAV_ITEMS:
            self.stack.addWidget(self.pages[key])
        content_layout.addWidget(self.stack, 1)
        layout.addWidget(content, 1)

        status = self.statusBar()
        status.setStyleSheet(
            f"background: #121A24; color: {MUTED}; border-top: 1px solid #2A3646; padding: 2px 8px;"
        )
        status.showMessage("就绪")

        self.goto("library")
        self.refresh_all()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(212)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(6)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        mark = QLabel("B")
        mark.setFixedSize(38, 38)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            f"background: {ACCENT}; color: white; border-radius: 10px;"
            "font-size: 20px; font-weight: 800;"
        )
        logo_row.addWidget(mark)
        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        name = QLabel("BOM 相似度")
        name.setStyleSheet("font-size: 15px; font-weight: 800; color: #FFFFFF;")
        version = QLabel("对比工具 · v1.0")
        version.setObjectName("Muted")
        text_box.addWidget(name)
        text_box.addWidget(version)
        logo_row.addLayout(text_box)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        layout.addSpacing(22)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for idx, (key, text) in enumerate(NAV_ITEMS):
            btn = button(text)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.goto(k))
            self.nav_group.addButton(btn, idx)
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        self.sidebar_stats = QLabel("库内 0 个方案")
        self.sidebar_stats.setObjectName("Muted")
        self.sidebar_stats.setWordWrap(True)
        layout.addWidget(self.sidebar_stats)

        open_btn = button("打开数据目录", "ghost")
        open_btn.clicked.connect(lambda: open_in_explorer(str(DB_PATH)))
        layout.addWidget(open_btn)
        return sidebar

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(46)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 0, 24, 0)
        self.crumb = QLabel("工作区 / 方案库")
        self.crumb.setObjectName("Muted")
        layout.addWidget(self.crumb)
        layout.addStretch(1)
        hint = QLabel("匹配优先级：下级编码 > 替代物料组 > 名称+规格模糊匹配")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        return bar

    def goto(self, key: str):
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        button = self.nav_buttons.get(key)
        if button and not button.isChecked():
            button.setChecked(True)
        titles = dict(NAV_ITEMS)
        self.crumb.setText(f"工作区 / {titles.get(key, key)}")
        if hasattr(page, "refresh"):
            page.refresh()

    def refresh_all(self):
        stats = self.db.stats()
        self.sidebar_stats.setText(
            f"库内 {stats['schemes']} 个方案\n{stats['items']} 条物料记录\n{stats['groups']} 个替代组"
        )
        for key in ("library", "alt"):
            page = self.pages[key]
            if hasattr(page, "refresh"):
                page.refresh()
        self.compare_page.reload_schemes()
        self.compare_page.reload_b_schemes()

    def toast(self, message: str):
        self.statusBar().showMessage(message, 4000)
