"""生成程序图标与演示数据（开发辅助脚本，不参与打包）。"""
from __future__ import annotations

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def make_icon():
    app = QApplication.instance() or QApplication([])
    size = 256
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)

    path = QPainterPath()
    path.addRoundedRect(QRectF(8, 8, size - 16, size - 16), 52, 52)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#4F8DFD"))
    gradient.setColorAt(1, QColor("#2B4FA8"))
    painter.fillPath(path, gradient)

    painter.setPen(QColor(255, 255, 255, 46))
    painter.setBrush(Qt.NoBrush)
    for offset in (0, 26):
        painter.drawRoundedRect(QRectF(40 + offset, 46 + offset, 176 - offset * 2, 164 - offset * 2), 28, 28)

    font = QFont("Segoe UI", 60, QFont.Black)
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(image.rect(), Qt.AlignCenter, "BOM")
    painter.end()

    assets = os.path.join(ROOT, "assets")
    os.makedirs(assets, exist_ok=True)
    png_path = os.path.join(assets, "app.png")
    image.save(png_path, "PNG")

    # 单张 PNG 封装的 ICO
    with open(png_path, "rb") as handle:
        png = handle.read()
    ico_path = os.path.join(assets, "app.ico")
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    with open(ico_path, "wb") as handle:
        handle.write(header + entry + png)
    print("icon ->", ico_path)


def make_samples():
    from openpyxl import Workbook

    headers = ["层级", "下级BOM", "下级编码", "名称", "规格", "单位", "标准用量",
               "损耗率", "替换物料", "获取途径", "发料中心"]

    v10 = [
        [1, "1", "MCU-STM32F103C8T6", "主控 MCU", "STM32F103C8T6 LQFP48", "PCS", 1, 0.005, "", "自制", "SMT-1"],
        [1, "1", "IC-AMS1117-3.3", "LDO 稳压器", "AMS1117-3.3 SOT-223", "PCS", 2, 0.003, "IC-AMS1117-3.3/IC-SPX3819-3.3", "外购", "SMT-1"],
        [1, "1", "R-0603-10K", "贴片电阻", "0603 10K 1% 1/10W", "PCS", 4, 0.01, "", "外购", "SMT-1"],
        [1, "1", "R-0603-1K", "贴片电阻", "0603 1K 1% 1/10W", "PCS", 6, 0.01, "", "外购", "SMT-1"],
        [1, "1", "C-0805-100N", "贴片电容", "0805 100nF 50V X7R", "PCS", 8, 0.02, "C-0805-100N/C-0805-100N-B", "外购", "SMT-1"],
        [1, "1", "C-0805-10U", "贴片电容", "0805 10uF 25V X5R", "PCS", 4, 0.02, "", "外购", "SMT-1"],
        [1, "1", "D-SS34", "肖特基二极管", "SS34 SMA 40V 3A", "PCS", 2, 0.01, "D-SS34/D-SS54", "外购", "SMT-1"],
        [1, "1", "L-4R7", "功率电感", "4.7uH 3A 屏蔽", "PCS", 1, 0.02, "", "外购", "SMT-1"],
        [1, "1", "LED-0805-GRN", "贴片 LED", "0805 绿色 20mA", "PCS", 1, 0.01, "", "外购", "SMT-2"],
        [1, "1", "CN-USB-MICRO", "USB 座", "Micro USB 5P 贴板", "PCS", 1, 0.01, "CN-USB-MICRO/CN-USB-C-5P", "外购", "插件-1"],
        [1, "1", "CN-2P-2.54", "排针", "2.54mm 2P 直插", "PCS", 2, 0.01, "", "外购", "插件-1"],
        [1, "1", "F-1A-1206", "贴片保险丝", "1206 1A 快断", "PCS", 1, 0.01, "", "外购", "SMT-1"],
        [1, "1", "SW-RESET", "轻触开关", "3x4x2mm 贴片", "PCS", 1, 0.01, "", "外购", "SMT-2"],
        [1, "1", "PCB-A03", "PCB 裸板", "A03 电源板 4 层 1.6mm", "PCS", 1, 0.03, "", "外协", "仓库-A"],
        [1, "1", "SCR-M3-8", "十字盘头螺丝", "M3x8 镀镍", "PCS", 4, 0.02, "", "外购", "五金仓"],
        [1, "1", "NUT-M3", "六角螺母", "M3 镀镍", "PCS", 4, 0.02, "", "外购", "五金仓"],
        [1, "1", "HS-AL-20", "铝散热片", "20x20x10mm", "PCS", 1, 0.01, "", "外购", "五金仓"],
        [1, "1", "LBL-A03", "标签贴纸", "A03 铭牌 30x15", "PCS", 1, 0.01, "", "外购", "仓库-A"],
    ]

    v11 = [list(row) for row in v10]
    # 数量变更
    for row in v11:
        if row[2] == "R-0603-10K":
            row[6] = 6
        if row[2] == "C-0805-10U":
            row[6] = 6
    # 等价替换
    for row in v11:
        if row[2] == "C-0805-100N":
            row[2] = "C-0805-100N-B"
            row[4] = "0805 100nF 50V X7R 高压"
        if row[2] == "IC-AMS1117-3.3":
            row[2] = "IC-SPX3819-3.3"
            row[3] = "LDO 稳压器"
            row[4] = "SPX3819-3.3 SOT-23-5"
    # 缺失
    v11 = [row for row in v11 if row[2] != "D-SS34"]
    # 获取途径变更
    for row in v11:
        if row[2] == "MCU-STM32F103C8T6":
            row[9] = "外购"
    # 新增
    v11.append([1, "1", "LED-0805-RED", "贴片 LED", "0805 红色 20mA", "PCS", 2, 0.01, "", "外购", "SMT-2"])
    v11.append([1, "1", "TVS-SMAJ5.0A", "TVS 二极管", "SMAJ5.0A SMA", "PCS", 2, 0.01, "", "外购", "SMT-1"])
    v11.append([1, "1", "MCU-ESP32-S3", "主控 MCU 模组", "ESP32-S3-WROOM-1-N8R2", "PCS", 1, 0.005, "MCU-ESP32-S3/MCU-ESP32-S3-N16", "外购", "SMT-1"])

    out_dir = os.path.join(ROOT, "示例数据")
    os.makedirs(out_dir, exist_ok=True)
    for filename, rows, sheet in (
        ("A03电源板_V1.0.xlsx", v10, "A03-V1.0"),
        ("A03电源板_V1.1.xlsx", v11, "A03-V1.1"),
    ):
        wb = Workbook()
        ws = wb.active
        ws.title = sheet
        ws.append(["A03 电源板 BOM 明细表"])
        ws.append(["文件说明：用于 BOM 相似度对比演示"])
        ws.append(headers)
        for row in rows:
            ws.append(row)
        ws.append([])
        ws.append(["合计", "", "", "", "", "", sum(r[6] for r in rows)])
        wb.save(os.path.join(out_dir, filename))
        print("sample ->", filename)

    # CSV 演示（另一块板，用于全库批量检索）
    import csv

    b07 = [
        ["1", "1", "MCU-ESP32-S3", "主控 MCU", "ESP32-S3-WROOM-1", "PCS", "1", "0.005", "", "外购", "SMT-1"],
        ["1", "1", "IC-AMS1117-3.3", "LDO 稳压器", "AMS1117-3.3 SOT-223", "PCS", "2", "0.003", "IC-AMS1117-3.3/IC-SPX3819-3.3", "外购", "SMT-1"],
        ["1", "1", "R-0603-10K", "贴片电阻", "0603 10K 1% 1/10W", "PCS", "10", "0.01", "", "外购", "SMT-1"],
        ["1", "1", "C-0805-100N", "贴片电容", "0805 100nF 50V X7R", "PCS", "12", "0.02", "C-0805-100N/C-0805-100N-B", "外购", "SMT-1"],
        ["1", "1", "CN-USB-C-16P", "USB 座", "Type-C 16P 贴板", "PCS", "1", "0.01", "CN-USB-MICRO/CN-USB-C-5P", "外购", "插件-1"],
        ["1", "1", "LED-0805-GRN", "贴片 LED", "0805 绿色 20mA", "PCS", "2", "0.01", "", "外购", "SMT-2"],
        ["1", "1", "PCB-B07", "PCB 裸板", "B07 控制板 4 层 1.6mm", "PCS", "1", "0.03", "", "外协", "仓库-A"],
        ["1", "1", "SCR-M3-8", "十字盘头螺丝", "M3x8 镀镍", "PCS", "6", "0.02", "", "外购", "五金仓"],
        ["1", "1", "SW-USER", "轻触开关", "4x4x1.5mm 贴片", "PCS", "3", "0.01", "", "外购", "SMT-2"],
    ]
    csv_path = os.path.join(out_dir, "B07控制板_BOM.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(b07)
    print("sample ->", os.path.basename(csv_path))


if __name__ == "__main__":
    make_icon()
    make_samples()
