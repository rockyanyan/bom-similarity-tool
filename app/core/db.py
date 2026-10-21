"""SQLite 数据层：BOM 方案库、明细、替代物料组、权重规则、映射模板。"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


DATA_DIR = app_dir() / "data"
DB_PATH = DATA_DIR / "bom_library.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scheme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT DEFAULT '',
    remark TEXT DEFAULT '',
    source_file TEXT DEFAULT '',
    is_flat INTEGER DEFAULT 0,
    item_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id INTEGER NOT NULL,
    row_no INTEGER DEFAULT 0,
    bom_parent TEXT DEFAULT '',
    code TEXT DEFAULT '',
    name TEXT DEFAULT '',
    spec TEXT DEFAULT '',
    unit TEXT DEFAULT '',
    qty REAL,
    loss_rate TEXT DEFAULT '',
    alt_text TEXT DEFAULT '',
    supply TEXT DEFAULT '',
    issue TEXT DEFAULT '',
    level INTEGER DEFAULT 1,
    total_qty REAL,
    issues TEXT DEFAULT '[]',
    FOREIGN KEY (scheme_id) REFERENCES scheme(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_item_scheme ON item(scheme_id);
CREATE INDEX IF NOT EXISTS idx_item_code ON item(code);

CREATE TABLE IF NOT EXISTS alt_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    note TEXT DEFAULT '',
    source TEXT DEFAULT 'manual',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alt_member (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT DEFAULT '',
    spec TEXT DEFAULT '',
    FOREIGN KEY (group_id) REFERENCES alt_group(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_member_code ON alt_member(code);
CREATE INDEX IF NOT EXISTS idx_member_group ON alt_member(group_id);

CREATE TABLE IF NOT EXISTS weight_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seq INTEGER DEFAULT 0,
    label TEXT DEFAULT '',
    field TEXT DEFAULT 'name',
    keyword TEXT NOT NULL,
    weight REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS map_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mapping TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS setting (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

DEFAULT_RULES = [
    ("主控物料", "name", "主控", 3.0),
    ("主控/MCU 相关", "name", "MCU", 3.0),
    ("芯片 IC", "name", "芯片", 2.0),
    ("模块/模组", "name", "模块", 2.0),
    ("模组", "name", "模组", 2.0),
    ("阻容感等常规物料", "name", "电阻", 1.0),
    ("电容", "name", "电容", 1.0),
    ("紧固件（最低权重）", "name", "螺丝", 0.5),
    ("螺钉", "name", "螺钉", 0.5),
    ("螺母/垫片", "name", "螺母", 0.5),
    ("紧固件", "name", "紧固件", 0.5),
]

DEFAULT_SETTINGS = {
    "algorithm": "cosine",
    "fuzzy_threshold": "0.85",
    "high_weight": "2.0",
    "diff_supply": "0",
    "diff_issue": "0",
    "default_weight": "1.0",
    "qty_tolerance": "0.001",
}


class DB:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._seed()
        self.conn.commit()

    # ---------- 基础 ----------
    def _seed(self):
        cursor = self.conn.execute("SELECT COUNT(*) AS c FROM weight_rule")
        if cursor.fetchone()["c"] == 0:
            for seq, (label, field, keyword, weight) in enumerate(DEFAULT_RULES):
                self.conn.execute(
                    "INSERT INTO weight_rule(seq,label,field,keyword,weight) VALUES(?,?,?,?,?)",
                    (seq, label, field, keyword, weight),
                )
        for key, value in DEFAULT_SETTINGS.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO setting(key,value) VALUES(?,?)", (key, value)
            )

    def close(self):
        self.conn.commit()
        self.conn.close()

    # ---------- 设置 ----------
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM setting WHERE key=?", (key,)).fetchone()
        return row["value"] if row and row["value"] is not None else default

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO setting(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    # ---------- 方案 ----------
    def create_scheme(self, name, version="", remark="", source_file="", is_flat=0, items=None):
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.execute(
            "INSERT INTO scheme(name,version,remark,source_file,is_flat,item_count,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (name, version, remark, source_file, 1 if is_flat else 0, len(items or []), created),
        )
        scheme_id = cursor.lastrowid
        if items:
            self.insert_items(scheme_id, items)
        self.conn.commit()
        return scheme_id

    def insert_items(self, scheme_id: int, items):
        rows = []
        for item in items:
            rows.append(
                (
                    scheme_id,
                    getattr(item, "row_no", 0),
                    getattr(item, "bom_parent", ""),
                    getattr(item, "code", ""),
                    getattr(item, "name", ""),
                    getattr(item, "spec", ""),
                    getattr(item, "unit", ""),
                    getattr(item, "qty", None),
                    getattr(item, "loss_rate", ""),
                    getattr(item, "alt_text", ""),
                    getattr(item, "supply", ""),
                    getattr(item, "issue", ""),
                    getattr(item, "level", 1),
                    getattr(item, "total_qty", None),
                    json.dumps(getattr(item, "issues", []), ensure_ascii=False),
                )
            )
        self.conn.executemany(
            "INSERT INTO item(scheme_id,row_no,bom_parent,code,name,spec,unit,qty,loss_rate,"
            "alt_text,supply,issue,level,total_qty,issues) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self.conn.execute(
            "UPDATE scheme SET item_count=(SELECT COUNT(*) FROM item WHERE scheme_id=?) WHERE id=?",
            (scheme_id, scheme_id),
        )
        self.conn.commit()

    def list_schemes(self, keyword: str = ""):
        sql = (
            "SELECT s.*, (SELECT COUNT(*) FROM item i WHERE i.scheme_id=s.id) AS items "
            "FROM scheme s"
        )
        params = ()
        if keyword:
            sql += " WHERE s.name LIKE ? OR s.version LIKE ? OR s.remark LIKE ?"
            like = f"%{keyword}%"
            params = (like, like, like)
        sql += " ORDER BY s.id DESC"
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def get_scheme(self, scheme_id: int):
        row = self.conn.execute("SELECT * FROM scheme WHERE id=?", (scheme_id,)).fetchone()
        return dict(row) if row else None

    def delete_scheme(self, scheme_id: int):
        self.conn.execute("DELETE FROM item WHERE scheme_id=?", (scheme_id,))
        self.conn.execute("DELETE FROM scheme WHERE id=?", (scheme_id,))
        self.conn.commit()

    def update_scheme(self, scheme_id, name, version, remark):
        self.conn.execute(
            "UPDATE scheme SET name=?, version=?, remark=? WHERE id=?",
            (name, version, remark, scheme_id),
        )
        self.conn.commit()

    def get_items(self, scheme_id: int):
        rows = self.conn.execute(
            "SELECT * FROM item WHERE scheme_id=? ORDER BY row_no, id", (scheme_id,)
        ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            try:
                data["issues"] = json.loads(data.get("issues") or "[]")
            except (json.JSONDecodeError, TypeError):
                data["issues"] = []
            result.append(data)
        return result

    # ---------- 替代物料组 ----------
    def list_alt_groups(self, keyword: str = ""):
        sql = (
            "SELECT g.*, (SELECT COUNT(*) FROM alt_member m WHERE m.group_id=g.id) AS members "
            "FROM alt_group g"
        )
        params = ()
        if keyword:
            sql += " WHERE g.name LIKE ?"
            params = (f"%{keyword}%",)
        sql += " ORDER BY g.id"
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def get_alt_group(self, group_id: int):
        row = self.conn.execute("SELECT * FROM alt_group WHERE id=?", (group_id,)).fetchone()
        return dict(row) if row else None

    def create_alt_group(self, name, note="", source="manual", codes=None):
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.execute(
            "INSERT INTO alt_group(name,note,source,created_at) VALUES(?,?,?,?)",
            (name, note, source, created),
        )
        group_id = cursor.lastrowid
        for code in codes or []:
            self.add_alt_member(group_id, code)
        self.conn.commit()
        return group_id

    def rename_alt_group(self, group_id, name, note):
        self.conn.execute(
            "UPDATE alt_group SET name=?, note=? WHERE id=?", (name, note, group_id)
        )
        self.conn.commit()

    def delete_alt_group(self, group_id):
        self.conn.execute("DELETE FROM alt_member WHERE group_id=?", (group_id,))
        self.conn.execute("DELETE FROM alt_group WHERE id=?", (group_id,))
        self.conn.commit()

    def list_alt_members(self, group_id):
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM alt_member WHERE group_id=? ORDER BY id", (group_id,)
            ).fetchall()
        ]

    def add_alt_member(self, group_id, code, name="", spec=""):
        exists = self.conn.execute(
            "SELECT id FROM alt_member WHERE group_id=? AND code=?", (group_id, code)
        ).fetchone()
        if exists:
            return exists["id"]
        cursor = self.conn.execute(
            "INSERT INTO alt_member(group_id,code,name,spec) VALUES(?,?,?,?)",
            (group_id, code, name, spec),
        )
        self.conn.commit()
        return cursor.lastrowid

    def delete_alt_member(self, member_id):
        self.conn.execute("DELETE FROM alt_member WHERE id=?", (member_id,))
        self.conn.commit()

    def merge_alt_groups(self, target_id, source_ids):
        for gid in source_ids:
            if gid == target_id:
                continue
            for member in self.list_alt_members(gid):
                self.add_alt_member(target_id, member["code"], member["name"], member["spec"])
            self.delete_alt_group(gid)
        self.conn.commit()

    def code_group_map(self) -> dict[str, set[int]]:
        """编码 → 所属替代组 id 集合。"""
        result: dict[str, set[int]] = {}
        for row in self.conn.execute("SELECT group_id, code FROM alt_member").fetchall():
            result.setdefault(row["code"], set()).add(row["group_id"])
        return result

    def apply_alt_pairs(self, pairs):
        """把（同组编码列表）合并进替代组：新建 / 追加 / 合并已有组，保留手工维护的组。

        pairs: [(codes, name, spec), ...]
        返回 (新建组数, 合并组数, 涉及编码数)
        """
        from .textutil import norm_code

        created = merged = 0
        touched: set[str] = set()
        for codes, name, _spec in pairs:
            members = []
            for code in codes:
                normalized = norm_code(code)
                if normalized and normalized not in members:
                    members.append(normalized)
            if len(members) < 2:
                continue
            placeholders = ",".join("?" * len(members))
            rows = self.conn.execute(
                f"SELECT DISTINCT group_id FROM alt_member WHERE code IN ({placeholders})",
                members,
            ).fetchall()
            group_ids = {row["group_id"] for row in rows}
            if group_ids:
                target = min(group_ids)
                for other in sorted(group_ids - {target}):
                    self.merge_alt_groups(target, [other])
                    merged += 1
            else:
                target = self.create_alt_group(
                    f"替代组-{members[0]}"[:60], "由替换物料自动解析生成", "auto", members
                )
                created += 1
            for code in members:
                self.add_alt_member(target, code)
                touched.add(code)
        self.conn.commit()
        return created, merged, len(touched)

    def rebuild_alt_groups_from_items(self):
        """扫描方案库全部明细的替换物料文本，增量合并替代组（不清空手工组）。"""
        from .textutil import parse_alt_codes

        pairs = []
        for row in self.conn.execute(
            "SELECT DISTINCT code, alt_text, name FROM item WHERE alt_text<>''"
        ).fetchall():
            code = (row["code"] or "").strip()
            alts = [c for c in parse_alt_codes(row["alt_text"]) if c]
            if not alts:
                continue
            members = ([code] if code else []) + alts
            if len(members) >= 2:
                pairs.append((members, row["name"], ""))
        return self.apply_alt_pairs(pairs)

    # ---------- 权重规则 ----------
    def list_weight_rules(self):
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM weight_rule ORDER BY seq, id"
            ).fetchall()
        ]

    def save_weight_rule(self, rule_id, label, field, keyword, weight, seq=0):
        if rule_id:
            self.conn.execute(
                "UPDATE weight_rule SET label=?, field=?, keyword=?, weight=?, seq=? WHERE id=?",
                (label, field, keyword, weight, seq, rule_id),
            )
        else:
            self.conn.execute(
                "INSERT INTO weight_rule(seq,label,field,keyword,weight) VALUES(?,?,?,?,?)",
                (seq, label, field, keyword, weight),
            )
        self.conn.commit()

    def delete_weight_rule(self, rule_id):
        self.conn.execute("DELETE FROM weight_rule WHERE id=?", (rule_id,))
        self.conn.commit()

    # ---------- 映射模板 ----------
    def list_templates(self):
        return [
            dict(row)
            for row in self.conn.execute("SELECT * FROM map_template ORDER BY id DESC").fetchall()
        ]

    def save_template(self, name, mapping: dict):
        exists = self.conn.execute(
            "SELECT id FROM map_template WHERE name=?", (name,)
        ).fetchone()
        payload = json.dumps(mapping, ensure_ascii=False)
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if exists:
            self.conn.execute(
                "UPDATE map_template SET mapping=?, created_at=? WHERE id=?",
                (payload, created, exists["id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO map_template(name,mapping,created_at) VALUES(?,?,?)",
                (name, payload, created),
            )
        self.conn.commit()

    def delete_template(self, template_id):
        self.conn.execute("DELETE FROM map_template WHERE id=?", (template_id,))
        self.conn.commit()

    # ---------- 统计 ----------
    def stats(self):
        schemes = self.conn.execute("SELECT COUNT(*) AS c FROM scheme").fetchone()["c"]
        items = self.conn.execute("SELECT COUNT(*) AS c FROM item").fetchone()["c"]
        groups = self.conn.execute("SELECT COUNT(*) AS c FROM alt_group").fetchone()["c"]
        return {"schemes": schemes, "items": items, "groups": groups}
