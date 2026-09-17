"""文本清洗与判定（原版 ``main.py:411-416``、``1013-1016``、``976-977``）。"""

from __future__ import annotations

import re

#: 原版 ``main.py:44`` ``MAX_TEXT_LENGTH = 120``
DEFAULT_MAX_TEXT_LENGTH = 120
TRUNCATION_SUFFIX = "..."

_LETTER_RE = re.compile(r"[A-Za-z]")


def clean_text(raw: str) -> str:
    """去首尾空白、把 CR/LF 折成空格、合并连续空格。

    与原版实现逐字等价（原版用 ``while "  " in text`` 循环折叠，这里保留同一算法以保证
    输出完全一致，虽然正则也能得到同样结果）。
    """
    text = str(raw).strip().replace("\r", " ").replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def is_likely_english(text: str) -> bool:
    """原版 ``_is_likely_english``：含 2 个及以上拉丁字母就当作英文（触发自动朗读）。"""
    return len(_LETTER_RE.findall(text or "")) >= 2


def letter_count(text: str) -> int:
    return len(_LETTER_RE.findall(text or ""))


def truncate(text: str, max_length: int = DEFAULT_MAX_TEXT_LENGTH, suffix: str = TRUNCATION_SUFFIX) -> str:
    """超长截断（原版 ``main.py:976-977``：超限才加后缀，未超限原样返回）。"""
    if len(text) > max_length:
        return text[:max_length] + suffix
    return text
