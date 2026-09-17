"""用例：批量生成英例句 + 中译（原 ``vocab_review.py:937-1004``、``vocab_review_web.py:288-319``）。

桌面端与 Web 端循环策略不同，这里用参数表达，不做行为合并：

============  ============  =========  ======================
界面           save_each     延时        终止条件
============  ============  =========  ======================
桌面端         每条后落盘     0.35s      窗口被关闭 / 余额不足
Web 端         结束时落盘一次  0.2s        余额不足
============  ============  =========  ======================
"""

from __future__ import annotations

from typing import Callable

from snaptranslate.application.dto import ExampleItemResult, GenerateOutcome, StopKind
from snaptranslate.application.vocabulary_target import VocabularyTarget
from snaptranslate.domain.errors import InsufficientBalanceError
from snaptranslate.domain.models.vocab_entry import Vocabulary, VocabEntry
from snaptranslate.domain.ports.clock import Clock
from snaptranslate.domain.ports.example_generator import ExampleGenerator

#: 原版两端的循环间隔
DESKTOP_DELAY_SEC = 0.35
WEB_DELAY_SEC = 0.2

OnItemStart = Callable[[int, int, str], None]
OnItemDone = Callable[[ExampleItemResult], None]
ShouldStop = Callable[[], bool]


class GenerateExamplesUseCase:
    def __init__(self, target: VocabularyTarget, clock: Clock) -> None:
        self._target = target
        self._clock = clock

    # —— 准备阶段 ——
    def pending_items(self, vocabulary: Vocabulary) -> list[VocabEntry]:
        """待补全的条目（英文例句或中译任一为空）。"""
        return [entry for entry in vocabulary if entry.needs_bilingual_example]

    def pending_count(self, vocabulary: Vocabulary) -> int:
        return vocabulary.pending_example_count()

    # —— 执行阶段 ——
    def execute(
        self,
        generator: ExampleGenerator,
        vocabulary: Vocabulary,
        pending: list[VocabEntry],
        *,
        on_item_start: OnItemStart | None = None,
        on_item_done: OnItemDone | None = None,
        should_stop: ShouldStop | None = None,
        save_each: bool = True,
        delay: float = DESKTOP_DELAY_SEC,
    ) -> GenerateOutcome:
        total = len(pending)
        ok = 0
        stop_kind = StopKind.COMPLETED
        for order, entry in enumerate(pending, start=1):
            if should_stop is not None and should_stop():
                stop_kind = StopKind.WINDOW_CLOSED
                break
            word = entry.word
            meaning = entry.meaning
            if on_item_start is not None:
                on_item_start(order, total, word)
            try:
                example, example_zh = generator.generate(word, meaning)
                entry.example = example
                entry.example_zh = example_zh
                if save_each:
                    self._target.repository.save(vocabulary.raw)
                ok += 1
                if on_item_done is not None:
                    on_item_done(ExampleItemResult(order, total, word, True))
            except InsufficientBalanceError:
                stop_kind = StopKind.INSUFFICIENT_BALANCE
                break
            except Exception as exc:  # noqa: BLE001 - 与原版一致：单条失败不打断整体
                if on_item_done is not None:
                    on_item_done(ExampleItemResult(order, total, word, False, str(exc)))
            self._clock.sleep(delay)
        if not save_each:
            self._target.repository.save(vocabulary.raw)
        return GenerateOutcome(ok=ok, total=total, stop_kind=stop_kind)
