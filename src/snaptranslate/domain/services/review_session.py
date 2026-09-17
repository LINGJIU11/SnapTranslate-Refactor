"""复习会话状态机。

原版把"顺序构建 / 当前位置 / 推进 / 揭示状态"这套逻辑在桌面端
（``vocab_review.py:614-633``、``718-732``）与 Web 端（``vocab_review_web.py:164-232``）
各写了一份；重构后两端共用本实现，表示层只负责渲染与事件转发。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from snaptranslate.domain.models.review import SortMode
from snaptranslate.domain.models.vocab_entry import Vocabulary, VocabEntry
from snaptranslate.domain.services.scoring import item_score


@dataclass
class RevealTransition:
    """``toggle_example`` 的状态迁移结果（Web 端需要据此决定是否朗读例句）。"""

    was_showing: bool
    now_showing: bool


class RevealState:
    """卡片揭示状态：释义 / 例句 / 例句翻译。"""

    def __init__(self) -> None:
        self.show_meaning = False
        self.show_example = False
        self.show_example_zh = False

    @property
    def any_revealed(self) -> bool:
        """原版评分时用 ``show_meaning or show_example or show_example_zh`` 判断加减分幅度。"""
        return bool(self.show_meaning or self.show_example or self.show_example_zh)

    def reset(self) -> None:
        self.show_meaning = False
        self.show_example = False
        self.show_example_zh = False

    def toggle_meaning(self) -> bool:
        self.show_meaning = not self.show_meaning
        return self.show_meaning

    def toggle_example(self) -> RevealTransition:
        was_showing = self.show_example
        self.show_example = not self.show_example
        if not self.show_example:
            # 原版：关闭例句时连带关闭例句翻译
            self.show_example_zh = False
        return RevealTransition(was_showing=was_showing, now_showing=self.show_example)

    def toggle_example_zh(self) -> bool:
        """仅在例句已显示时才允许切换（原版提前 return 的语义）。"""
        if not self.show_example:
            return self.show_example_zh
        self.show_example_zh = not self.show_example_zh
        return self.show_example_zh


class ReviewSession:
    """一次复习会话：持有词表、顺序、当前位置与揭示状态。"""

    def __init__(
        self,
        vocabulary: Vocabulary,
        mode: SortMode | str = SortMode.RANDOM,
        rng: random.Random | None = None,
    ) -> None:
        self.vocabulary = vocabulary
        self.mode = SortMode(mode)
        self._rng = rng
        self.order: list[int] = []
        self.position = 0
        self.reveal = RevealState()
        self.rebuild_order()

    # —— 顺序 ——
    def set_mode(self, mode: SortMode | str) -> None:
        self.mode = SortMode(mode)
        self.rebuild_order()
        self.position = 0

    def rebuild_order(self) -> None:
        """按模式重建顺序（原版 ``_rebuild_order``：random 用全局 RNG，评分模式带索引兜底排序）。"""
        size = len(self.vocabulary)
        self.order = list(range(size))
        if size <= 1:
            return
        if self.mode is SortMode.RANDOM:
            if self._rng is None:
                random.shuffle(self.order)
            else:
                self._rng.shuffle(self.order)
        elif self.mode is SortMode.SCORE_ASC:
            raw = self.vocabulary.raw
            self.order.sort(key=lambda i: (item_score(raw[i]), i))
        elif self.mode is SortMode.SCORE_DESC:
            raw = self.vocabulary.raw
            self.order.sort(key=lambda i: (-item_score(raw[i]), i))

    # —— 当前卡片 ——
    def current(self) -> VocabEntry | None:
        if not self.order or self.position < 0 or self.position >= len(self.order):
            return None
        return self.vocabulary.get(self.order[self.position])

    def reset_reveal(self) -> None:
        self.reveal.reset()

    def current_index(self) -> int | None:
        """当前卡片在词表中的下标（Web 端用于生成"自动朗读 token"）。"""
        if not self.order or self.position < 0 or self.position >= len(self.order):
            return None
        return self.order[self.position]

    # —— 推进 ——
    def advance_after_grade(self) -> None:
        """评分后重排顺序并前进一格（原版 ``_advance_after_grade`` 逐行等价）。"""
        if not self.order:
            return
        size = len(self.order)
        current_index = self.order[self.position]
        self.rebuild_order()
        try:
            new_position = self.order.index(current_index)
        except ValueError:
            new_position = 0
        self.position = (new_position + 1) % size
        self.reset_reveal()
