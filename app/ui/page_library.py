"""方案库页面。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..core.textutil import format_qty
from .common import button, card_stat, fill_table, make_table
from .dialogs import ItemDetailDialog


class LibraryPage(QWidget):
    HEADERS = ["方案名称", "版本", "物料数", "层级", "来源文件", "创建时间", "备注"]
    WIDTHS = [260, 90, 80, 80, 260, 160, 260]

    def __init__(self, db, window):
        super().__init__()
        self.db = db
        self.window = window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("BOM 方案库")
        title.setObjectName("PageTitle")
        subtitle = QLabel("整份 BOM 方案入库后，可与新 BOM 做相似度比对与差异分析")
        subtitle.setObjectName("PageSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        refresh_btn = button("刷新")
        refresh_btn.clicked.connect(self.refresh)
        import_btn = button("＋ 导入新 BOM", "primary")
        import_btn.clicked.connect(lambda: self.window.goto("import"))
        header.addWidget(refresh_btn)
        header.addWidget(import_btn)
        layout.addLayout(header)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.card_schemes = card_stat("方案总数", "0", "#FFFFFF")
        self.card_items = card_stat("物料记录", "0", "#FFFFFF")
        self.card_groups = card_stat("替代物料组", "0", "#FFFFFF")
        self.card_flat = card_stat("已扁平化方案", "0", "#FFFFFF")
        for card in (self.card_schemes, self.card_items, self.card_groups, self.card_flat):
            card.setFixedHeight(84)
            stats.addWidget(card)
        layout.addLayout(stats)

        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索方案名称 / 版本 / 备注…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(320)
        self.search.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        self.hint = QLabel("")
        self.hint.setObjectName("Muted")
        toolbar.addWidget(self.hint)
        detail_btn = button("查看明细")
        detail_btn.clicked.connect(self.open_detail)
        compare_btn = button("用此方案对比")
        compare_btn.clicked.connect(self.compare_current)
        delete_btn = button("删除方案", "danger")
        delete_btn.clicked.connect(self.delete_current)
        toolbar.addWidget(detail_btn)
        toolbar.addWidget(compare_btn)
        toolbar.addWidget(delete_btn)
        layout.addLayout(toolbar)

        self.table = make_table(self.HEADERS, self.WIDTHS, stretch_last=True)
        self.table.doubleClicked.connect(self.open_detail)
        layout.addWidget(self.table, 1)

        self.schemes: list[dict] = []

    def refresh(self):
        keyword = self.search.text().strip()
        self.schemes = self.db.list_schemes(keyword)
        rows, aligns = [], {}
        for scheme in self.schemes:
            rows.append([
                scheme["name"],
                scheme["version"] or "-",
                scheme["items"],
                "多层展开" if scheme["is_flat"] else "单层",
                scheme["source_file"] or "-",
                scheme["created_at"],
                scheme["remark"] or "",
            ])
        for col in (1, 2, 3):
            aligns[col] = Qt.AlignCenter
        fill_table(self.table, rows, aligns=aligns)
        self.hint.setText(f"共 {len(self.schemes)} 个方案" + ("（已筛选）" if keyword else ""))

        stats = self.db.stats()
        self.card_schemes.value_label.setText(str(stats["schemes"]))
        self.card_items.value_label.setText(str(stats["items"]))
        self.card_groups.value_label.setText(str(stats["groups"]))
        flat = sum(1 for item in self.schemes if item["is_flat"])
        self.card_flat.value_label.setText(str(flat))

    def _current(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.schemes):
            QMessageBox.information(self, "提示", "请先在列表中选择一个方案。")
            return None
        return self.schemes[row]

    def open_detail(self):
        scheme = self._current()
        if not scheme:
            return
        items = self.db.get_items(scheme["id"])
        ItemDetailDialog(scheme, items, self).exec()

    def compare_current(self):
        scheme = self._current()
        if not scheme:
            return
        self.window.goto("compare")
        self.window.compare_page.select_scheme(scheme["id"])

    def delete_current(self):
        scheme = self._current()
        if not scheme:
            return
        confirm = QMessageBox.question(
            self,
            "删除方案",
            f"确定删除方案『{scheme['name']}』及其 {scheme['items']} 条明细？\n该操作不可撤销。",
        )
        if confirm != QMessageBox.Yes:
            return
        self.db.delete_scheme(scheme["id"])
        self.refresh()
        self.window.refresh_all()
