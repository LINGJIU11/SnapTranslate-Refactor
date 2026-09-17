"""进度回调：应用层只发出**阶段枚举**，具体文案与显示时长由表示层决定。

原版把中文状态文案直接写在业务逻辑里（``main.py:971 987 995 1046 1074 1078 1120-1124 1140-1141 1169-1170``），
并且同一个阶段在"状态栏"和"光标提示条"上是两句不同的话——这正是需要分层的地方。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Stage(str, Enum):
    """翻译/OCR 流程中会出现的中间状态。"""

    READING_SELECTION = "reading_selection"
    #: 模拟 Ctrl+C 未生效（剪贴板没有变化）——原版没有这个状态，因为原版把失败当成了成功
    CAPTURE_FAILED = "capture_failed"
    TRANSLATING = "translating"
    DONE = "done"
    FAILED = "failed"
    NO_TEXT = "no_text"
    OCR_PREPARING = "ocr_preparing"
    OCR_CAPTURING = "ocr_capturing"
    OCR_RECOGNIZING = "ocr_recognizing"
    OCR_TRANSLATING = "ocr_translating"
    OCR_UNAVAILABLE = "ocr_unavailable"
    OCR_BUSY = "ocr_busy"
    OCR_FAILED = "ocr_failed"


def _noop(_stage: Stage) -> None:
    return None


@dataclass
class ProgressReporter:
    """状态栏 / 光标提示条两个出口。

    表示层实现这两个回调时负责切回 UI 线程（Tk 用 ``root.after(0, ...)``）。
    """

    on_status: Callable[[Stage], None] = field(default=_noop)
    on_cursor: Callable[[Stage], None] = field(default=_noop)

    def status(self, stage: Stage) -> None:
        self.on_status(stage)

    def cursor(self, stage: Stage) -> None:
        self.on_cursor(stage)
