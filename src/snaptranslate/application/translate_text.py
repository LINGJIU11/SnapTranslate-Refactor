"""用例：把一段文本翻成简体中文（原 ``main.py:966-1011`` ``_translate_text_job``）。

保留原版的全部行为细节：
- 先 ``clean_text``，空文本走"未检测到可翻译文本"分支；
- 超过 ``MAX_TEXT_LENGTH``（120）截断并加 ``...``；
- 含 ≥2 个拉丁字母就**自动朗读**（原版没有开关，音量来自界面滑块）；
- 成功/失败都会更新光标提示与状态栏。
"""

from __future__ import annotations

from typing import Callable

from snaptranslate.application.dto import ErrorKind, OutcomeKind, TranslationOutcome
from snaptranslate.application.progress import ProgressReporter, Stage
from snaptranslate.domain.errors import SnapTranslateError
from snaptranslate.domain.models.translation import TranslationResult
from snaptranslate.domain.ports.error_formatter import ErrorFormatter
from snaptranslate.domain.ports.translator import Translator
from snaptranslate.domain.ports.tts import TextToSpeech
from snaptranslate.domain.services.text_cleaning import (
    DEFAULT_MAX_TEXT_LENGTH,
    clean_text,
    is_likely_english,
    truncate,
)

#: 原 ``main.py:8``：朗读进程超时 8 秒
SPEAK_TIMEOUT_SEC = 8.0


class TranslateTextUseCase:
    """文本翻译用例。

    :param translator_provider: 按"翻译源"取值返回对应翻译器（由 bootstrap 注入工厂）
    :param source_provider: 返回当前翻译源（界面单选值，默认 ``google``）
    :param tts: 朗读端口
    :param tts_volume_provider: 返回当前朗读音量（0~100）
    :param format_error: 把底层异常格式化成用户可读文案（基础设施实现）
    """

    def __init__(
        self,
        translator_provider: Callable[[str], Translator],
        source_provider: Callable[[], str],
        tts: TextToSpeech,
        format_error: ErrorFormatter,
        tts_volume_provider: Callable[[], int] | None = None,
        *,
        max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
    ) -> None:
        self._translator_provider = translator_provider
        self._source_provider = source_provider
        self._tts = tts
        self._format_error = format_error
        self._tts_volume_provider = tts_volume_provider
        self._max_text_length = max_text_length

    # —— 供"最近一条翻译"等场景复用 ——
    def translate(self, text: str) -> TranslationResult:
        """只做翻译，不涉及界面状态（原 ``TranslatorApp.translate``）。"""
        translator = self._translator_provider(self._current_source())
        return translator.translate(text)

    def _current_source(self) -> str:
        try:
            return self._source_provider() or "google"
        except Exception:
            # 原 ``_translate_primary_source``：读取 Tk 变量失败时回退 google
            return "google"

    def _tts_volume(self) -> int:
        if self._tts_volume_provider is None:
            return 100
        try:
            return max(0, min(100, int(self._tts_volume_provider())))
        except Exception:
            return 100

    def execute(self, raw_text: str, *, progress: ProgressReporter, no_text_hint: str) -> TranslationOutcome:
        cleaned = clean_text(raw_text)
        if not cleaned:
            progress.cursor(Stage.NO_TEXT)
            return TranslationOutcome(kind=OutcomeKind.NO_TEXT, error_message=no_text_hint)

        truncated = len(cleaned) > self._max_text_length
        text = truncate(cleaned, self._max_text_length)

        if is_likely_english(text):
            self._tts.speak_async(text, volume=self._tts_volume(), prefer_en=True, timeout_sec=SPEAK_TIMEOUT_SEC)

        try:
            progress.cursor(Stage.TRANSLATING)
            result = self.translate(text)
            progress.cursor(Stage.DONE)
            return TranslationOutcome(
                kind=OutcomeKind.OK,
                source_text=text,
                result=result,
                truncated=truncated,
            )
        except SnapTranslateError as exc:
            progress.cursor(Stage.FAILED)
            return TranslationOutcome(
                kind=OutcomeKind.ERROR,
                source_text=text,
                truncated=truncated,
                error_kind=ErrorKind.TRANSLATE,
                error_message=exc.render(),
            )
        except Exception as exc:  # noqa: BLE001 - 与原版一致：任何异常都要给用户一个可读提示
            progress.cursor(Stage.FAILED)
            return TranslationOutcome(
                kind=OutcomeKind.ERROR,
                source_text=text,
                truncated=truncated,
                error_kind=ErrorKind.TRANSLATE,
                error_message=self._format_error(exc),
            )
