"""BOM 相似度对比工具 · 程序入口。"""
from __future__ import annotations

import ctypes
import os
import sys
import traceback

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.db import DB
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme


def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _set_dark_titlebar(window):
    if not sys.platform.startswith("win"):
        return
    try:
        hwnd = int(window.winId())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("bom.similarity.tool")
        except Exception:  # noqa: BLE001
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("BOM 相似度对比工具")
    app.setOrganizationName("BOM Tools")
    apply_theme(app)

    icon_path = resource_path("assets/app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    try:
        db = DB()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, "启动失败", f"无法打开数据库：\n{exc}")
        return 1

    try:
        window = MainWindow(db)
    except Exception:  # noqa: BLE001
        QMessageBox.critical(None, "启动失败", traceback.format_exc())
        return 1

    window.show()
    _set_dark_titlebar(window)
    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
