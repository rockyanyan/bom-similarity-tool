"""替代物料组管理页面。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..core.textutil import norm_code, parse_alt_codes
from .common import Card, button, fill_table, make_table
from .dialogs import AltGroupDialog, MemberDialog
from .theme import GREEN, MUTED, ORANGE


class AltGroupPage(QWidget):
    GROUP_HEADERS = ["组名称", "成员数", "来源", "备注"]
    GROUP_WIDTHS = [220, 60, 70, 150]
    MEMBER_HEADERS = ["物料编码", "名称", "规格"]
    MEMBER_WIDTHS = [180, 200, 240]

    def __init__(self, db, window):
        super().__init__()
        self.db = db
        self.window = window
        self.groups: list[dict] = []
        self.members: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("替代物料组")
        title.setObjectName("PageTitle")
        self.subtitle = QLabel("等价物料判定依据：同一替代组内的编码视为可互换")
        self.subtitle.setObjectName("PageSubtitle")
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        parse_btn = button("从方案库自动解析", "primary")
        parse_btn.clicked.connect(self.auto_parse)
        check_btn = button("校验循环引用")
        check_btn.clicked.connect(self.validate)
        header.addWidget(check_btn)
        header.addWidget(parse_btn)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        left_card = Card("替代组列表")
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索组名称…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.reload_groups)
        search_row.addWidget(self.search, 1)
        left_card.add_layout(search_row)

        self.group_table = make_table(self.GROUP_HEADERS, self.GROUP_WIDTHS, stretch_last=True)
        self.group_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.group_table.itemSelectionChanged.connect(self.load_members)
        left_card.add(self.group_table)

        actions = QHBoxLayout()
        add_btn = button("新增组", "primary")
        add_btn.clicked.connect(self.add_group)
        rename_btn = button("重命名")
        rename_btn.clicked.connect(self.rename_group)
        merge_btn = button("合并所选")
        merge_btn.clicked.connect(self.merge_groups)
        del_btn = button("删除", "danger")
        del_btn.clicked.connect(self.delete_group)
        actions.addWidget(add_btn)
        actions.addWidget(rename_btn)
        actions.addWidget(merge_btn)
        actions.addStretch(1)
        actions.addWidget(del_btn)
        left_card.add_layout(actions)
        body.addWidget(left_card, 3)

        right_card = Card("组内物料", "同一组内编码互为替代")
        self.member_hint = QLabel("请选择左侧替代组")
        self.member_hint.setObjectName("Muted")
        right_card.add(self.member_hint)
        self.member_table = make_table(self.MEMBER_HEADERS, self.MEMBER_WIDTHS, stretch_last=True)
        right_card.add(self.member_table)
        member_actions = QHBoxLayout()
        add_member = button("添加物料", "primary")
        add_member.clicked.connect(self.add_member)
        del_member = button("移除所选", "danger")
        del_member.clicked.connect(self.delete_member)
        member_actions.addWidget(add_member)
        member_actions.addStretch(1)
        member_actions.addWidget(del_member)
        right_card.add_layout(member_actions)
        body.addWidget(right_card, 2)

        layout.addLayout(body, 1)

    # ---------- 刷新 ----------
    def refresh(self):
        self.reload_groups()

    def reload_groups(self):
        keyword = self.search.text().strip()
        self.groups = self.db.list_alt_groups(keyword)
        source_text = {"manual": "手工", "auto": "自动"}
        rows = [[g["name"], g["members"], source_text.get(g["source"], g["source"]),
                 g["note"] or ""] for g in self.groups]
        fill_table(self.group_table, rows, aligns={1: Qt.AlignCenter, 2: Qt.AlignCenter})
        total_members = sum(g["members"] for g in self.groups)
        self.subtitle.setText(
            f"等价物料判定依据：同一替代组内的编码视为可互换 · 共 {len(self.groups)} 组 / {total_members} 个编码"
        )
        if self.groups:
            self.group_table.selectRow(0)
        else:
            self.load_members()

    def current_group(self):
        row = self.group_table.currentRow()
        if 0 <= row < len(self.groups):
            return self.groups[row]
        return None

    def selected_groups(self):
        rows = sorted({index.row() for index in self.group_table.selectedIndexes()})
        return [self.groups[r] for r in rows if 0 <= r < len(self.groups)]

    def load_members(self):
        group = self.current_group()
        if not group:
            self.members = []
            fill_table(self.member_table, [])
            self.member_hint.setText("请选择左侧替代组")
            return
        self.members = self.db.list_alt_members(group["id"])
        rows = [[m["code"], m["name"], m["spec"]] for m in self.members]
        fill_table(self.member_table, rows)
        self.member_hint.setText(f"{group['name']} · {len(self.members)} 个编码")

    # ---------- 操作 ----------
    def add_group(self):
        dialog = AltGroupDialog(parent=self)
        if dialog.exec():
            name, note = dialog.values()
            self.db.create_alt_group(name, note, "manual")
            self.reload_groups()
            self.window.refresh_all()

    def rename_group(self):
        group = self.current_group()
        if not group:
            QMessageBox.information(self, "提示", "请先选择一个替代组。")
            return
        dialog = AltGroupDialog(group["name"], group["note"] or "", self)
        if dialog.exec():
            name, note = dialog.values()
            self.db.rename_alt_group(group["id"], name, note)
            self.reload_groups()

    def delete_group(self):
        group = self.current_group()
        if not group:
            QMessageBox.information(self, "提示", "请先选择一个替代组。")
            return
        if QMessageBox.question(self, "删除替代组", f"确定删除『{group['name']}』及其成员？") != QMessageBox.Yes:
            return
        self.db.delete_alt_group(group["id"])
        self.reload_groups()
        self.window.refresh_all()

    def merge_groups(self):
        selected = self.selected_groups()
        if len(selected) < 2:
            QMessageBox.information(self, "提示", "请按住 Ctrl 选择至少两个替代组再合并。")
            return
        target, others = selected[0], selected[1:]
        names = "、".join(g["name"] for g in others)
        if QMessageBox.question(
            self, "合并替代组",
            f"将 {names} 合并到『{target['name']}』？\n合并后编码不可互换的成员会一起参与等价判定，请确认。",
        ) != QMessageBox.Yes:
            return
        self.db.merge_alt_groups(target["id"], [g["id"] for g in others])
        self.reload_groups()
        self.window.refresh_all()

    def add_member(self):
        group = self.current_group()
        if not group:
            QMessageBox.information(self, "提示", "请先选择一个替代组。")
            return
        dialog = MemberDialog(self)
        if dialog.exec():
            code, name, spec = dialog.values()
            self.db.add_alt_member(group["id"], norm_code(code), name, spec)
            self.reload_groups()
            self.load_members()
            self.window.refresh_all()

    def delete_member(self):
        row = self.member_table.currentRow()
        if row < 0 or row >= len(self.members):
            QMessageBox.information(self, "提示", "请先选择要移除的物料。")
            return
        self.db.delete_alt_member(self.members[row]["id"])
        self.load_members()
        self.reload_groups()
        self.window.refresh_all()

    # ---------- 自动解析 / 校验 ----------
    def auto_parse(self):
        try:
            created, merged, touched = self.db.rebuild_alt_groups_from_items()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "解析失败", str(exc))
            return
        self.reload_groups()
        self.window.refresh_all()
        QMessageBox.information(
            self, "自动解析完成",
            f"从方案库替换物料文本解析：新增 {created} 组、合并 {merged} 组、涉及 {touched} 个编码。\n"
            "手工维护的组不会被删除。",
        )

    def validate(self):
        issues: list[str] = []
        groups = self.db.list_alt_groups()
        code_groups: dict[str, list[str]] = {}
        for group in groups:
            members = self.db.list_alt_members(group["id"])
            if len(members) < 2:
                issues.append(f"『{group['name']}』只有 {len(members)} 个编码，无法构成替代关系。")
            for member in members:
                code_groups.setdefault(member["code"], []).append(group["name"])

        duplicated = {code: names for code, names in code_groups.items() if len(names) > 1}
        for code, names in list(duplicated.items())[:20]:
            issues.append(f"编码 {code} 同时属于多个替代组：{'、'.join(names)}，建议合并。")

        self_ref = []
        for row in self.db.conn.execute(
            "SELECT code, alt_text FROM item WHERE alt_text<>''"
        ).fetchall():
            code = norm_code(row["code"])
            alts = {norm_code(c) for c in parse_alt_codes(row["alt_text"])}
            if code and code in alts:
                self_ref.append(code)
        for code in self_ref[:20]:
            issues.append(f"编码 {code} 的替换物料中引用了自身，已自动忽略。")

        cyclic = []
        for scheme in self.db.list_schemes():
            for item in self.db.get_items(scheme["id"]):
                if "BOM 循环嵌套" in (item.get("issues") or []):
                    cyclic.append(f"{scheme['name']}/{item['code'] or item['row_no']}")
        for name in cyclic[:10]:
            issues.append(f"BOM 层级循环嵌套：{name}，展开时已跳过父级加倍。")

        if not issues:
            QMessageBox.information(self, "校验通过", "未发现替代组循环引用或异常配置。")
            return
        text = "\n".join(f"· {line}" for line in issues[:40])
        QMessageBox.warning(self, "校验结果", f"发现 {len(issues)} 项待处理：\n\n{text}")
