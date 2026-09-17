"""用例：划词翻译（原 ``main.py:1043-1048`` ``_do_translate_job``）。"""

from __future__ import annotations

from snaptranslate.application.dto import TranslationOutcome
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

    def execute(self, *, progress: ProgressReporter, no_text_hint: str) -> TranslationOutcome:
        progress.cursor(Stage.READING_SELECTION)
        text = self._selection_reader.read_selected_text()
        return self._translate_text.execute(text, progress=progress, no_text_hint=no_text_hint)
