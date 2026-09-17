"""词条与词表集合。

设计要点（见 ARCHITECTURE.md §4.1）：**原始 dict 是唯一事实来源**，
``VocabEntry`` 只是它的强类型视图。这样既能对外提供封装与类型安全，
又保证"读入 → 修改 → 写回"不改变键序、不丢弃未知字段——这是与原版行为等价的前提。
"""

from __future__ import annotations

from typing import Any, Iterator

from snaptranslate.domain.services.scoring import DEFAULT_SCORE, item_score, normalize_scores
from snaptranslate.domain.services.text_cleaning import clean_text

#: 新增词条时的字段顺序（原版 ``main.py:1486-1495``）
NEW_ENTRY_FIELDS: tuple[str, ...] = ("word", "meaning", "example", "example_zh", "score", "reviews")


def _text(value: Any) -> str:
    """原版读文本字段的两种写法（``str(it.get(k, ""))`` 与 ``it.get(k, "") or ""``）等价于此。"""
    return "" if value is None else str(value)


class VocabEntry:
    """词条视图：读写都直接落到原始 dict，不复制。"""

    __slots__ = ("_raw",)

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    @classmethod
    def create(cls, word: str, meaning: str) -> "VocabEntry":
        """按原版字段顺序创建新词条。"""
        return cls(
            {
                "word": word,
                "meaning": meaning,
                "example": "",
                "example_zh": "",
                "score": DEFAULT_SCORE,
                "reviews": 0,
            }
        )

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    def get(self, key: str, default: Any = None) -> Any:
        """读取底层字段（用于访问未知/扩展字段）。"""
        return self._raw.get(key, default)

    # —— 文本字段 ——
    @property
    def word(self) -> str:
        return _text(self._raw.get("word", ""))

    @word.setter
    def word(self, value: str) -> None:
        self._raw["word"] = value

    @property
    def meaning(self) -> str:
        return _text(self._raw.get("meaning", ""))

    @meaning.setter
    def meaning(self, value: str) -> None:
        self._raw["meaning"] = value

    @property
    def example(self) -> str:
        return _text(self._raw.get("example", ""))

    @example.setter
    def example(self, value: str) -> None:
        self._raw["example"] = value

    @property
    def example_zh(self) -> str:
        return _text(self._raw.get("example_zh", ""))

    @example_zh.setter
    def example_zh(self, value: str) -> None:
        self._raw["example_zh"] = value

    # —— 学习状态 ——
    @property
    def score(self) -> float:
        return item_score(self._raw)

    @score.setter
    def score(self, value: float) -> None:
        self._raw["score"] = value

    @property
    def reviews(self) -> int:
        return int(self._raw.get("reviews") or 0)

    @reviews.setter
    def reviews(self, value: int) -> None:
        self._raw["reviews"] = value

    @property
    def needs_bilingual_example(self) -> bool:
        """英文例句与中文译文任一为空即视为待补全（原版 ``needs_bilingual_example``）。"""
        return (not self.example.strip()) or (not self.example_zh.strip())


class Vocabulary:
    """词表集合：封装增删查与统计，内部保持原始 dict 列表。"""

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._items: list[dict[str, Any]] = items if items is not None else []

    # —— 容器协议 ——
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[VocabEntry]:
        return iter(self.entries())

    def __bool__(self) -> bool:
        return bool(self._items)

    @property
    def raw(self) -> list[dict[str, Any]]:
        """底层 dict 列表（交给仓储层序列化用）。"""
        return self._items

    def entries(self) -> list[VocabEntry]:
        """仅包装 dict 元素（原版 main.py 允许列表里混入非 dict，这里跳过）。"""
        return [VocabEntry(item) for item in self._items if isinstance(item, dict)]

    # —— 查询 ——
    def get(self, index: int) -> VocabEntry | None:
        if index < 0 or index >= len(self._items):
            return None
        item = self._items[index]
        if not isinstance(item, dict):
            return None
        return VocabEntry(item)

    def find(self, word: str) -> VocabEntry | None:
        """按 ``word`` 字段精确匹配（原版 ``it.get("word") == word``）。"""
        for item in self._items:
            if isinstance(item, dict) and item.get("word") == word:
                return VocabEntry(item)
        return None

    def words(self) -> list[str]:
        return [entry.word for entry in self.entries()]

    def recent_words(self, limit: int = 5) -> list[str]:
        """原版 ``_load_recent_saved_words``：清洗 → 去重（保序）→ 反转 → 取前 N。"""
        words: list[str] = []
        for entry in self.entries():
            word = clean_text(entry.word)
            if word:
                words.append(word)
        deduped = list(dict.fromkeys(words))
        deduped.reverse()
        return deduped[:limit]

    # —— 变更 ——
    def add(self, word: str, meaning: str) -> VocabEntry:
        entry = VocabEntry.create(word, meaning)
        self._items.append(entry.raw)
        return entry

    def remove_word(self, word: str) -> int:
        """删除所有匹配词条，返回删除条数。

        注意：原版 ``_delete_saved_word`` 的过滤条件会**保留非 dict 元素**，这里保持一致。
        """
        kept: list[dict[str, Any]] = []
        removed = 0
        for item in self._items:
            matched = isinstance(item, dict) and clean_text(_text(item.get("word", ""))) == word
            if matched:
                removed += 1
            else:
                kept.append(item)
        if removed:
            self._items = kept
        return removed

    def normalize_scores(self) -> None:
        normalize_scores(self._items)

    # —— 统计 ——
    def pending_example_count(self) -> int:
        return sum(1 for entry in self.entries() if entry.needs_bilingual_example)

    def with_example_count(self) -> int:
        """英例句与中译都齐全的条数（原版 ``set.py:count_with_example``）。"""
        count = 0
        for entry in self.entries():
            if entry.example.strip() and entry.example_zh.strip():
                count += 1
        return count
