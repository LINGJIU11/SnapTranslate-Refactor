"""并发竞速策略（原 ``main.py:262-304`` ``_translate_parallel_race_zh``）。

同时向多条免费线路发起请求，**谁先返回有效译文就用谁**，其余请求在后台自然结束。
沿用原版的两个关键语义：

1. 竞速前先查缓存：命中则直接返回且**不带引擎标签**（界面不会显示"（X 最快返回）"）；
2. 全部失败时优先抛 MyMemory 的额度提示（原版判断 ``isinstance(err, RuntimeError)``）。
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from snaptranslate.domain.errors import TranslationError
from snaptranslate.domain.models.translation import TranslationResult
from snaptranslate.domain.ports.translator import Translator
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.lingva import LingvaTranslator
from snaptranslate.infrastructure.translation.mymemory import TranslationQuotaError
from snaptranslate.infrastructure.translation.policy import (
    CACHE_ENGINE_KEYS,
    ENGINE_LABEL_GOOGLE,
    ENGINE_LABEL_GOOGLE_CLIENTS5,
    ENGINE_LABEL_MYMEMORY,
    RACE_MAX_WORKERS,
)


class RacingTranslator:
    """多线路并发竞速翻译器。"""

    name = "racing"

    def __init__(
        self,
        cache: TranslationCache,
        google_gtx: Translator,
        google_clients5: Translator,
        mymemory: Translator,
        lingvas: list[LingvaTranslator],
        *,
        max_workers: int = RACE_MAX_WORKERS,
    ) -> None:
        self._cache = cache
        self._gtx = google_gtx
        self._clients5 = google_clients5
        self._mymemory = mymemory
        self._lingvas = lingvas
        self._max_workers = max_workers

    def translate(self, text: str) -> TranslationResult:
        for key in CACHE_ENGINE_KEYS:
            hit = self._cache.get(key, text)
            if hit is not None:
                return TranslationResult(hit)

        executor = ThreadPoolExecutor(max_workers=self._max_workers)
        future_to_label: dict[Future, str] = {}
        try:
            future_to_label[executor.submit(self._gtx.translate, text)] = ENGINE_LABEL_GOOGLE
            future_to_label[executor.submit(self._clients5.translate, text)] = ENGINE_LABEL_GOOGLE_CLIENTS5
            future_to_label[executor.submit(self._mymemory.translate, text)] = ENGINE_LABEL_MYMEMORY
            for lingva in self._lingvas:
                future_to_label[executor.submit(lingva.translate, text)] = lingva.label

            errors: list[BaseException] = []
            for future in as_completed(future_to_label):
                exception = future.exception()
                if exception is not None:
                    errors.append(exception)
                    continue
                result = future.result()
                if result and not result.is_empty:
                    return TranslationResult(result.text, future_to_label[future])
            if errors:
                for error in errors:
                    if isinstance(error, TranslationQuotaError):
                        raise error
                raise errors[0]
            return TranslationResult.no_result()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
