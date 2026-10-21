"""离屏渲染界面截图，用于开发自检。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import asdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.db import DB  # noqa: E402
from app.core.importer import CleanOptions, auto_mapping, clean_rows, collect_alt_pairs, read_file  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.theme import apply_theme  # noqa: E402

SAMPLES = os.path.join(ROOT, "示例数据")
OUT = os.path.join(ROOT, ".snapshots")


def import_scheme(db, filename, name, version):
    sheet = read_file(os.path.join(SAMPLES, filename))
    result = clean_rows(sheet, auto_mapping(sheet.headers), CleanOptions())
    scheme_id = db.create_scheme(name, version, "", filename, 0, result.items)
    return scheme_id, result


def main():
    workdir = tempfile.mkdtemp(prefix="bomsnap_")
    db_path = os.path.join(workdir, "snap.db")
    db = DB(db_path)

    id_a, r10 = import_scheme(db, "A03电源板_V1.0.xlsx", "A03 电源板", "V1.0")
    id_b, r11 = import_scheme(db, "A03电源板_V1.1.xlsx", "A03 电源板", "V1.1")
    import_scheme(db, "B07控制板_BOM.csv", "B07 控制板", "V1.0")
    db.apply_alt_pairs(collect_alt_pairs(r10.items))

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow(db)
    window.resize(1460, 920)
    window.show()
    app.processEvents()

    os.makedirs(OUT, exist_ok=True)

    def shot(name):
        app.processEvents()
        path = os.path.join(OUT, f"{name}.png")
        window.grab().save(path)
        print("shot ->", path)

    window.goto("library")
    shot("01_library")

    window.goto("import")
    window.import_page.load_file(os.path.join(SAMPLES, "A03电源板_V1.1.xlsx"))
    app.processEvents()
    shot("02_import")

    window.goto("compare")
    window.compare_page.select_scheme(id_a)
    pos = window.compare_page.b_combo.findData(id_b)
    if pos >= 0:
        window.compare_page.b_combo.setCurrentIndex(pos)
    window.compare_page.chk_supply.setChecked(True)
    window.compare_page.run_compare()
    shot("03_compare")

    window.compare_page.run_batch()
    shot("04_batch")

    window.compare_page.export_report  # noqa: B018
    window.goto("alt")
    shot("05_alt")

    window.goto("settings")
    shot("06_settings")

    db.close()
    print("done")


if __name__ == "__main__":
    main()
