"""进程内翻译结果缓存。

对应原版 ``main.py:57-76`` 的 ``_TRANS_OK_CACHE``：``OrderedDict`` + LRU 淘汰 +
**只缓存确有译文的结果**（避免把 "(无翻译结果)" 钉死）。无 TTL、不落盘——原样保留。
"""

from __future__ import annotations

from collections import OrderedDict

from snaptranslate.domain.models.translation import NO_TRANSLATION_RESULT
from snaptranslate.infrastructure.translation.policy import CACHE_MAX_SIZE


class TranslationCache:
    """线程安全性沿用原版：直接操作 OrderedDict（CPython 下 dict 操作是原子的）。"""

    def __init__(self, max_size: int = CACHE_MAX_SIZE) -> None:
        self._store: "OrderedDict[tuple[str, str, str], str]" = OrderedDict()
        self.max_size = max_size

    def get(self, engine: str, text: str, variant: str = "") -> str | None:
        """取缓存。

        :param variant: 方向标签（新增功能用，见
            :class:`~snaptranslate.domain.models.translation.Direction`）。
            默认空串 → 键与原来完全一致，原版那一路（自动 → 中文）的缓存语义不变。
        """
        key = (engine, variant, text)
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, engine: str, text: str, result: str, variant: str = "") -> None:
        if not result or result == NO_TRANSLATION_RESULT:
            return
        key = (engine, variant, text)
        self._store[key] = result
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
