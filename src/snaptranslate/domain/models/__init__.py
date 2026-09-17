"""领域模型与值对象。"""

from __future__ import annotations

from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.models.hotkey import DEFAULT_HOTKEYS, Hotkey
from snaptranslate.domain.models.review import Grade, GradeResult, SortMode
from snaptranslate.domain.models.translation import NO_TRANSLATION_RESULT, TranslationResult
from snaptranslate.domain.models.vocab_entry import Vocabulary, VocabEntry

__all__ = [
    "BBox",
    "DEFAULT_HOTKEYS",
    "Grade",
    "GradeResult",
    "Hotkey",
    "NO_TRANSLATION_RESULT",
    "SortMode",
    "TranslationResult",
    "VocabEntry",
    "Vocabulary",
]
