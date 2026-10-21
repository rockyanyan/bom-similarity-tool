"""对话框：列映射、方案明细、权重规则、替代组编辑。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import exporter
from ..core.importer import FIELD_LABELS, FIELDS, CleanOptions, SheetData, clean_rows
from ..core.textutil import format_qty
from .common import Card, button, fill_table, make_table, table_item
from .theme import ACCENT, MUTED, RED

FIELD_CHOICES = [("name", "名称"), ("code", "编码"), ("spec", "规格"), ("any", "名称+规格+编码")]


class MappingDialog(QDialog):
    """列映射调整对话框，供文件对比时使用。"""

    def __init__(self, sheet: SheetData, mapping: dict, flatten: bool = False, parent=None):
        super().__init__(parent)
        self.sheet = sheet
        self.setWindowTitle("列映射设置")
        self.resize(560, 620)
        self.mapping = dict(mapping)
        self.flatten = flatten
        self._combos: dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        title = QLabel("把文件列绑定到标准字段")
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        info = QLabel(f"文件：{sheet.path}\n数据行：{len(sheet.rows)} 行 · 共 {len(sheet.headers)} 列")
        info.setObjectName("Muted")
        layout.addWidget(info)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(9)
        for idx, (key, label, _required) in enumerate(FIELDS):
            row, col = divmod(idx, 2)
            box = QVBoxLayout()
            box.setSpacing(3)
            caption = QLabel(label)
            caption.setObjectName("Muted")
            combo = QComboBox()
            combo.addItem("（不映射）", "")
            for header in sheet.headers:
                combo.addItem(header, header)
            if self.mapping.get(key):
                pos = combo.findData(self.mapping[key])
                if pos >= 0:
                    combo.setCurrentIndex(pos)
            combo.currentIndexChanged.connect(self._update_preview)
            self._combos[key] = combo
            box.addWidget(caption)
            box.addWidget(combo)
            grid.addLayout(box, row, col)
        layout.addLayout(grid)

        self.preview_label = QLabel()
        self.preview_label.setObjectName("Muted")
        layout.addWidget(self.preview_label)

        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = button("取消")
        cancel.clicked.connect(self.reject)
        ok = button("应用映射", "primary")
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)
        self._update_preview()

    def _collect(self) -> dict:
        result = {}
        for key, combo in self._combos.items():
            value = combo.currentData()
            if value:
                result[key] = value
        return result

    def _update_preview(self):
        mapping = self._collect()
        missing = [FIELD_LABELS[k] for k in ("code", "qty") if k not in mapping]
        if missing:
            self.preview_label.setText(f"缺少必填字段映射：{'、'.join(missing)}")
            self.preview_label.setStyleSheet(f"color: {RED};")
            return
        try:
            result = clean_rows(self.sheet, mapping, CleanOptions(flatten=self.flatten))
        except Exception as exc:  # noqa: BLE001
            self.preview_label.setText(f"清洗失败：{exc}")
            self.preview_label.setStyleSheet(f"color: {RED};")
            return
        abnormal = sum(1 for item in result.items if item.issues)
        self.preview_label.setStyleSheet(f"color: {MUTED};")
        self.preview_label.setText(
            f"可解析 {len(result.items)} 条物料，异常 {abnormal} 条，跳过 {len(result.skipped)} 行"
        )

    def _accept(self):
        mapping = self._collect()
        if "code" not in mapping or "qty" not in mapping:
            QMessageBox.warning(self, "映射不完整", "『下级编码』与『标准用量』必须映射。")
            return
        self.mapping = mapping
        self.accept()


class ItemDetailDialog(QDialog):
    """查看方案明细。"""

    HEADERS = ["行号", "层级", "下级BOM", "下级编码", "名称", "规格", "单位",
               "标准用量", "展开总用量", "损耗率", "替换物料", "获取途径", "发料中心", "异常"]
    WIDTHS = [56, 50, 90, 130, 180, 200, 50, 80, 92, 66, 140, 90, 90, 130]

    def __init__(self, scheme: dict, items: list, parent=None):
        super().__init__(parent)
        self.scheme = scheme
        self.items = items
        self.setWindowTitle(f"BOM 明细 · {scheme['name']}")
        self.resize(1180, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"{scheme['name']}  {scheme.get('version', '')}")
        title.setObjectName("CardTitle")
        header.addWidget(title)
        meta = QLabel(f"{len(items)} 条物料 · 来源 {scheme.get('source_file') or '手动录入'} · {scheme.get('created_at', '')}")
        meta.setObjectName("Muted")
        header.addWidget(meta)
        header.addStretch(1)
        export_btn = button("导出明细 Excel", "ghost")
        export_btn.clicked.connect(self._export)
        header.addWidget(export_btn)
        layout.addLayout(header)

        table = make_table(self.HEADERS, self.WIDTHS, stretch_last=False)
        rows, colors, aligns = [], [], {}
        for item in items:
            rows.append([
                item.get("row_no"), item.get("level"), item.get("bom_parent"), item.get("code"),
                item.get("name"), item.get("spec"), item.get("unit"),
                format_qty(item.get("qty")), format_qty(item.get("total_qty")),
                item.get("loss_rate"), item.get("alt_text"), item.get("supply"),
                item.get("issue"), "；".join(item.get("issues") or []) or "正常",
            ])
            colors.append(RED if item.get("issues") else None)
        for col in (0, 1, 2, 6, 7, 8, 9):
            aligns[col] = Qt.AlignCenter
        fill_table(table, rows, colors, aligns=aligns)
        layout.addWidget(table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = button("关闭")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)

    def _export(self):
        default = f"{self.scheme['name']}_BOM明细.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "导出 BOM 明细", default, "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            exporter.export_scheme_items(self.scheme, self.items, path)
            QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))


class WeightRuleDialog(QDialog):
    """物料权重规则维护。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("物料权重配置")
        self.resize(760, 640)
        self.current_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        title = QLabel("物料权重规则")
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        tip = QLabel("按顺序匹配，命中第一条规则即取其权重；未命中使用默认权重。主控高、常规阻容中、紧固件最低。")
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self.table = make_table(["规则名", "匹配字段", "关键词", "权重"], [200, 120, 200, 80], stretch_last=True)
        layout.addWidget(self.table, 1)
        self.table.itemSelectionChanged.connect(self._on_select)

        form_card = Card("新增 / 编辑规则")
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("如：主控物料")
        self.field_combo = QComboBox()
        for key, text in FIELD_CHOICES:
            self.field_combo.addItem(text, key)
        self.keyword_edit = QLineEdit()
        self.keyword_edit.setPlaceholderText("如：主控 / 电阻 / 螺丝")
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.01, 100.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(1.0)
        self.weight_spin.setDecimals(2)
        form.addWidget(QLabel("规则名"), 0, 0)
        form.addWidget(self.label_edit, 0, 1)
        form.addWidget(QLabel("匹配字段"), 0, 2)
        form.addWidget(self.field_combo, 0, 3)
        form.addWidget(QLabel("关键词"), 1, 0)
        form.addWidget(self.keyword_edit, 1, 1)
        form.addWidget(QLabel("权重"), 1, 2)
        form.addWidget(self.weight_spin, 1, 3)
        form_card.add_layout(form)

        actions = QHBoxLayout()
        self.save_btn = button("新增规则", "primary")
        self.save_btn.clicked.connect(self._save)
        self.clear_btn = button("清空表单")
        self.clear_btn.clicked.connect(self._clear_form)
        self.delete_btn = button("删除选中", "danger")
        self.delete_btn.clicked.connect(self._delete)
        actions.addWidget(self.save_btn)
        actions.addWidget(self.clear_btn)
        actions.addStretch(1)
        actions.addWidget(self.delete_btn)
        form_card.add_layout(actions)
        layout.addWidget(form_card)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = button("完成", "primary")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        layout.addLayout(bottom)
        self._reload()

    def _reload(self):
        rules = self.db.list_weight_rules()
        field_text = dict(FIELD_CHOICES)
        rows = [[r["label"] or "-", field_text.get(r["field"], r["field"]), r["keyword"], f"{r['weight']:.2f}"] for r in rules]
        fill_table(self.table, rows, aligns={3: Qt.AlignCenter})
        self.rules = rules
        self.delete_btn.setEnabled(bool(rules))

    def _on_select(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rules):
            return
        rule = self.rules[row]
        self.current_id = rule["id"]
        self.label_edit.setText(rule["label"] or "")
        pos = self.field_combo.findData(rule["field"])
        self.field_combo.setCurrentIndex(max(0, pos))
        self.keyword_edit.setText(rule["keyword"])
        self.weight_spin.setValue(float(rule["weight"]))
        self.save_btn.setText("保存修改")

    def _clear_form(self):
        self.current_id = None
        self.label_edit.clear()
        self.keyword_edit.clear()
        self.weight_spin.setValue(1.0)
        self.field_combo.setCurrentIndex(0)
        self.save_btn.setText("新增规则")
        self.table.clearSelection()

    def _save(self):
        keyword = self.keyword_edit.text().strip()
        if not keyword:
            QMessageBox.warning(self, "缺少关键词", "请填写用于匹配的关键词。")
            return
        self.db.save_weight_rule(
            self.current_id,
            self.label_edit.text().strip() or keyword,
            self.field_combo.currentData(),
            keyword,
            self.weight_spin.value(),
            seq=0,
        )
        self._clear_form()
        self._reload()

    def _delete(self):
        if not self.current_id:
            return
        confirm = QMessageBox.question(self, "确认删除", "确定删除该权重规则？")
        if confirm != QMessageBox.Yes:
            return
        self.db.delete_weight_rule(self.current_id)
        self._clear_form()
        self._reload()


class AltGroupDialog(QDialog):
    def __init__(self, name: str = "", note: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("替代物料组")
        self.resize(420, 240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.addWidget(QLabel("组名称"))
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("如：0603 10K 电阻替代组")
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("备注"))
        self.note_edit = QLineEdit(note)
        self.note_edit.setPlaceholderText("可选")
        layout.addWidget(self.note_edit)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = button("取消")
        cancel.clicked.connect(self.reject)
        ok = button("保存", "primary")
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "名称不能为空", "请填写替代组名称。")
            return
        self.accept()

    def values(self):
        return self.name_edit.text().strip(), self.note_edit.text().strip()


class MemberDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加替代物料")
        self.resize(420, 220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        form = QFormLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("必填，如 R0603-10K-1%")
        self.name_edit = QLineEdit()
        self.spec_edit = QLineEdit()
        form.addRow("物料编码", self.code_edit)
        form.addRow("名称", self.name_edit)
        form.addRow("规格", self.spec_edit)
        layout.addLayout(form)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = button("取消")
        cancel.clicked.connect(self.reject)
        ok = button("添加", "primary")
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def _accept(self):
        if not self.code_edit.text().strip():
            QMessageBox.warning(self, "编码不能为空", "请填写物料编码。")
            return
        self.accept()

    def values(self):
        return (
            self.code_edit.text().strip(),
            self.name_edit.text().strip(),
            self.spec_edit.text().strip(),
        )
