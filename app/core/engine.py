"""相似度计算与差异分类引擎。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from .textutil import (
    format_qty,
    material_similarity,
    norm_code,
    norm_text,
    parse_alt_codes,
)

TYPE_EXACT = "完全匹配"
TYPE_ALT = "等价替换匹配"
TYPE_QTY = "数量变更"
TYPE_NEW = "新增物料"
TYPE_MISSING = "缺失物料"
DIFF_TYPES = [TYPE_EXACT, TYPE_ALT, TYPE_QTY, TYPE_NEW, TYPE_MISSING]
KEY_TYPES = {TYPE_ALT, TYPE_NEW, TYPE_MISSING}


@dataclass
class CompareOptions:
    algorithm: str = "cosine"          # cosine | jaccard
    fuzzy_threshold: float = 0.85
    use_alt: bool = True
    diff_supply: bool = False
    diff_issue: bool = False
    high_weight: float = 2.0
    qty_tol: float = 0.001
    default_weight: float = 1.0


@dataclass
class Material:
    index: int
    code: str = ""
    name: str = ""
    spec: str = ""
    unit: str = ""
    qty: float = 0.0
    alt_text: str = ""
    supply: str = ""
    issue: str = ""
    bom_parent: str = ""
    level: int = 1
    weight: float = 1.0
    altset: set = field(default_factory=set)
    groups: set = field(default_factory=set)
    raw: dict = field(default_factory=dict)


@dataclass
class CompareResult:
    score: float
    algorithm: str
    rows: list
    stats: dict
    matched: int
    total_a: int
    total_b: int
    label_a: str
    label_b: str
    time: str
    high_weight_count: int = 0
    warnings: list = field(default_factory=list)

    @property
    def algorithm_label(self) -> str:
        return "加权余弦相似度" if self.algorithm == "cosine" else "加权 Jaccard"


def qty_equal(a, b, tol: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    diff = abs(float(a) - float(b))
    return diff <= max(tol * max(abs(float(a)), abs(float(b))), 1e-9)


class BomComparator:
    def __init__(self, db=None, options: CompareOptions | None = None):
        self.db = db
        self.options = options or CompareOptions()
        self.rules = db.list_weight_rules() if db else []
        self.group_map = db.code_group_map() if (db and self.options.use_alt) else {}
        self.group_index: dict[int, list[int]] = {}

    # ---------- 预处理 ----------
    def _weight_of(self, item: dict) -> float:
        values = {
            "name": norm_text(item.get("name")),
            "code": norm_code(item.get("code")),
            "spec": norm_text(item.get("spec")),
        }
        values["any"] = values["name"] + values["spec"] + values["code"]
        for rule in self.rules:
            keyword = norm_text(rule.get("keyword"))
            if not keyword:
                continue
            target = values.get(rule.get("field", "name"), values["name"])
            if keyword in target:
                return float(rule.get("weight") or self.options.default_weight)
        return float(self.options.default_weight)

    def _prepare(self, items: list[dict]) -> list[Material]:
        materials = []
        for idx, item in enumerate(items):
            code = norm_code(item.get("code") or "")
            altset = set()
            if code:
                altset.add(code)
            if self.options.use_alt:
                for alt in parse_alt_codes(item.get("alt_text") or ""):
                    alt_code = norm_code(alt)
                    if alt_code:
                        altset.add(alt_code)
            groups = set()
            if self.options.use_alt:
                for value in altset:
                    groups |= self.group_map.get(value, set())
            qty = item.get("total_qty")
            if qty is None:
                qty = item.get("qty")
            materials.append(
                Material(
                    index=idx,
                    code=code,
                    name=item.get("name") or "",
                    spec=item.get("spec") or "",
                    unit=item.get("unit") or "",
                    qty=float(qty or 0.0),
                    alt_text=item.get("alt_text") or "",
                    supply=item.get("supply") or "",
                    issue=item.get("issue") or "",
                    bom_parent=item.get("bom_parent") or "",
                    level=int(item.get("level") or 1),
                    weight=self._weight_of(item),
                    altset=altset,
                    groups=groups,
                    raw=item,
                )
            )
        return materials

    # ---------- 匹配 ----------
    def _match(self, mats_a: list[Material], mats_b: list[Material]):
        used_b: set[int] = set()
        pairs: list[tuple[int, int, str]] = []
        matched_a: set[int] = set()

        code_index: dict[str, list[int]] = {}
        alt_index: dict[str, list[int]] = {}
        group_index: dict[int, list[int]] = {}
        for mat in mats_b:
            if mat.code:
                code_index.setdefault(mat.code, []).append(mat.index)
            for value in mat.altset:
                alt_index.setdefault(value, []).append(mat.index)
            for gid in mat.groups:
                group_index.setdefault(gid, []).append(mat.index)

        # 1) 编码完全一致
        for mat in mats_a:
            if not mat.code:
                continue
            for candidate in code_index.get(mat.code, []):
                if candidate not in used_b:
                    used_b.add(candidate)
                    matched_a.add(mat.index)
                    pairs.append((mat.index, candidate, "exact"))
                    break

        # 2) 替代物料组 / 替换物料交叉引用
        if self.options.use_alt:
            for mat in mats_a:
                if mat.index in matched_a:
                    continue
                scores: dict[int, int] = {}
                for gid in mat.groups:
                    for candidate in group_index.get(gid, []):
                        if candidate not in used_b:
                            scores[candidate] = max(scores.get(candidate, 0), 400)
                for value in mat.altset:
                    for candidate in alt_index.get(value, []):
                        if candidate not in used_b:
                            scores[candidate] = max(scores.get(candidate, 0), 500)
                    for candidate in code_index.get(value, []):
                        if candidate not in used_b:
                            scores[candidate] = max(scores.get(candidate, 0), 700 if value == mat.code else 450)
                if not scores:
                    continue
                best = max(scores.items(), key=lambda kv: (kv[1], -kv[0]))[0]
                used_b.add(best)
                matched_a.add(mat.index)
                pairs.append((mat.index, best, "alt"))

        # 3) 编码为空时按名称+规格模糊匹配
        threshold = self.options.fuzzy_threshold
        unmatched_b = [m for m in mats_b if m.index not in used_b]
        if unmatched_b and threshold < 1.0:
            for mat in mats_a:
                if mat.index in matched_a:
                    continue
                if not (mat.name or mat.spec):
                    continue
                best_score, best_mat = 0.0, None
                for candidate in unmatched_b:
                    if candidate.index in used_b:
                        continue
                    if mat.code and candidate.code:
                        continue  # 双方都有编码时不做模糊匹配，避免误判
                    score = material_similarity(mat.name, mat.spec, candidate.name, candidate.spec)
                    if score > best_score:
                        best_score, best_mat = score, candidate
                if best_mat is not None and best_score >= threshold:
                    used_b.add(best_mat.index)
                    matched_a.add(mat.index)
                    pairs.append((mat.index, best_mat.index, "fuzzy"))

        return pairs, matched_a, used_b

    # ---------- 主流程 ----------
    def compare(self, items_a: list[dict], items_b: list[dict],
                label_a: str = "库内方案", label_b: str = "新BOM") -> CompareResult:
        mats_a = self._prepare(items_a)
        mats_b = self._prepare(items_b)
        pairs, matched_a, used_b = self._match(mats_a, mats_b)

        pair_weight = 0.0
        union_weight = 0.0
        dot = norm_a = norm_b = 0.0
        rows: list[dict] = []
        stats = {name: 0 for name in DIFF_TYPES}

        for ia, ib, match_type in pairs:
            a, b = mats_a[ia], mats_b[ib]
            weight = (a.weight + b.weight) / 2
            pair_weight += weight
            union_weight += weight

            va = a.qty * a.weight
            vb = b.qty * b.weight
            dot += va * vb
            norm_a += va * va
            norm_b += vb * vb

            code_same = bool(a.code and b.code and a.code == b.code)
            qty_same = qty_equal(a.qty, b.qty, self.options.qty_tol)

            extra = []
            if self.options.diff_supply and norm_text(a.supply) != norm_text(b.supply):
                extra.append("获取途径变更")
            if self.options.diff_issue and norm_text(a.issue) != norm_text(b.issue):
                extra.append("发料中心变更")

            if code_same:
                diff_type = TYPE_EXACT if qty_same else TYPE_QTY
                note = "" if qty_same else "用量变更"
            else:
                diff_type = TYPE_ALT
                note = "名称+规格模糊匹配" if match_type == "fuzzy" else "替代物料等价"
                if not qty_same:
                    note += "；用量同时变更"

            name = a.name if norm_text(a.name) == norm_text(b.name) else f"{a.name} → {b.name}"
            spec = a.spec if norm_text(a.spec) == norm_text(b.spec) else f"{a.spec} → {b.spec}"
            delta = b.qty - a.qty
            delta_pct = (delta / a.qty * 100) if a.qty else None

            highlight = weight >= self.options.high_weight and diff_type in KEY_TYPES
            stats[diff_type] += 1
            rows.append(
                {
                    "type": diff_type,
                    "code_a": a.code,
                    "code_b": b.code,
                    "name": name,
                    "spec": spec,
                    "unit": a.unit or b.unit,
                    "qty_a": a.qty,
                    "qty_b": b.qty,
                    "delta": delta,
                    "delta_pct": delta_pct,
                    "weight": weight,
                    "supply_a": a.supply,
                    "supply_b": b.supply,
                    "issue_a": a.issue,
                    "issue_b": b.issue,
                    "bom_parent": a.bom_parent or b.bom_parent,
                    "level": max(a.level, b.level),
                    "alt_text": a.alt_text or b.alt_text,
                    "extra": "、".join(extra),
                    "note": note,
                    "highlight": highlight,
                    "match": match_type,
                }
            )

        for mat in mats_a:
            if mat.index in matched_a:
                continue
            union_weight += mat.weight
            norm_a += (mat.qty * mat.weight) ** 2
            stats[TYPE_MISSING] += 1
            rows.append(self._single_row(mat, TYPE_MISSING, "a"))

        for mat in mats_b:
            if mat.index in used_b:
                continue
            union_weight += mat.weight
            norm_b += (mat.qty * mat.weight) ** 2
            stats[TYPE_NEW] += 1
            rows.append(self._single_row(mat, TYPE_NEW, "b"))

        if self.options.algorithm == "jaccard":
            score = pair_weight / union_weight if union_weight > 0 else 0.0
        else:
            denominator = math.sqrt(norm_a) * math.sqrt(norm_b)
            if denominator <= 0:
                score = 1.0 if not mats_a and not mats_b else 0.0
            else:
                score = dot / denominator

        order = {name: i for i, name in enumerate(DIFF_TYPES)}
        rows.sort(key=lambda r: (order.get(r["type"], 9), -(r["weight"] or 0), r["code_a"] or r["code_b"]))

        warnings = []
        unit_pairs = [
            (mats_a[ia], mats_b[ib])
            for ia, ib, _ in pairs
            if mats_a[ia].unit and mats_b[ib].unit and mats_a[ia].unit != mats_b[ib].unit
        ]
        if unit_pairs:
            warnings.append(f"{len(unit_pairs)} 项物料单位不一致，已按数值直接比较，需人工复核。")
        if any(r["highlight"] for r in rows):
            warnings.append("高权重物料存在新增/缺失/替换，已在明细中标红，需人工复核。")

        return CompareResult(
            score=round(score * 100, 2),
            algorithm=self.options.algorithm,
            rows=rows,
            stats=stats,
            matched=len(pairs),
            total_a=len(mats_a),
            total_b=len(mats_b),
            label_a=label_a,
            label_b=label_b,
            time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            high_weight_count=sum(1 for r in rows if r["highlight"]),
            warnings=warnings,
        )

    def _single_row(self, mat: Material, diff_type: str, side: str) -> dict:
        highlight = mat.weight >= self.options.high_weight
        return {
            "type": diff_type,
            "code_a": mat.code if side == "a" else "",
            "code_b": mat.code if side == "b" else "",
            "name": mat.name,
            "spec": mat.spec,
            "unit": mat.unit,
            "qty_a": mat.qty if side == "a" else None,
            "qty_b": mat.qty if side == "b" else None,
            "delta": None,
            "delta_pct": None,
            "weight": mat.weight,
            "supply_a": mat.supply if side == "a" else "",
            "supply_b": mat.supply if side == "b" else "",
            "issue_a": mat.issue if side == "a" else "",
            "issue_b": mat.issue if side == "b" else "",
            "bom_parent": mat.bom_parent,
            "level": mat.level,
            "alt_text": mat.alt_text,
            "extra": "",
            "note": "库内有、新BOM无" if side == "a" else "新BOM有、库内无",
            "highlight": highlight,
            "match": "",
        }


def batch_compare(db, target_items: list[dict], target_label: str,
                  options: CompareOptions, scheme_ids: list[int] | None = None):
    """新 BOM 与库内全部（或指定）方案批量比对，按相似度降序返回。"""
    comparator = BomComparator(db, options)
    results = []
    for scheme in db.list_schemes():
        if scheme_ids is not None and scheme["id"] not in scheme_ids:
            continue
        items = db.get_items(scheme["id"])
        if not items:
            continue
        result = comparator.compare(
            items,
            target_items,
            label_a=f"{scheme['name']} {scheme['version']}".strip(),
            label_b=target_label,
        )
        result.scheme_id = scheme["id"]
        result.scheme_name = scheme["name"]
        result.scheme_version = scheme["version"]
        results.append(result)
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def row_to_text(row: dict) -> dict:
    """把差异行转成便于导出/展示的字符串值。"""
    return {
        "差异类型": row["type"],
        "层级": row["level"],
        "下级BOM": row["bom_parent"],
        "库内编码": row["code_a"],
        "新BOM编码": row["code_b"],
        "名称": row["name"],
        "规格": row["spec"],
        "单位": row["unit"],
        "库内标准用量": format_qty(row["qty_a"]),
        "新BOM标准用量": format_qty(row["qty_b"]),
        "用量变化": ("+" if (row["delta"] or 0) > 0 else "") + format_qty(row["delta"])
        if row["delta"] is not None else "",
        "变化率": f"{row['delta_pct']:.2f}%" if row["delta_pct"] is not None else "",
        "权重": f"{row['weight']:.2f}",
        "库内获取途径": row["supply_a"],
        "新BOM获取途径": row["supply_b"],
        "库内发料中心": row["issue_a"],
        "新BOM发料中心": row["issue_b"],
        "替换物料": row["alt_text"],
        "附加差异": row["extra"],
        "说明": row["note"],
    }
