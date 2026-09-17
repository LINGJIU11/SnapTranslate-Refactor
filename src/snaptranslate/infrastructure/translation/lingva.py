"""Lingva 镜像（原 ``main.py:231-259``）。

Lingva 是开源的 Google 翻译前端，反代性质、实例随时可能挂掉，所以原版配了两个镜像并发尝试。
注意原版**两个镜像共用同一个缓存键** ``"lingva"``（谁先成功都会被另一个读到），这里保留。
"""

from __future__ import annotations

import json
import time
from urllib.parse import quote

import requests

from snaptranslate.domain.models.translation import NO_TRANSLATION_RESULT, TranslationResult
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.policy import (
    HTTP_HEADERS,
    LINGVA_MAX_QUERY_LEN,
    RETRY_BACKOFF_BASE,
    TRANSLATE_RETRIES,
    TRANSLATE_TIMEOUT,
)


def host_of(base: str) -> str:
    """``https://lingva.ml`` → ``lingva.ml``（原版用它拼引擎标签）。"""
    return base.split("//", 1)[-1].split("/", 1)[0]


class LingvaTranslator:
    name = "lingva"
    cache_key = "lingva"

    def __init__(
        self,
        base: str,
        cache: TranslationCache,
        *,
        timeout=TRANSLATE_TIMEOUT,
        retries: int = TRANSLATE_RETRIES,
    ) -> None:
        self.base = base.rstrip("/")
        self.host = host_of(base)
        self._cache = cache
        self._timeout = timeout
        self._retries = retries

    @property
    def label(self) -> str:
        return f"Lingva（{self.host}）"

    def translate(self, text: str) -> TranslationResult:
        shared = self._cache.get(self.cache_key, text)
        if shared is not None:
            return TranslationResult(shared)
        segment = quote(text, safe="")
        if len(segment) > LINGVA_MAX_QUERY_LEN:
            return TranslationResult.no_result()
        url = f"{self.base}/api/v1/auto/zh/{segment}"
        for attempt in range(self._retries):
            try:
                resp = requests.get(url, timeout=self._timeout, headers=HTTP_HEADERS)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    return TranslationResult.no_result()
                out = (data.get("translation") or "").strip()
                if not out:
                    return TranslationResult.no_result()
                self._cache.put(self.cache_key, text, out)
                return TranslationResult(out)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt + 1 < self._retries:
                    time.sleep(RETRY_BACKOFF_BASE * (attempt + 1))
                    continue
                return TranslationResult.no_result()
            except (json.JSONDecodeError, requests.exceptions.RequestException, ValueError, TypeError):
                return TranslationResult.no_result()
        return TranslationResult(NO_TRANSLATION_RESULT)
