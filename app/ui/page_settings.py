"""参数设置页面。"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..core.db import DB_PATH
from .common import Card, button, fill_table, make_table, open_in_explorer
from .dialogs import FIELD_CHOICES, WeightRuleDialog
from .theme import MUTED


class SettingsPage(QWidget):
    def __init__(self, db, window):
        super().__init__()
        self.db = db
        self.window = window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        title = QLabel("参数设置")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("算法、权重与数据管理。参数会影响相似度得分与差异分类，修改后重新对比生效")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(subtitle)

        body = QHBoxLayout()
        body.setSpacing(14)

        # 左列：默认参数
        left = QVBoxLayout()
        left.setSpacing(14)
        card1 = Card("默认对比参数")
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("默认算法"))
        self.algo_combo = QComboBox()
        self.algo_combo.addItem("加权余弦相似度", "cosine")
        self.algo_combo.addItem("加权 Jaccard", "jaccard")
        row1.addWidget(self.algo_combo, 1)
        card1.add_layout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("模糊匹配阈值"))
        self.fuzzy_spin = QDoubleSpinBox()
        self.fuzzy_spin.setRange(0.5, 1.0)
        self.fuzzy_spin.setSingleStep(0.01)
        self.fuzzy_spin.setDecimals(2)
        row2.addWidget(self.fuzzy_spin, 1)
        card1.add_layout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("高权重阈值"))
        self.high_spin = QDoubleSpinBox()
        self.high_spin.setRange(1.0, 20.0)
        self.high_spin.setSingleStep(0.5)
        self.high_spin.setDecimals(2)
        row3.addWidget(self.high_spin, 1)
        card1.add_layout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("未命中规则默认权重"))
        self.default_spin = QDoubleSpinBox()
        self.default_spin.setRange(0.01, 100.0)
        self.default_spin.setSingleStep(0.1)
        self.default_spin.setDecimals(2)
        row4.addWidget(self.default_spin, 1)
        card1.add_layout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("用量对比容差"))
        self.tol_spin = QDoubleSpinBox()
        self.tol_spin.setRange(0.0, 0.2)
        self.tol_spin.setSingleStep(0.001)
        self.tol_spin.setDecimals(4)
        row5.addWidget(self.tol_spin, 1)
        card1.add_layout(row5)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_btn = button("保存参数", "primary")
        save_btn.clicked.connect(self.save)
        save_row.addWidget(save_btn)
        card1.add_layout(save_row)
        left.addWidget(card1)

        card3 = Card("数据与备份")
        path_label = QLabel(str(DB_PATH))
        path_label.setObjectName("Muted")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card3.add(path_label)
        data_actions = QHBoxLayout()
        open_btn = button("打开数据目录")
        open_btn.clicked.connect(lambda: open_in_explorer(str(DB_PATH)))
        backup_btn = button("备份数据库")
        backup_btn.clicked.connect(self.backup)
        data_actions.addWidget(open_btn)
        data_actions.addWidget(backup_btn)
        data_actions.addStretch(1)
        card3.add_layout(data_actions)
        left.addWidget(card3)
        left.addStretch(1)

        # 右列：权重规则
        right = QVBoxLayout()
        card2 = Card("物料权重规则", "按顺序匹配，命中第一条生效")
        self.rule_table = make_table(["规则名", "匹配字段", "关键词", "权重"], [180, 110, 160, 70], stretch_last=True)
        self.rule_table.setMinimumHeight(280)
        card2.add(self.rule_table)
        rule_actions = QHBoxLayout()
        hint = QLabel("主控高、常规阻容中、紧固件最低")
        hint.setObjectName("Muted")
        rule_actions.addWidget(hint)
        rule_actions.addStretch(1)
        edit_btn = button("管理权重规则", "primary")
        edit_btn.clicked.connect(self.edit_rules)
        rule_actions.addWidget(edit_btn)
        card2.add_layout(rule_actions)
        right.addWidget(card2)

        card4 = Card("说明")
        desc = QLabel(
            "· 损耗率不参与任何计算与打分。\n"
            "· 用量只取标准用量；多层展开时总用量＝各级标准用量逐层相乘。\n"
            "· 匹配优先级：下级编码 > 替代物料组 > 名称+规格模糊匹配。\n"
            "· 获取途径、发料中心默认不参与打分，可在对比页按需标记差异。\n"
            "· 单位不换算，单位不一致时按数值比较并提示人工复核。\n"
            "· 相似度分数仅供参考，等价物料判定结果需人工复核。"
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        card4.add(desc)
        right.addWidget(card4)
        right.addStretch(1)

        body.addLayout(left, 1)
        body.addLayout(right, 1)
        layout.addLayout(body, 1)
        self.refresh()

    def refresh(self):
        self.algo_combo.setCurrentIndex(
            max(0, self.algo_combo.findData(self.db.get_setting("algorithm", "cosine")))
        )
        self.fuzzy_spin.setValue(float(self.db.get_setting("fuzzy_threshold", "0.85")))
        self.high_spin.setValue(float(self.db.get_setting("high_weight", "2")))
        self.default_spin.setValue(float(self.db.get_setting("default_weight", "1")))
        self.tol_spin.setValue(float(self.db.get_setting("qty_tolerance", "0.001")))
        self.load_rules()

    def load_rules(self):
        rules = self.db.list_weight_rules()
        field_text = dict(FIELD_CHOICES)
        rows = [
            [r["label"] or "-", field_text.get(r["field"], r["field"]), r["keyword"], f"{r['weight']:.2f}"]
            for r in rules
        ]
        fill_table(self.rule_table, rows, aligns={3: Qt.AlignCenter})

    def save(self):
        self.db.set_setting("algorithm", self.algo_combo.currentData())
        self.db.set_setting("fuzzy_threshold", str(self.fuzzy_spin.value()))
        self.db.set_setting("high_weight", str(self.high_spin.value()))
        self.db.set_setting("default_weight", str(self.default_spin.value()))
        self.db.set_setting("qty_tolerance", str(self.tol_spin.value()))
        self.window.compare_page.load_settings()
        self.window.toast("参数已保存")

    def edit_rules(self):
        WeightRuleDialog(self.db, self).exec()
        self.load_rules()

    def backup(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default = str(Path.home() / f"bom_library_backup_{stamp}.db")
        path, _ = QFileDialog.getSaveFileName(self, "备份数据库", default, "SQLite 数据库 (*.db)")
        if not path:
            return
        try:
            self.db.conn.commit()
            shutil.copyfile(DB_PATH, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "备份失败", str(exc))
            return
        QMessageBox.information(self, "备份完成", f"数据库已备份到：\n{path}")
