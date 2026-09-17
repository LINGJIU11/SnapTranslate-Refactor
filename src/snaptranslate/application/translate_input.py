"""用例：把用户敲进输入框的中文翻成英文（**新增功能**，原版没有对应实现）。

与划词路径（:mod:`.translate_text`）的分工：

============================  ==========================================  ==================
用例                            输入来源                                    方向
============================  ==========================================  ==================
``TranslateTextUseCase``       划词 / OCR / 界面里选中的文本               自动 → 简体中文
``TranslateInputUseCase``      **用户手敲**在浮层输入框里的中文             中文 → 英文
============================  ==========================================  ==================

刻意只在"用例"这一层新增，翻译本身仍旧交给同一个 :class:`Translator` 端口
（默认装配的是"clients5 + MyMemory"竞速器），所以换线路、加代理、走缓存
这些能力**不需要**为新功能重写一遍。
"""

from __future__ import annotations

from typing import Callable

from snaptranslate.application.dto import ErrorKind, OutcomeKind, TranslationOutcome
from snaptranslate.domain.errors import SnapTranslateError
from snaptranslate.domain.models.translation import (
    CHINESE_TO_ENGLISH,
    Direction,
    TranslationResult,
)
from snaptranslate.domain.ports.error_formatter import ErrorFormatter
from snaptranslate.domain.ports.translator import Translator
from snaptranslate.domain.services.text_cleaning import clean_text, truncate

#: 输入框允许的最大长度：MyMemory 的匿名额度对长文本不友好，客户端接口也有 URL 长度上限。
INPUT_MAX_LENGTH = 1000

#: 方向提供者：默认中译英；测试或将来加"英译中"时替换即可
DirectionProvider = Callable[[], Direction]


class TranslateInputUseCase:
    """输入框翻译用例（异步由表示层负责，本类只做同步的一次翻译）。

    :param translator_provider: 按"翻译源"取值返回翻译器（与划词路径共用同一个工厂）
    :param source_provider: 返回当前翻译源（界面单选值）
    :param format_error: 把底层异常格式化成用户可读文案（基础设施实现）
    :param direction_provider: 翻译方向，默认 :data:`CHINESE_TO_ENGLISH`
    """

    def __init__(
        self,
        translator_provider: Callable[[str], Translator],
        source_provider: Callable[[], str],
        format_error: ErrorFormatter,
        *,
        direction_provider: DirectionProvider | None = None,
        max_length: int = INPUT_MAX_LENGTH,
    ) -> None:
        self._translator_provider = translator_provider
        self._source_provider = source_provider
        self._format_error = format_error
        self._direction_provider = direction_provider or (lambda: CHINESE_TO_ENGLISH)
        self._max_length = max_length

    @property
    def direction(self) -> Direction:
        return self._direction_provider()

    @property
    def max_length(self) -> int:
        """最长可翻译字符数（表示层用它拼"已截断"的提示文案）。"""
        return self._max_length

    def translate(self, text: str) -> TranslationResult:
        """只做翻译（供将来"朗读英文""收录英文"等场景复用）。"""
        translator = self._translator_provider(self._current_source())
        return translator.translate(text, self.direction)

    def execute(self, raw_text: str) -> TranslationOutcome:
        """执行一次输入翻译。

        失败不抛异常，统一返回 ``TranslationOutcome``——与划词路径一致，
        表示层只做"把结果画到框里"这一件事。**文案不在本层拼**（统一放在
        ``presentation/texts.py``），这里只给"数据"。
        """
        cleaned = clean_text(raw_text)
        if not cleaned:
            return TranslationOutcome(kind=OutcomeKind.NO_TEXT)

        truncated = len(cleaned) > self._max_length
        text = truncate(cleaned, self._max_length)
        try:
            result = self.translate(text)
        except SnapTranslateError as exc:
            return TranslationOutcome(
                kind=OutcomeKind.ERROR,
                source_text=text,
                truncated=truncated,
                error_kind=ErrorKind.TRANSLATE,
                error_message=exc.render(),
            )
        except Exception as exc:  # noqa: BLE001 - 与划词路径一致：任何异常都给可读文案
            return TranslationOutcome(
                kind=OutcomeKind.ERROR,
                source_text=text,
                truncated=truncated,
                error_kind=ErrorKind.TRANSLATE,
                error_message=self._format_error(exc),
            )
        return TranslationOutcome(
            kind=OutcomeKind.OK,
            source_text=text,
            result=result,
            truncated=truncated,
        )

    def _current_source(self) -> str:
        try:
            return self._source_provider() or "google"
        except Exception:
            # 与 ``TranslateTextUseCase`` 一致：读 Tk 变量失败时回退竞速
            return "google"


__all__ = [
    "INPUT_MAX_LENGTH",
    "DirectionProvider",
    "TranslateInputUseCase",
]
