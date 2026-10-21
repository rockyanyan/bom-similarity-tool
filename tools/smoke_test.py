"""核心逻辑冒烟测试（不启动 GUI）。"""
from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import asdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.core.db import DB
from app.core.engine import BomComparator, CompareOptions, batch_compare
from app.core.exporter import export_report
from app.core.importer import (
    CleanOptions,
    SheetData,
    auto_mapping,
    clean_rows,
    collect_alt_pairs,
    read_file,
)

SAMPLES = os.path.join(ROOT, "示例数据")


def load(path):
    sheet = read_file(path)
    mapping = auto_mapping(sheet.headers)
    print(f"[read] {os.path.basename(path)} sheet={sheet.active_sheet} rows={len(sheet.rows)}")
    print("       mapping:", mapping)
    result = clean_rows(sheet, mapping, CleanOptions())
    print(f"       items={len(result.items)} skipped={len(result.skipped)} warnings={result.warnings}")
    return result


def main():
    workdir = tempfile.mkdtemp(prefix="bomtest_")
    db_path = os.path.join(workdir, "test.db")
    db = DB(db_path)

    r10 = load(os.path.join(SAMPLES, "A03电源板_V1.0.xlsx"))
    r11 = load(os.path.join(SAMPLES, "A03电源板_V1.1.xlsx"))
    rb07 = load(os.path.join(SAMPLES, "B07控制板_BOM.csv"))

    pairs = collect_alt_pairs(r10.items)
    print(f"[alt] pairs={len(pairs)} apply={db.apply_alt_pairs(pairs)}")
    print(f"[alt] apply again (idempotent)={db.apply_alt_pairs(pairs)}")

    id_a = db.create_scheme("A03 电源板", "V1.0", "基线版本", "A03电源板_V1.0.xlsx", 0, r10.items)
    id_b = db.create_scheme("A03 电源板", "V1.1", "改版", "A03电源板_V1.1.xlsx", 0, r11.items)
    id_c = db.create_scheme("B07 控制板", "V1.0", "另一块板", "B07控制板_BOM.csv", 0, rb07.items)
    print(f"[db] schemes={db.stats()}")

    items_a = db.get_items(id_a)
    items_b = db.get_items(id_b)
    for algo in ("cosine", "jaccard"):
        options = CompareOptions(algorithm=algo, diff_supply=True)
        result = BomComparator(db, options).compare(items_a, items_b, "A03 V1.0", "A03 V1.1")
        print(f"[compare:{algo}] score={result.score} matched={result.matched} stats={result.stats}")
        for row in result.rows:
            print("   ", row["type"], "|", row["code_a"], "->", row["code_b"],
                  "|", row["name"], "|", row["qty_a"], "->", row["qty_b"],
                  "| extra:", row["extra"], "| highlight:", row["highlight"])

    options = CompareOptions(algorithm="cosine", diff_supply=True, diff_issue=True)
    report = os.path.join(workdir, "report.xlsx")
    export_report(result, report, options)
    print(f"[export] {report} exists={os.path.exists(report)} size={os.path.getsize(report)}")

    # 批量
    results = batch_compare(db, [asdict(i) for i in r11.items], "A03 V1.1", options)
    print("[batch]", [(r.scheme_name, r.scheme_version, r.score) for r in results])

    # 多层展开 + 循环检测
    headers = ["下级BOM", "下级编码", "名称", "规格", "单位", "标准用量", "损耗率", "替换物料", "获取途径", "发料中心"]
    rows = [
        ["1", "P1", "半成品A", "模块", "PCS", 2, "", "", "", ""],
        ["1.1", "P2", "子件B", "模块", "PCS", 3, "", "", "", ""],
        ["1.1.1", "P3", "零件C", "螺丝", "PCS", 4, "", "", "", ""],
        ["b", "a", "循环X", "模块", "PCS", 1, "", "", "", ""],
        ["a", "b", "循环Y", "模块", "PCS", 1, "", "", "", ""],
    ]
    sheet = SheetData("memory", headers, rows, ["sheet1"], "sheet1", 0)
    mapping = auto_mapping(headers)
    flat = clean_rows(sheet, mapping, CleanOptions(flatten=True))
    for item in flat.items:
        print(f"[flatten] {item.bom_parent:<6} {item.code:<3} qty={item.qty} total={item.total_qty} level={item.level} issues={item.issues}")

    # 模糊匹配（编码为空）
    headers2 = ["下级BOM", "下级编码", "名称", "规格", "单位", "标准用量", "损耗率", "替换物料", "获取途径", "发料中心"]
    left = [["1", "", "贴片电阻 10K", "0603 10K 1%", "PCS", 2, "", "", "", ""]]
    right = [["1", "", "贴片电阻10K", "0603 10K 1%", "PCS", 2, "", "", "", ""]]
    a = clean_rows(SheetData("l", headers2, left, ["s"], "s", 0), auto_mapping(headers2), CleanOptions()).items
    b = clean_rows(SheetData("r", headers2, right, ["s"], "s", 0), auto_mapping(headers2), CleanOptions()).items
    fuzzy = BomComparator(db, CompareOptions(fuzzy_threshold=0.8)).compare(
        [asdict(i) for i in a], [asdict(i) for i in b]
    )
    print(f"[fuzzy] score={fuzzy.score} stats={fuzzy.stats}")

    db.close()
    print("\nALL CORE TESTS DONE ->", workdir)


if __name__ == "__main__":
    main()
