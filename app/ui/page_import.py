"""BOM 导入与清洗页面。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core.importer import (
    FIELD_LABELS,
    FIELDS,
    CleanOptions,
    auto_mapping,
    clean_rows,
    collect_alt_pairs,
    read_file,
)
from ..core.textutil import format_qty
from .common import Card, button, fill_table, make_table
from .theme import GREEN, MUTED, ORANGE, RED

MAX_PREVIEW_ROWS = 2000


class ImportPage(QWidget):
    HEADERS = ["行号", "状态", "下级BOM", "下级编码", "名称", "规格", "单位",
               "标准用量", "展开总用量", "替换物料", "获取途径", "发料中心"]
    WIDTHS = [60, 80, 84, 130, 180, 190, 50, 80, 90, 130, 90, 90]

    def __init__(self, db, window):
        super().__init__()
        self.db = db
        self.window = window
        self.sheet = None
        self.mapping: dict[str, str] = {}
        self.result = None
        self.combos: dict[str, QComboBox] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(16)

        # ---------- 左侧 ----------
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(440)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 6, 0)
        left.setSpacing(12)

        title = QLabel("导入 BOM")
        title.setObjectName("PageTitle")
        left.addWidget(title)
        subtitle = QLabel("支持 Excel(.xlsx) 与 CSV，映射方案可存为模板复用")
        subtitle.setObjectName("PageSubtitle")
        left.addWidget(subtitle)

        # 文件卡
        file_card = Card("1 · 选择文件")
        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("尚未选择文件")
        browse_btn = button("浏览…", "primary")
        browse_btn.clicked.connect(self.browse)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse_btn)
        file_card.add_layout(file_row)

        sheet_row = QHBoxLayout()
        sheet_row.addWidget(QLabel("工作表"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.setEnabled(False)
        self.sheet_combo.currentTextChanged.connect(self.on_sheet_changed)
        sheet_row.addWidget(self.sheet_combo, 1)
        file_card.add_layout(sheet_row)

        tpl_row = QHBoxLayout()
        tpl_row.addWidget(QLabel("映射模板"))
        self.template_combo = QComboBox()
        self.template_combo.currentIndexChanged.connect(self.on_template_changed)
        tpl_row.addWidget(self.template_combo, 1)
        file_card.add_layout(tpl_row)
        tpl_btns = QHBoxLayout()
        save_tpl = button("保存为模板", "ghost")
        save_tpl.clicked.connect(self.save_template)
        del_tpl = button("删除模板", "ghost")
        del_tpl.clicked.connect(self.delete_template)
        tpl_btns.addWidget(save_tpl)
        tpl_btns.addWidget(del_tpl)
        tpl_btns.addStretch(1)
        file_card.add_layout(tpl_btns)
        left.addWidget(file_card)

        # 映射卡
        map_card = Card("2 · 列映射", "必填：下级编码、标准用量")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for idx, (key, label, required) in enumerate(FIELDS):
            row, col = divmod(idx, 2)
            box = QVBoxLayout()
            box.setSpacing(3)
            caption = QLabel(label + (" *" if required else ""))
            caption.setObjectName("Muted")
            combo = QComboBox()
            combo.addItem("（不映射）", "")
            combo.currentIndexChanged.connect(self.on_mapping_changed)
            self.combos[key] = combo
            box.addWidget(caption)
            box.addWidget(combo)
            grid.addLayout(box, row, col)
        map_card.add_layout(grid)
        left.addWidget(map_card)

        # 清洗卡
        clean_card = Card("3 · 清洗选项")
        self.chk_strip = QCheckBox("去除首尾空格、压缩空白")
        self.chk_strip.setChecked(True)
        self.chk_upper = QCheckBox("统一编码大小写（转大写）")
        self.chk_upper.setChecked(True)
        self.chk_total = QCheckBox("跳过合计行 / 小计行")
        self.chk_total.setChecked(True)
        self.chk_comment = QCheckBox("跳过注释行（#、//、说明）")
        self.chk_comment.setChecked(True)
        self.chk_flatten = QCheckBox("启用多层展开（总用量＝逐层相乘，含循环检测）")
        self.chk_alt = QCheckBox("入库时自动解析替换物料并合并替代组")
        self.chk_alt.setChecked(True)
        for chk in (self.chk_strip, self.chk_upper, self.chk_total,
                    self.chk_comment, self.chk_flatten, self.chk_alt):
            chk.toggled.connect(self.on_mapping_changed)
            clean_card.add(chk)
        left.addWidget(clean_card)

        # 方案信息
        info_card = Card("4 · 方案信息")
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名称 *"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：A03 电源板 BOM")
        name_row.addWidget(self.name_edit, 1)
        info_card.add_layout(name_row)
        ver_row = QHBoxLayout()
        ver_row.addWidget(QLabel("版本"))
        self.version_edit = QLineEdit("V1.0")
        ver_row.addWidget(self.version_edit, 1)
        info_card.add_layout(ver_row)
        remark_row = QHBoxLayout()
        remark_row.addWidget(QLabel("备注"))
        self.remark_edit = QLineEdit()
        self.remark_edit.setPlaceholderText("可选")
        remark_row.addWidget(self.remark_edit, 1)
        info_card.add_layout(remark_row)

        actions = QHBoxLayout()
        preview_btn = button("预览清洗结果")
        preview_btn.clicked.connect(self.preview)
        self.import_btn = button("确认入库", "primary")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.do_import)
        actions.addWidget(preview_btn)
        actions.addWidget(self.import_btn, 1)
        info_card.add_layout(actions)
        left.addWidget(info_card)
        left.addStretch(1)

        left_scroll.setWidget(left_widget)
        root.addWidget(left_scroll)

        # ---------- 右侧预览 ----------
        preview_card = Card("导入预览", "确认无误后再入库")
        self.stats_label = QLabel("请选择文件后预览")
        self.stats_label.setObjectName("Muted")
        self.stats_label.setWordWrap(True)
        preview_card.add(self.stats_label)

        self.table = make_table(self.HEADERS, self.WIDTHS, stretch_last=True)
        preview_card.add(self.table)
        root.addWidget(preview_card, 1)

        self.reload_templates()
        self.refresh()

    # ---------- 数据加载 ----------
    def refresh(self):
        self.reload_templates()

    def reload_templates(self):
        current = self.template_combo.currentText()
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("（不使用模板）", None)
        for tpl in self.db.list_templates():
            self.template_combo.addItem(tpl["name"], tpl["id"])
        self.template_combo.blockSignals(False)
        if current:
            pos = self.template_combo.findText(current)
            if pos >= 0:
                self.template_combo.setCurrentIndex(pos)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 BOM 文件", "", "BOM 文件 (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)"
        )
        if path:
            self.load_file(path)

    def load_file(self, path: str, show_error: bool = True):
        try:
            sheet = read_file(path)
        except Exception as exc:  # noqa: BLE001
            if show_error:
                QMessageBox.critical(self, "读取失败", f"{exc}")
            return
        self.sheet = sheet
        self.path_edit.setText(sheet.path)
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItems(sheet.sheet_names)
        if sheet.active_sheet in sheet.sheet_names:
            self.sheet_combo.setCurrentText(sheet.active_sheet)
        self.sheet_combo.setEnabled(len(sheet.sheet_names) > 1)
        self.sheet_combo.blockSignals(False)
        if not self.name_edit.text().strip():
            self.name_edit.setText(Path(path).stem)
        self.apply_auto_mapping()
        self.preview()

    def on_sheet_changed(self, name: str):
        if not self.sheet or not name or name == self.sheet.active_sheet:
            return
        if name not in self.sheet.sheet_names:
            return
        try:
            sheet = read_file(self.sheet.path, name)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "读取失败", str(exc))
            return
        self.sheet = sheet
        self.apply_auto_mapping()
        self.preview()

    def template_mapping(self) -> dict | None:
        tpl_id = self.template_combo.currentData()
        if not tpl_id:
            return None
        import json

        for tpl in self.db.list_templates():
            if tpl["id"] == tpl_id:
                try:
                    return json.loads(tpl["mapping"])
                except (json.JSONDecodeError, TypeError):
                    return None
        return None

    def apply_auto_mapping(self):
        if not self.sheet:
            return
        self.mapping = auto_mapping(self.sheet.headers, self.template_mapping())
        for key, combo in self.combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("（不映射）", "")
            for header in self.sheet.headers:
                combo.addItem(header, header)
            target = self.mapping.get(key)
            if target:
                pos = combo.findData(target)
                combo.setCurrentIndex(max(0, pos))
            combo.blockSignals(False)

    def on_mapping_changed(self):
        if not self.sheet:
            return
        mapping = {}
        for key, combo in self.combos.items():
            value = combo.currentData()
            if value:
                mapping[key] = value
        self.mapping = mapping
        if "code" in mapping and "qty" in mapping:
            self.preview()
        else:
            self.stats_label.setText("请先映射『下级编码』与『标准用量』")
            self.stats_label.setStyleSheet(f"color: {ORANGE};")

    def on_template_changed(self):
        if self.sheet:
            self.apply_auto_mapping()
            self.preview()

    def save_template(self):
        if not self.sheet:
            QMessageBox.information(self, "提示", "请先选择并完成列映射。")
            return
        mapping = {key: combo.currentData() for key, combo in self.combos.items() if combo.currentData()}
        if "code" not in mapping or "qty" not in mapping:
            QMessageBox.warning(self, "映射不完整", "『下级编码』与『标准用量』必须映射后才能保存模板。")
            return
        name, ok = QInputDialog.getText(self, "保存映射模板", "模板名称：", text="标准 BOM 模板")
        if not ok or not name.strip():
            return
        self.db.save_template(name.strip(), mapping)
        self.reload_templates()
        pos = self.template_combo.findText(name.strip())
        if pos >= 0:
            self.template_combo.setCurrentIndex(pos)
        self.window.toast(f"映射模板『{name.strip()}』已保存")

    def delete_template(self):
        tpl_id = self.template_combo.currentData()
        if not tpl_id:
            QMessageBox.information(self, "提示", "当前未选择模板。")
            return
        name = self.template_combo.currentText()
        if QMessageBox.question(self, "删除模板", f"确定删除模板『{name}』？") != QMessageBox.Yes:
            return
        self.db.delete_template(tpl_id)
        self.reload_templates()
        self.window.toast("模板已删除")

    # ---------- 清洗预览 ----------
    def options(self) -> CleanOptions:
        return CleanOptions(
            strip=self.chk_strip.isChecked(),
            upper=self.chk_upper.isChecked(),
            skip_total=self.chk_total.isChecked(),
            skip_comment=self.chk_comment.isChecked(),
            flatten=self.chk_flatten.isChecked(),
        )

    def preview(self):
        if not self.sheet:
            return
        mapping = {key: combo.currentData() for key, combo in self.combos.items() if combo.currentData()}
        if "code" not in mapping or "qty" not in mapping:
            QMessageBox.warning(self, "映射不完整", "请映射『下级编码』与『标准用量』。")
            return
        try:
            result = clean_rows(self.sheet, mapping, self.options())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "清洗失败", str(exc))
            return
        self.result = result
        items = result.items
        abnormal = sum(1 for item in items if item.issues)
        self.stats_label.setStyleSheet(f"color: {MUTED};")
        text = (
            f"有效物料 {len(items)} 条 · 异常 {abnormal} 条 · 跳过 {len(result.skipped)} 行"
            f" · 源文件 {len(self.sheet.rows)} 行"
        )
        if self.chk_flatten.isChecked():
            cyclic = sum(1 for item in items if "BOM 循环嵌套" in item.issues)
            text += f" · 多层展开已启用" + (f"（检测到 {cyclic} 处循环嵌套）" if cyclic else "")
        if result.warnings:
            text += f"\n提示：{result.warnings[0]}"
        self.stats_label.setText(text)

        rows, colors, aligns = [], [], {}
        shown = min(len(items), MAX_PREVIEW_ROWS)
        for item in items[:shown]:
            status = "异常" if item.issues else "正常"
            rows.append([
                item.row_no, status, item.bom_parent, item.code, item.name, item.spec,
                item.unit, format_qty(item.qty), format_qty(item.total_qty),
                item.alt_text, item.supply, item.issue,
            ])
            colors.append(RED if item.issues else None)
        for skipped in result.skipped[:200]:
            rows.append([skipped["row_no"], "跳过", skipped["reason"], "", skipped["preview"], "", "", "", "", "", "", ""])
            colors.append("#6B7A8F")
        for col in (0, 1, 2, 6, 7, 8):
            aligns[col] = Qt.AlignCenter
        fill_table(self.table, rows, colors, aligns=aligns)
        if len(items) > MAX_PREVIEW_ROWS:
            self.stats_label.setText(text + f"（预览仅显示前 {MAX_PREVIEW_ROWS} 条）")

        self.import_btn.setEnabled(bool(items))

    # ---------- 入库 ----------
    def do_import(self):
        if not self.result or not self.result.items:
            QMessageBox.warning(self, "无数据", "没有可入库的物料，请检查文件与映射。")
            return
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少方案名称", "请填写方案名称。")
            self.name_edit.setFocus()
            return
        flatten = self.chk_flatten.isChecked()
        try:
            scheme_id = self.db.create_scheme(
                name=name,
                version=self.version_edit.text().strip(),
                remark=self.remark_edit.text().strip(),
                source_file=Path(self.sheet.path).name if self.sheet else "",
                is_flat=flatten,
                items=self.result.items,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "入库失败", str(exc))
            return

        alt_note = ""
        if self.chk_alt.isChecked():
            pairs = collect_alt_pairs(self.result.items)
            if pairs:
                created, merged, touched = self.db.apply_alt_pairs(pairs)
                alt_note = f"\n替代物料组：新增 {created} 组、合并 {merged} 组，涉及 {touched} 个编码。"

        self.window.refresh_all()
        QMessageBox.information(
            self,
            "入库成功",
            f"方案『{name}』已入库，共 {len(self.result.items)} 条物料。{alt_note}",
        )
        self.reset()
        self.window.goto("library")

    def reset(self):
        self.sheet = None
        self.result = None
        self.path_edit.clear()
        self.sheet_combo.clear()
        self.name_edit.clear()
        self.remark_edit.clear()
        self.version_edit.setText("V1.0")
        fill_table(self.table, [])
        self.stats_label.setText("请选择文件后预览")
        self.stats_label.setStyleSheet(f"color: {MUTED};")
        self.import_btn.setEnabled(False)
