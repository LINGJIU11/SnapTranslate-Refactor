"""用例：截图 OCR 翻译（原 ``main.py:1069-1174`` ``_do_screen_ocr_translate_job``）。

保留原版三处关键行为：
1. **OCR 互斥**：已有任务在跑时提示"OCR 正在进行中，请稍候…"并直接返回；
2. OCR 依赖缺失走独立分支（标题为"OCR 不可用"）；
3. OCR 完成后复用同一个文本翻译用例（含自动朗读与状态提示）。
"""

from __future__ import annotations

import threading

from snaptranslate.application.dto import ErrorKind, OutcomeKind, TranslationOutcome
from snaptranslate.application.progress import ProgressReporter, Stage
from snaptranslate.application.translate_text import TranslateTextUseCase
from snaptranslate.domain.errors import OcrError, OcrUnavailableError
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.ports.ocr import OcrEngine, OcrStage


class TranslateScreenshotUseCase:
    def __init__(self, ocr_engine: OcrEngine, translate_text: TranslateTextUseCase) -> None:
        self._ocr = ocr_engine
        self._translate_text = translate_text
        self._lock = threading.Lock()
        self._running = False

    def execute(self, bbox: BBox, *, progress: ProgressReporter, no_text_hint: str) -> TranslationOutcome:
        with self._lock:
            if self._running:
                progress.cursor(Stage.OCR_BUSY)
                progress.status(Stage.OCR_BUSY)
                return TranslationOutcome(kind=OutcomeKind.BUSY)
            self._running = True
        try:
            progress.cursor(Stage.OCR_PREPARING)
            try:
                text = self._ocr.extract_text(bbox, on_stage=self._stage_reporter(progress))
            except OcrError as exc:
                unavailable = isinstance(exc, OcrUnavailableError)
                progress.cursor(Stage.OCR_UNAVAILABLE if unavailable else Stage.OCR_FAILED)
                return TranslationOutcome(
                    kind=OutcomeKind.ERROR,
                    error_kind=ErrorKind.OCR_UNAVAILABLE if unavailable else ErrorKind.OCR_FAILED,
                    error_message=exc.render(),
                )
            progress.status(Stage.OCR_TRANSLATING)
            return self._translate_text.execute(text, progress=progress, no_text_hint=no_text_hint)
        finally:
            with self._lock:
                self._running = False

    @staticmethod
    def _stage_reporter(progress: ProgressReporter):
        def report(stage: OcrStage) -> None:
            if stage is OcrStage.CAPTURING:
                progress.status(Stage.OCR_CAPTURING)
                progress.cursor(Stage.OCR_CAPTURING)
            elif stage is OcrStage.RECOGNIZING:
                progress.status(Stage.OCR_RECOGNIZING)
                progress.cursor(Stage.OCR_RECOGNIZING)

        return report
