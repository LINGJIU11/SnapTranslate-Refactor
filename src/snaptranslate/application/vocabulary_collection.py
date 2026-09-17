"""用例：生词本收录与删除（原 ``main.py:936-947``、``1050-1067``、``1473-1503``）。

行为要点：
- 每次操作都**重新从磁盘读**词表（原版如此），避免与复习端/Web 端互相覆盖；
- 收录前按 ``word`` 字段精确判重；
- "收录最近一条翻译"与"收录某条历史"走同一个落盘逻辑。
"""

from __future__ import annotations

from typing import Callable

from snaptranslate.application.dto import CollectKind, CollectOutcome, DeleteKind, DeleteOutcome
from snaptranslate.domain.models.vocab_entry import Vocabulary
from snaptranslate.domain.ports.vocabulary_repository import VocabularyRepository
from snaptranslate.domain.services.text_cleaning import clean_text

#: 原版界面展示的"最近加入生词本"条数
RECENT_SAVED_LIMIT = 5


class VocabularyCollectionUseCase:
    def __init__(self, repository: VocabularyRepository) -> None:
        self._repository = repository

    # —— 收录 ——
    def collect(self, word: str, meaning: str) -> CollectOutcome:
        """收录一条词（``word``/``meaning`` 由调用方清洗后传入，与原版一致）。"""
        if not word or not meaning:
            return CollectOutcome(CollectKind.EMPTY)
        vocabulary = Vocabulary(self._repository.load_raw())
        if vocabulary.find(word) is not None:
            return CollectOutcome(CollectKind.DUPLICATE, word)
        vocabulary.add(word, meaning)
        try:
            self._repository.save(vocabulary.raw)
        except Exception:
            return CollectOutcome(CollectKind.FAILED, word)
        return CollectOutcome(CollectKind.ADDED, word)

    def recent_saved_words(self, limit: int = RECENT_SAVED_LIMIT) -> list[str]:
        """原 ``_load_recent_saved_words``。"""
        return Vocabulary(self._repository.load_raw()).recent_words(limit)

    # —— 删除 ——
    def delete_recent(self, index: int, limit: int = RECENT_SAVED_LIMIT) -> DeleteOutcome:
        vocabulary = Vocabulary(self._repository.load_raw())
        words = vocabulary.recent_words(limit)
        if index < 0 or index >= len(words):
            return DeleteOutcome(DeleteKind.EMPTY)
        target = words[index]
        if vocabulary.remove_word(target) == 0:
            return DeleteOutcome(DeleteKind.NOT_FOUND, target)
        try:
            self._repository.save(vocabulary.raw)
        except Exception:
            return DeleteOutcome(DeleteKind.FAILED, target)
        return DeleteOutcome(DeleteKind.DELETED, target)


class RecallLastTranslationUseCase:
    """把"最近一条翻译"收录进生词本（原 ``_do_save_last_translation_job``）。"""

    def __init__(
        self,
        collection: VocabularyCollectionUseCase,
        last_translation_provider: Callable[[], tuple[str, str]],
    ) -> None:
        self._collection = collection
        self._last_translation_provider = last_translation_provider

    def execute(self) -> CollectOutcome:
        word, meaning = self._last_translation_provider()
        word = clean_text(word or "")
        meaning = clean_text(meaning or "")
        if not word or not meaning:
            return CollectOutcome(CollectKind.NO_LAST)
        return self._collection.collect(word, meaning)
