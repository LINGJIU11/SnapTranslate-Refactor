"""翻译端口。

一个 ``Translator`` 代表**一条翻译线路或一种策略**（竞速、单接口、未来的 LLM 通道等），
应用层只知道"给它文本、拿回 :class:`TranslationResult`"。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from snaptranslate.domain.models.translation import AUTO_TO_CHINESE, Direction, TranslationResult


@runtime_checkable
class Translator(Protocol):
    """翻译能力。实现方在失败时必须抛 :class:`~snaptranslate.domain.errors.TranslationError`。"""

    @property
    def name(self) -> str:
        """线路名（用于日志与调试，如 ``"racing"`` / ``"mymemory"``）。"""
        ...

    def translate(
        self,
        text: str,
        direction: Direction = AUTO_TO_CHINESE,
    ) -> TranslationResult:
        """把 ``text`` 按 ``direction`` 翻译。

        ``direction`` 默认是原版唯一的"自动 → 简体中文"，因此既有调用方（划词/截图）
        的代码与行为完全不变；中译英输入框显式传
        :data:`~snaptranslate.domain.models.translation.CHINESE_TO_ENGLISH`。
        """
        ...
