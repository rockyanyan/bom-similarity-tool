"""文本清洗、归一化、数值解析工具。"""
from __future__ import annotations

import difflib
import re
import unicodedata

_SPACE_RE = re.compile(r"\s+")
_ALT_SPLIT_RE = re.compile(r"[/,;|、，；\s]+")
_BRACKET_RE = re.compile(r"[()\[\]{}<>]")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def clean_text(value) -> str:
    """去首尾空格、压缩内部空白、全角转半角、去掉零宽字符。用于展示。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\xa0", " ")
    text = _SPACE_RE.sub(" ", text)
    return text.strip()


def norm_text(value) -> str:
    """用于匹配的归一化：去全部空白、大写、去括号。"""
    text = clean_text(value).upper()
    text = _SPACE_RE.sub("", text)
    text = _BRACKET_RE.sub("", text)
    return text


def norm_code(value) -> str:
    """物料编码归一化。"""
    code = norm_text(value)
    code = code.replace("－", "-").replace("—", "-")
    if code.endswith(".0") and code[:-2].isdigit():
        code = code[:-2]
    return code


def parse_number(value):
    """解析数值，无法解析返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace(",", "").replace("，", "")
    if not text:
        return None
    match = _NUM_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def is_numeric_text(value) -> bool:
    text = clean_text(value).replace(",", "").replace("，", "")
    if not text:
        return True
    try:
        float(text)
        return True
    except ValueError:
        return False


def parse_alt_codes(value) -> list[str]:
    """解析替换物料文本，如 "A/B、C 或 D" → [A, B, C, D]。"""
    text = clean_text(value)
    if not text:
        return []
    text = text.replace("或", "/").replace("替代", "/").replace("等同", "/")
    parts = _ALT_SPLIT_RE.split(text)
    result: list[str] = []
    for part in parts:
        code = clean_text(_BRACKET_RE.sub("", part))
        if not code:
            continue
        if code not in result:
            result.append(code)
    return result


def text_similarity(left, right) -> float:
    """名称/规格的模糊相似度 0~1。"""
    a, b = norm_text(left), norm_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer:
        ratio = max(ratio, 0.85 + 0.15 * len(shorter) / max(1, len(longer)))
    return min(1.0, ratio)


def material_similarity(name_a, spec_a, name_b, spec_b) -> float:
    """物料整体相似度：名称 60% + 规格 40%，规格为空时只看名称。"""
    name_score = text_similarity(name_a, name_b)
    if norm_text(spec_a) and norm_text(spec_b):
        spec_score = text_similarity(spec_a, spec_b)
        return round(name_score * 0.6 + spec_score * 0.4, 4)
    return round(name_score, 4)


def format_qty(value) -> str:
    if value is None:
        return ""
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.6f}".rstrip("0").rstrip(".")
