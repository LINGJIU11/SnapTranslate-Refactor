"""领域模型与值对象。"""

from __future__ import annotations

from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.models.hotkey import (
    ALL_HOTKEY_KEYS,
    DEFAULT_HOTKEYS,
    DEFAULT_INPUT_HOTKEY,
    INPUT_HOTKEY_KEY,
    Hotkey,
    feature_hotkeys,
)
from snaptranslate.domain.models.review import Grade, GradeResult, SortMode
from snaptranslate.domain.models.selection import SelectionCapture
from snaptranslate.domain.models.translation import (
    AUTO_TO_CHINESE,
    CHINESE_TO_ENGLISH,
    NO_TRANSLATION_RESULT,
    Direction,
    TranslationResult,
)
from snaptranslate.domain.models.vocab_entry import Vocabulary, VocabEntry

__all__ = [
    "ALL_HOTKEY_KEYS",
    "AUTO_TO_CHINESE",
    "BBox",
    "CHINESE_TO_ENGLISH",
    "DEFAULT_HOTKEYS",
    "DEFAULT_INPUT_HOTKEY",
    "Direction",
    "Grade",
    "GradeResult",
    "Hotkey",
    "INPUT_HOTKEY_KEY",
    "NO_TRANSLATION_RESULT",
    "SelectionCapture",
    "SortMode",
    "TranslationResult",
    "VocabEntry",
    "Vocabulary",
    "feature_hotkeys",
]
