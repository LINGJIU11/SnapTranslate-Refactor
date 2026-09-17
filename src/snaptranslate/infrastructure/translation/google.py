"""Google 两条免费线路（原 ``main.py:102-127`` 与 ``202-228``）。

两条线路分别打不同主机（``translate.googleapis.com`` / ``clients5.google.com``），
原版让它们并发竞速以提高弱网下的命中率。
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
    RETRY_BACKOFF_BASE,
    TRANSLATE_RETRIES,
    TRANSLATE_TIMEOUT,
)

GTX_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
CLIENTS5_ENDPOINT = "https://clients5.google.com/translate_a/t"


class GoogleGtxTranslator:
    """``client=gtx`` 逆向接口，质量较好，国内常需可访问 Google 的网络。"""

    name = "google"
    cache_key = "google"

    def __init__(self, cache: TranslationCache, *, timeout=TRANSLATE_TIMEOUT, retries: int = TRANSLATE_RETRIES) -> None:
        self._cache = cache
        self._timeout = timeout
        self._retries = retries

    def translate(self, text: str) -> TranslationResult:
        hit = self._cache.get(self.cache_key, text)
        if hit is not None:
            return TranslationResult(hit)
        url = f"{GTX_ENDPOINT}?client=gtx&sl=auto&tl=zh-CN&dt=t&q={quote(text)}"
        for attempt in range(self._retries):
            try:
                resp = requests.get(url, timeout=self._timeout, headers=HTTP_HEADERS)
                resp.raise_for_status()
                data = json.loads(resp.text)
                translated = "".join(part[0] for part in data[0] if part and part[0])
                out = translated.strip() if translated.strip() else NO_TRANSLATION_RESULT
                if out != NO_TRANSLATION_RESULT:
                    self._cache.put(self.cache_key, text, out)
                return TranslationResult(out)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt + 1 < self._retries:
                    time.sleep(RETRY_BACKOFF_BASE * (attempt + 1))
                    continue
                raise
        # 理论不可达（retries >= 1），仅为类型完整性
        return TranslationResult.no_result()


def parse_clients5_payload(data: object) -> str:
    """解析 ``[[译文, 源语言], ...]`` 结构（原 ``_parse_google_clients5_payload``）。"""
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, list):
        return ""
    parts: list[str] = []
    for row in data:
        if isinstance(row, (list, tuple)) and row:
            cell = row[0]
            if isinstance(cell, str) and cell:
                parts.append(cell)
        elif isinstance(row, str) and row:
            parts.append(row)
    return "".join(parts).strip()


class GoogleClients5Translator:
    """Chrome 词典扩展入口（``client=dict-chrome-ex``），换个域名赌它没被封。"""

    name = "google_clients5"
    cache_key = "google_c5"

    def __init__(self, cache: TranslationCache, *, timeout=TRANSLATE_TIMEOUT, retries: int = TRANSLATE_RETRIES) -> None:
        self._cache = cache
        self._timeout = timeout
        self._retries = retries

    def translate(self, text: str) -> TranslationResult:
        hit = self._cache.get(self.cache_key, text)
        if hit is not None:
            return TranslationResult(hit)
        url = f"{CLIENTS5_ENDPOINT}?client=dict-chrome-ex&sl=auto&tl=zh-CN&q={quote(text, safe='')}"
        for attempt in range(self._retries):
            try:
                resp = requests.get(url, timeout=self._timeout, headers=HTTP_HEADERS)
                resp.raise_for_status()
                data = json.loads(resp.text)
                translated = parse_clients5_payload(data)
                out = translated if translated else NO_TRANSLATION_RESULT
                if out != NO_TRANSLATION_RESULT:
                    self._cache.put(self.cache_key, text, out)
                return TranslationResult(out)
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt + 1 < self._retries:
                    time.sleep(RETRY_BACKOFF_BASE * (attempt + 1))
                    continue
                raise
            except (json.JSONDecodeError, requests.exceptions.HTTPError):
                # 原版在此直接放弃（不再重试），由竞速层决定是否用别的线路
                return TranslationResult.no_result()
        return TranslationResult.no_result()
