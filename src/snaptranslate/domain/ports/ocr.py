"""OCR 端口。

封装"截屏 + 识别"两件事：应用层只给出屏幕矩形，拿回文字；
具体用什么引擎（Tesseract / 未来的 RapidOCR）由基础设施层决定。
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Protocol, runtime_checkable

from snaptranslate.domain.models.geometry import BBox


class OcrStage(str, Enum):
    """OCR 阶段（原版用两条不同的状态文案分别更新状态栏与光标提示）。"""

    CAPTURING = "capturing"
    RECOGNIZING = "recognizing"


#: 阶段回调：实现方在截屏/识别前各触发一次，表示层据此显示"截图中…/识别中…"
StageCallback = Callable[[OcrStage], None]


@runtime_checkable
class OcrEngine(Protocol):
    """屏幕区域文字识别能力。"""

    @property
    def is_available(self) -> bool:
        """依赖是否齐备（原版检查 ``pillow`` / ``pytesseract`` / Tesseract 可执行文件）。"""
        ...

    def extract_text(self, bbox: BBox, on_stage: StageCallback | None = None) -> str:
        """识别指定屏幕区域内的文字，失败抛 :class:`~snaptranslate.domain.errors.OcrError`。"""
        ...
