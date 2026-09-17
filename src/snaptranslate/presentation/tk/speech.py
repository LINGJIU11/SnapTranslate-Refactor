"""复习卡片的「自动朗读」调度（原 ``vocab_review.py:661-692`` 的 ``_maybe_speak_for_card``）。

原版用一个递增的"代次计数" ``_speak_generation`` 做防抖：切到新卡片时计数 +1，
后台线程在自己真正开口前比对代次，发现自己已是"上一张卡"的遗留任务就直接返回。
这里把这套计数与线程启动收在一个小组件里，朗读本身仍然是 ``deps.review`` 的用例。
"""

from __future__ import annotations

import threading
from typing import Callable

from snaptranslate.domain.models.vocab_entry import VocabEntry

#: 朗读执行体：``(词条, 模式, 音量) -> None``（生产实现即 ``ReviewUseCase.speak_for_card``）
SpeakForCard = Callable[[VocabEntry | None, str, int], None]
#: 例句朗读执行体：``(词条, 音量) -> None``（生产实现即 ``ReviewUseCase.speak_example``）
SpeakExample = Callable[[VocabEntry | None, int], None]


class SpeakScheduler:
    """按原版代次语义在后台线程里朗读当前卡片。"""

    def __init__(self, speak_for_card: SpeakForCard, speak_example: SpeakExample | None = None) -> None:
        self._speak_for_card = speak_for_card
        self._speak_example = speak_example
        self._generation = 0

    def speak_for_card(self, entry: VocabEntry | None, mode: str, volume: int) -> None:
        """原 ``_maybe_speak_for_card``：``none`` 模式直接返回，且**不**占用代次。"""
        if entry is None or mode == "none":
            return
        self._generation += 1
        generation = self._generation

        def worker() -> None:
            # 行为等价：只比对代次，不取消已经开始的朗读（原版同样只做"跳过"）
            if generation != self._generation:
                return
            self._speak_for_card(entry, mode, volume)

        threading.Thread(target=worker, daemon=True).start()

    def speak_example(self, entry: VocabEntry | None, volume: int) -> None:
        """原 ``_toggle_example`` 展开例句时的朗读：另起线程、**不**占用代次。

        生成实现是 ``ReviewUseCase.speak_example``（例文空则自身返回），
        由构造方通过 ``speak_example`` 参数注入。
        """
        if entry is None or self._speak_example is None:
            return
        threading.Thread(target=self._speak_example, args=(entry, volume), daemon=True).start()


__all__ = ["SpeakExample", "SpeakForCard", "SpeakScheduler"]
