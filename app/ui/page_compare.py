"""相似度对比页面。"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import exporter
from ..core.engine import (
    DIFF_TYPES,
    TYPE_EXACT,
    BomComparator,
    CompareOptions,
    batch_compare,
    row_to_text,
)
from ..core.importer import CleanOptions, auto_mapping, clean_rows, read_file
from ..core.textutil import format_qty
from .common import Card, button, fill_table, make_table, open_in_explorer
from .dialogs import MappingDialog, WeightRuleDialog
from .theme import ACCENT, GREEN, MUTED, ORANGE, RED, TYPE_COLORS


class ComparePage(QWidget):
    HEADERS = ["差异类型", "层级", "下级BOM", "库内编码", "新BOM编码", "名称", "规格", "单位",
               "库内用量", "新BOM用量", "用量变化", "变化率", "权重", "库内获取途径",
               "新BOM获取途径", "库内发料中心", "新BOM发料中心", "附加差异", "说明"]
    WIDTHS = [110, 46, 76, 120, 120, 160, 170, 46, 76, 84, 74, 68, 52, 90, 90, 90, 90, 110, 150]

    BATCH_HEADERS = ["排名", "方案名称", "版本", "相似度", "完全匹配", "等价替换", "数量变更",
                     "新增", "缺失", "高权重差异"]
    BATCH_WIDTHS = [56, 260, 90, 90, 90, 90, 90, 70, 70, 100]

    def __init__(self, db, window):
        super().__init__()
        self.db = db
        self.window = window
        self.result = None
        self.batch_results = []
        self.file_sheet = None
        self.file_mapping: dict = {}
        self.file_flatten = False
        self.file_items: list[dict] = []
        self.file_label = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(16)

        # ---------- 左侧控制区 ----------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(370)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_host = QWidget()
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 6, 0)
        left.setSpacing(12)

        title = QLabel("相似度对比")
        title.setObjectName("PageTitle")
        left.addWidget(title)
        subtitle = QLabel("库内方案两两对比，或上传新 BOM 检索全库相似方案")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)

        # A 方案
        card_a = Card("对比基准 A（库内方案）")
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索方案…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reload_schemes)
        card_a.add(self.search)
        self.scheme_table = make_table(["方案名称", "物料"], [220, 54], stretch_last=False)
        self.scheme_table.setMinimumHeight(150)
        self.scheme_table.setMaximumHeight(210)
        self.scheme_table.itemSelectionChanged.connect(self._on_a_selected)
        card_a.add(self.scheme_table)
        left.addWidget(card_a)

        # B 来源
        card_b = Card("待对比 BOM（B）")
        self.radio_scheme = QRadioButton("选择库内方案")
        self.radio_file = QRadioButton("上传本地文件")
        self.radio_scheme.setChecked(True)
        self.radio_scheme.toggled.connect(self._on_source_changed)
        card_b.add(self.radio_scheme)
        self.b_combo = QComboBox()
        card_b.add(self.b_combo)

        file_box = QVBoxLayout()
        file_box.setSpacing(6)
        self.radio_file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("未选择文件")
        choose_btn = button("选择…")
        choose_btn.clicked.connect(self.choose_file)
        self.choose_btn = choose_btn
        self.radio_file_row.addWidget(self.file_path_edit, 1)
        self.radio_file_row.addWidget(choose_btn)
        file_box.addLayout(self.radio_file_row)
        map_row = QHBoxLayout()
        self.map_label = QLabel("支持 xlsx / csv")
        self.map_label.setObjectName("Muted")
        self.map_btn = button("列映射", "ghost")
        self.map_btn.setEnabled(False)
        self.map_btn.clicked.connect(self.open_mapping)
        map_row.addWidget(self.map_label, 1)
        map_row.addWidget(self.map_btn)
        file_box.addLayout(map_row)
        card_b.add_layout(file_box)
        card_b.add(self.radio_file)
        self._set_file_widgets_enabled(False)
        left.addWidget(card_b)

        # 参数
        card_p = Card("对比参数")
        algo_row = QHBoxLayout()
        algo_row.addWidget(QLabel("算法"))
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItem("加权余弦相似度（默认）", "cosine")
        self.algorithm_combo.addItem("加权 Jaccard", "jaccard")
        algo_row.addWidget(self.algorithm_combo, 1)
        card_p.add_layout(algo_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("模糊匹配阈值"), 0, 0)
        self.fuzzy_spin = QSpinBox()
        self.fuzzy_spin.setRange(50, 100)
        self.fuzzy_spin.setSuffix(" %")
        self.fuzzy_spin.setValue(85)
        grid.addWidget(self.fuzzy_spin, 0, 1)
        grid.addWidget(QLabel("高权重阈值"), 1, 0)
        self.high_spin = QSpinBox()
        self.high_spin.setRange(1, 20)
        self.high_spin.setValue(2)
        self.high_spin.setPrefix("≥ ")
        grid.addWidget(self.high_spin, 1, 1)
        card_p.add_layout(grid)

        self.chk_supply = QCheckBox("标记获取途径差异")
        self.chk_issue = QCheckBox("标记发料中心差异")
        card_p.add(self.chk_supply)
        card_p.add(self.chk_issue)

        weight_btn = button("物料权重配置", "ghost")
        weight_btn.clicked.connect(self.open_weights)
        card_p.add(weight_btn)
        left.addWidget(card_p)

        # 按钮
        run_btn = button("开始对比", "primary")
        run_btn.setMinimumHeight(40)
        run_btn.clicked.connect(self.run_compare)
        left.addWidget(run_btn)

        batch_row = QHBoxLayout()
        batch_btn = button("批量对比全库")
        batch_btn.clicked.connect(self.run_batch)
        self.top_n = QSpinBox()
        self.top_n.setRange(1, 100)
        self.top_n.setValue(10)
        self.top_n.setPrefix("TOP ")
        batch_row.addWidget(batch_btn)
        batch_row.addWidget(self.top_n)
        left.addLayout(batch_row)
        left.addStretch(1)
        left_scroll.setWidget(left_host)
        root.addWidget(left_scroll)

        # ---------- 右侧结果 ----------
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_detail_view())
        self.stack.addWidget(self._build_batch_view())
        root.addWidget(self.stack, 1)

        self.load_settings()
        self.reload_schemes()
        self.reload_b_schemes()
        self._on_source_changed()

    # ---------- 视图构建 ----------
    def _build_detail_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        summary = Card()
        top = QHBoxLayout()
        score_box = QVBoxLayout()
        score_box.setSpacing(0)
        caption = QLabel("相似度得分")
        caption.setObjectName("Muted")
        self.lbl_score = QLabel("--")
        self.lbl_score.setObjectName("ScoreValue")
        self.lbl_algo = QLabel("加权余弦相似度")
        self.lbl_algo.setObjectName("Muted")
        score_box.addWidget(caption)
        score_box.addWidget(self.lbl_score)
        score_box.addWidget(self.lbl_algo)
        top.addLayout(score_box)
        top.addSpacing(20)

        info_box = QVBoxLayout()
        info_box.setSpacing(4)
        self.lbl_a = QLabel("方案 A：--")
        self.lbl_b = QLabel("方案 B：--")
        self.lbl_time = QLabel("对比时间：--")
        self.lbl_matched = QLabel("匹配物料：--")
        for label in (self.lbl_a, self.lbl_b, self.lbl_time, self.lbl_matched):
            label.setObjectName("Muted")
            info_box.addWidget(label)
        top.addLayout(info_box)
        top.addStretch(1)

        counts = QGridLayout()
        counts.setHorizontalSpacing(18)
        counts.setVerticalSpacing(6)
        self.count_labels = {}
        for idx, dtype in enumerate(DIFF_TYPES):
            row, col = divmod(idx, 3)
            label = QLabel(dtype)
            label.setObjectName("Muted")
            value = QLabel("0")
            value.setStyleSheet(f"color: {TYPE_COLORS[dtype]}; font-size: 20px; font-weight: 700;")
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(value)
            box.addWidget(label)
            counts.addLayout(box, row, col)
            self.count_labels[dtype] = value
        top.addLayout(counts)
        summary.add_layout(top)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(f"color: {ORANGE};")
        self.warning_label.hide()
        summary.add(self.warning_label)
        layout.addWidget(summary)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("差异类型"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部", "")
        for dtype in DIFF_TYPES:
            self.filter_combo.addItem(dtype, dtype)
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        toolbar.addWidget(self.filter_combo)
        self.chk_key_only = QCheckBox("只看重点（标红项）")
        self.chk_key_only.toggled.connect(self.apply_filter)
        toolbar.addWidget(self.chk_key_only)
        self.row_count_label = QLabel("")
        self.row_count_label.setObjectName("Muted")
        toolbar.addWidget(self.row_count_label)
        toolbar.addStretch(1)
        self.export_btn = button("导出 Excel 差异报告", "primary")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_report)
        toolbar.addWidget(self.export_btn)
        layout.addLayout(toolbar)

        self.table = make_table(self.HEADERS, self.WIDTHS, stretch_last=False)
        layout.addWidget(self.table, 1)
        return page

    def _build_batch_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = Card("全库相似度排行", "按相似度降序，双击查看差异明细")
        self.batch_label = QLabel("尚未执行批量对比")
        self.batch_label.setObjectName("Muted")
        self.batch_label.setWordWrap(True)
        card.add(self.batch_label)
        self.batch_table = make_table(self.BATCH_HEADERS, self.BATCH_WIDTHS, stretch_last=True)
        self.batch_table.doubleClicked.connect(self.open_batch_detail)
        card.add(self.batch_table)
        layout.addWidget(card, 1)
        return page

    # ---------- 数据 ----------
    def refresh(self):
        self.reload_schemes()
        self.reload_b_schemes()

    def reload_schemes(self):
        keyword = self.search.text().strip()
        self.schemes = self.db.list_schemes(keyword)
        selected_id = self.selected_scheme_id()
        rows = [[s["name"], s["items"]] for s in self.schemes]
        fill_table(self.scheme_table, rows, aligns={1: Qt.AlignCenter})
        if selected_id:
            for idx, scheme in enumerate(self.schemes):
                if scheme["id"] == selected_id:
                    self.scheme_table.selectRow(idx)
                    break

    def reload_b_schemes(self):
        current = self.b_combo.currentData()
        self.b_combo.blockSignals(True)
        self.b_combo.clear()
        for scheme in self.db.list_schemes():
            self.b_combo.addItem(f"{scheme['name']} {scheme['version']}".strip(), scheme["id"])
        self.b_combo.blockSignals(False)
        if current:
            pos = self.b_combo.findData(current)
            if pos >= 0:
                self.b_combo.setCurrentIndex(pos)

    def selected_scheme_id(self):
        row = self.scheme_table.currentRow()
        if 0 <= row < len(self.schemes):
            return self.schemes[row]["id"]
        return None

    def select_scheme(self, scheme_id: int):
        self.search.clear()
        self.reload_schemes()
        for idx, scheme in enumerate(self.schemes):
            if scheme["id"] == scheme_id:
                self.scheme_table.selectRow(idx)
                break
        self.reload_b_schemes()
        if self.b_combo.count() > 1 and self.b_combo.currentData() == scheme_id:
            self.b_combo.setCurrentIndex((self.b_combo.currentIndex() + 1) % self.b_combo.count())

    def _on_a_selected(self):
        pass

    def _on_source_changed(self):
        is_file = self.radio_file.isChecked()
        self.b_combo.setEnabled(not is_file)
        self._set_file_widgets_enabled(is_file)

    def _set_file_widgets_enabled(self, enabled: bool):
        self.file_path_edit.setEnabled(enabled)
        self.choose_btn.setEnabled(enabled)
        self.map_btn.setEnabled(enabled and self.file_sheet is not None)

    # ---------- 参数 ----------
    def load_settings(self):
        algo = self.db.get_setting("algorithm", "cosine")
        pos = self.algorithm_combo.findData(algo)
        self.algorithm_combo.setCurrentIndex(max(0, pos))
        self.fuzzy_spin.setValue(int(float(self.db.get_setting("fuzzy_threshold", "0.85")) * 100))
        self.high_spin.setValue(int(float(self.db.get_setting("high_weight", "2"))))
        self.chk_supply.setChecked(self.db.get_setting("diff_supply", "0") == "1")
        self.chk_issue.setChecked(self.db.get_setting("diff_issue", "0") == "1")

    def build_options(self) -> CompareOptions:
        options = CompareOptions(
            algorithm=self.algorithm_combo.currentData(),
            fuzzy_threshold=self.fuzzy_spin.value() / 100,
            diff_supply=self.chk_supply.isChecked(),
            diff_issue=self.chk_issue.isChecked(),
            high_weight=float(self.high_spin.value()),
            default_weight=float(self.db.get_setting("default_weight", "1")),
            qty_tol=float(self.db.get_setting("qty_tolerance", "0.001")),
        )
        self.db.set_setting("algorithm", options.algorithm)
        self.db.set_setting("fuzzy_threshold", str(options.fuzzy_threshold))
        self.db.set_setting("high_weight", str(options.high_weight))
        self.db.set_setting("diff_supply", "1" if options.diff_supply else "0")
        self.db.set_setting("diff_issue", "1" if options.diff_issue else "0")
        return options

    def open_weights(self):
        WeightRuleDialog(self.db, self).exec()

    # ---------- B 文件 ----------
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择待对比 BOM", "", "BOM 文件 (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)"
        )
        if not path:
            return
        try:
            sheet = read_file(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.file_sheet = sheet
        self.file_path_edit.setText(sheet.path)
        templates = self.db.list_templates()
        import json

        template = None
        if templates:
            try:
                template = json.loads(templates[0]["mapping"])
            except (json.JSONDecodeError, TypeError):
                template = None
        self.file_mapping = auto_mapping(sheet.headers, template)
        if "code" not in self.file_mapping or "qty" not in self.file_mapping:
            dialog = MappingDialog(sheet, self.file_mapping, parent=self)
            if dialog.exec():
                self.file_mapping = dialog.mapping
            else:
                self.map_label.setText("未完成列映射，无法对比")
                return
        self.radio_file.setChecked(True)
        self.rebuild_file_items()
        self.map_btn.setEnabled(True)
        if self.file_items:
            self.map_label.setText(f"已解析 {len(self.file_items)} 条物料")
            self.map_label.setStyleSheet(f"color: {GREEN};")

    def open_mapping(self):
        if not self.file_sheet:
            return
        dialog = MappingDialog(self.file_sheet, self.file_mapping, self.file_flatten, self)
        if dialog.exec():
            self.file_mapping = dialog.mapping
            self.rebuild_file_items()
            self.map_label.setText(f"已解析 {len(self.file_items)} 条物料")
            self.map_label.setStyleSheet(f"color: {GREEN};")

    def rebuild_file_items(self):
        if not self.file_sheet:
            self.file_items = []
            return
        try:
            result = clean_rows(
                self.file_sheet, self.file_mapping, CleanOptions(flatten=self.file_flatten)
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "清洗失败", str(exc))
            self.file_items = []
            return
        self.file_items = [asdict(item) for item in result.items]
        self.file_label = Path(self.file_sheet.path).stem

    def load_b(self):
        if self.radio_scheme.isChecked():
            scheme_id = self.b_combo.currentData()
            if not scheme_id:
                QMessageBox.information(self, "提示", "库内暂无方案，请先导入 BOM。")
                return None, None
            scheme = self.db.get_scheme(scheme_id)
            items = self.db.get_items(scheme_id)
            label = f"{scheme['name']} {scheme['version']}".strip()
            return items, label
        if not self.file_items:
            QMessageBox.information(self, "提示", "请先选择并映射待对比的 BOM 文件。")
            return None, None
        return self.file_items, self.file_label

    # ---------- 比对 ----------
    def run_compare(self):
        scheme_id = self.selected_scheme_id()
        if not scheme_id:
            QMessageBox.information(self, "提示", "请先在左侧选择对比基准方案 A。")
            return
        items_b, label_b = self.load_b()
        if items_b is None:
            return
        scheme = self.db.get_scheme(scheme_id)
        items_a = self.db.get_items(scheme_id)
        if not items_a:
            QMessageBox.information(self, "提示", "方案 A 没有物料明细。")
            return
        comparator = BomComparator(self.db, self.build_options())
        self.result = comparator.compare(
            items_a, items_b, f"{scheme['name']} {scheme['version']}".strip(), label_b
        )
        self.show_result(self.result)
        self.stack.setCurrentIndex(0)

    def show_result(self, result):
        self.lbl_score.setText(f"{result.score:.2f}%")
        self.lbl_algo.setText(result.algorithm_label)
        self.lbl_a.setText(f"方案 A：{result.label_a}")
        self.lbl_b.setText(f"方案 B：{result.label_b}")
        self.lbl_time.setText(f"对比时间：{result.time}")
        self.lbl_matched.setText(
            f"匹配物料：{result.matched} 项 · 物料数 A/B：{result.total_a}/{result.total_b}"
        )
        for dtype, label in self.count_labels.items():
            label.setText(str(result.stats.get(dtype, 0)))
        if result.warnings:
            self.warning_label.setText("⚠ " + "  ".join(result.warnings))
            self.warning_label.show()
        else:
            self.warning_label.hide()
        self.export_btn.setEnabled(bool(result.rows))
        self.apply_filter()

    def apply_filter(self):
        if not self.result:
            fill_table(self.table, [])
            return
        dtype = self.filter_combo.currentData()
        key_only = self.chk_key_only.isChecked()
        rows = [
            row for row in self.result.rows
            if (not dtype or row["type"] == dtype) and (not key_only or row["highlight"])
        ]
        self._fill_diff_table(rows)
        self.row_count_label.setText(f"显示 {len(rows)} / {len(self.result.rows)} 行")

    def _fill_diff_table(self, rows: list[dict]):
        table = self.table
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            text = row_to_text(row)
            values = [
                row["type"], row["level"], row["bom_parent"], row["code_a"], row["code_b"],
                row["name"], row["spec"], row["unit"], format_qty(row["qty_a"]),
                format_qty(row["qty_b"]), text["用量变化"], text["变化率"],
                f"{row['weight']:.2f}", row["supply_a"], row["supply_b"],
                row["issue_a"], row["issue_b"], row["extra"], row["note"],
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setTextAlignment(
                    Qt.AlignCenter if c in (1, 2, 7, 8, 9, 10, 11, 12) else Qt.AlignLeft | Qt.AlignVCenter
                )
                if row["highlight"]:
                    item.setBackground(QColor("#3D1D24"))
                    item.setForeground(QColor("#FF8A8A"))
                    font = QFont("Microsoft YaHei UI", 9)
                    font.setBold(True)
                    item.setFont(font)
                elif c == 0:
                    item.setForeground(QColor(TYPE_COLORS.get(row["type"], MUTED)))
                elif row["type"] in ("新增物料",) and c in (4, 9):
                    item.setForeground(QColor(GREEN))
                elif row["type"] in ("缺失物料",) and c in (3, 8):
                    item.setForeground(QColor(RED))
                elif row["extra"] and c == 17:
                    item.setForeground(QColor(ORANGE))
                table.setItem(r, c, item)
        table.setUpdatesEnabled(True)

    def export_report(self):
        if not self.result:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        default = f"BOM差异报告_{self.result.label_a}_vs_{self.result.label_b}_{stamp}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "导出差异报告", default, "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            exporter.export_report(self.result, path, self.build_options())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        box = QMessageBox(self)
        box.setWindowTitle("导出成功")
        box.setText(f"差异报告已导出：\n{path}")
        open_btn = box.addButton("打开所在文件夹", QMessageBox.ActionRole)
        box.addButton("关闭", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            open_in_explorer(path)

    # ---------- 批量 ----------
    def run_batch(self):
        items_b, label_b = self.load_b()
        if items_b is None:
            return
        options = self.build_options()
        self.window.toast("正在与全库方案比对…")
        try:
            results = batch_compare(self.db, items_b, label_b, options)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "批量对比失败", str(exc))
            return
        if not results:
            QMessageBox.information(self, "提示", "库内暂无可对比的方案。")
            return
        self.batch_results = results[: self.top_n.value()]
        rows, aligns = [], {}
        for idx, res in enumerate(self.batch_results, start=1):
            rows.append([
                idx, res.scheme_name, res.scheme_version, f"{res.score:.2f}%",
                res.stats.get(TYPE_EXACT, 0), res.stats.get("等价替换匹配", 0),
                res.stats.get("数量变更", 0), res.stats.get("新增物料", 0),
                res.stats.get("缺失物料", 0), res.high_weight_count,
            ])
        for col in range(0, 10):
            aligns[col] = Qt.AlignCenter
        fill_table(self.batch_table, rows, aligns=aligns)
        self.batch_label.setText(
            f"目标 BOM：{label_b} · 共比对 {len(results)} 个方案，显示 TOP {len(self.batch_results)}"
            f" · 算法：{self.batch_results[0].algorithm_label} · {datetime.now().strftime('%H:%M:%S')}"
        )
        self.stack.setCurrentIndex(1)

    def open_batch_detail(self):
        row = self.batch_table.currentRow()
        if row < 0 or row >= len(self.batch_results):
            return
        res = self.batch_results[row]
        self.select_scheme(res.scheme_id)
        self.run_compare()
