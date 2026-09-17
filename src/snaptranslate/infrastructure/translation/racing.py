"""并发竞速策略（原 ``main.py:262-304`` ``_translate_parallel_race_zh``）。

原版同时打 5 条线路；**2026-09-17 按实测裁剪为 2 条**（见 KNOWN_ISSUES.md §五 F7）：

- ``translate.googleapis.com``（gtx）稳定 **HTTP 429**，走代理也一样；
- 两个 Lingva 镜像被 Cloudflare 挡（**HTTP 403**，返回挑战页）。

留下真正能供货的 ``clients5.google.com`` 与 ``api.mymemory.translated.net``。
其余语义与原版一致：谁先返回有效译文用谁；命中缓存直接短路；
全部失败时优先抛 MyMemory 的额度提示。
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from snaptranslate.domain.models.translation import AUTO_TO_CHINESE, Direction, TranslationResult
from snaptranslate.domain.ports.translator import Translator
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.mymemory import TranslationQuotaError
from snaptranslate.infrastructure.translation.policy import (
    CACHE_ENGINE_KEYS,
    ENGINE_LABEL_GOOGLE_CLIENTS5,
    ENGINE_LABEL_MYMEMORY,
    RACE_MAX_WORKERS,
)


class RacingTranslator:
    """多线路并发竞速翻译器（当前 2 条线路）。

    ``translate(text, direction)`` 把方向原样透传给每条线路，并把它纳入缓存键——
    同一个句子"中→英"与"自动→中"的结果不会互相串味（见
    :class:`~snaptranslate.domain.models.translation.Direction`）。
    """

    name = "racing"

    def __init__(
        self,
        cache: TranslationCache,
        google_clients5: Translator,
        mymemory: Translator,
        *,
        max_workers: int = RACE_MAX_WORKERS,
    ) -> None:
        self._cache = cache
        self._clients5 = google_clients5
        self._mymemory = mymemory
        self._max_workers = max_workers

    @property
    def line_names(self) -> tuple[str, ...]:
        """当前参与竞速的线路名（日志/自检用）。"""
        return (ENGINE_LABEL_GOOGLE_CLIENTS5, ENGINE_LABEL_MYMEMORY)

    def translate(
        self,
        text: str,
        direction: Direction = AUTO_TO_CHINESE,
    ) -> TranslationResult:
        for key in CACHE_ENGINE_KEYS:
            hit = self._cache.get(key, text, direction.variant)
            if hit is not None:
                return TranslationResult(hit)

        executor = ThreadPoolExecutor(max_workers=self._max_workers)
        future_to_label: dict[Future, str] = {}
        try:
            future_to_label[executor.submit(self._clients5.translate, text, direction)] = (
                ENGINE_LABEL_GOOGLE_CLIENTS5
            )
            future_to_label[executor.submit(self._mymemory.translate, text, direction)] = (
                ENGINE_LABEL_MYMEMORY
            )

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
