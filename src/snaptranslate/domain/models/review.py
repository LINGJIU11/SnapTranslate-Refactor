"""复习相关的枚举与结果值对象。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SortMode(str, Enum):
    """复习顺序（原版用裸字符串 ``random`` / ``score_asc`` / ``score_desc``）。"""

    RANDOM = "random"
    SCORE_ASC = "score_asc"
    SCORE_DESC = "score_desc"


class Grade(str, Enum):
    """自评档位。"""

    KNOW = "know"
    VAGUE = "vague"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GradeResult:
    """一次评分的产出（原版 ``_apply_grade`` 直接改 dict 并拼日志文案）。"""

    word: str
    grade: Grade
    revealed: bool
    old_score: float
    new_score: float
    delta: float
    reviews: int
    saved: bool = True
