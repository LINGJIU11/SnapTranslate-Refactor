"""评分规则（原版三处重复实现：``vocab_review.py:45-73``、``vocab_review_web.py:21-49``、``set.py:9``）。

本模块只处理**原始 dict**，不 import 模型层，避免 domain 内部循环依赖。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

DEFAULT_SCORE = 50.0
SCORE_MIN = 0.0
SCORE_MAX = 100.0

#: (档位, 是否已在当前张上点过「显示释义/例句」) → 分数变化（原版逐字一致）
GRADE_DELTA: dict[tuple[str, bool], float] = {
    ("know", False): 10.0,
    ("vague", False): -4.0,
    ("unknown", False): -8.0,
    ("know", True): 5.0,
    ("vague", True): -7.0,
    ("unknown", True): -12.0,
}


def _grade_key(grade: object) -> str:
    """``Grade`` 是 ``str`` 枚举，但 Enum 的 ``__hash__`` 与字符串不同，需显式取值。"""
    value = getattr(grade, "value", grade)
    return str(value)


def item_score(item: Mapping[str, Any]) -> float:
    """取词条熟练度并夹到 [0, 100]（原版 ``item_score``）。"""
    raw = item.get("score")
    if raw is None:
        value = DEFAULT_SCORE
    else:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = DEFAULT_SCORE
    return max(SCORE_MIN, min(SCORE_MAX, value))


def normalize_scores(items: Iterable[dict[str, Any]]) -> None:
    """就地归一化整表评分（原版 ``normalize_vocab_scores``）。"""
    for item in items:
        item["score"] = item_score(item)


def apply_grade(item: dict[str, Any], grade: object, revealed: bool) -> tuple[float, float, float, int] | None:
    """按自评档位就地更新 ``score`` / ``reviews``。

    返回 ``(old, new, delta, reviews)``；档位非法（``GRADE_DELTA`` 里没有）时返回 ``None``，
    对应原版 ``_apply_grade`` 的提前 return。
    """
    delta = GRADE_DELTA.get((_grade_key(grade), bool(revealed)))
    if delta is None:
        return None
    old = item_score(item)
    new = max(SCORE_MIN, min(SCORE_MAX, old + delta))
    item["score"] = round(new, 1)
    reviews = int(item.get("reviews") or 0) + 1
    item["reviews"] = reviews
    return old, round(new, 1), delta, reviews
