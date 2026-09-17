"""用例：划词翻译（原 ``main.py:1043-1048`` ``_do_translate_job``）。

**本用例修掉了一个原版缺陷**（见 KNOWN_ISSUES.md #20）：原版取词失败时无法识别，
会把剪贴板里的旧内容当原文翻译；现在取词结果里带 ``copied`` 标志，
未真正复制成功就直接报"取词失败"，绝不拿旧内容顶替。
"""

from __future__ import annotations

from snaptranslate.application.dto import OutcomeKind, TranslationOutcome
from snaptranslate.application.progress import ProgressReporter, Stage
from snaptranslate.application.translate_text import TranslateTextUseCase
from snaptranslate.domain.ports.selection_reader import SelectionReader


class TranslateSelectionUseCase:
    """取词 → 翻译。

    "是否启用划词翻译"的开关判断留在表示层（原版读 Tk 变量 ``enable_var``）。
    """

    def __init__(self, selection_reader: SelectionReader, translate_text: TranslateTextUseCase) -> None:
        self._selection_reader = selection_reader
        self._translate_text = translate_text

    def execute(
        self,
        *,
        progress: ProgressReporter,
        no_text_hint: str,
        capture_failed_hint: str = "",
        modifier_hint: str = "",
    ) -> TranslationOutcome:
        progress.cursor(Stage.READING_SELECTION)
        capture = self._selection_reader.read_selected_text()
        if not capture.copied:
            # 剪贴板没有变化 = 这次 Ctrl+C 没生效。**不要把 clipboard_text 当原文**
            progress.cursor(Stage.CAPTURE_FAILED)
            hint = modifier_hint if (capture.modifiers_held and modifier_hint) else capture_failed_hint
            return TranslationOutcome(
                kind=OutcomeKind.NO_TEXT,
                error_message=hint or no_text_hint,
                capture_failed=True,
            )
        return self._translate_text.execute(capture.text, progress=progress, no_text_hint=no_text_hint)
