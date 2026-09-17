"""Google clients5 线路（原 ``main.py:202-228``）。

原版还有一条 ``translate.googleapis.com``（gtx）线路，因稳定 429 已在 F7 中裁掉
（见 KNOWN_ISSUES.md §五）；这里只保留实际能供货的 ``clients5.google.com``。
"""

from __future__ import annotations

import json
import time
from urllib.parse import quote

import requests

from snaptranslate.domain.models.translation import (
    AUTO_TO_CHINESE,
    NO_TRANSLATION_RESULT,
    Direction,
    TranslationResult,
)
from snaptranslate.infrastructure.network.http import get as http_get
from snaptranslate.infrastructure.network.proxy_policy import ProxyPolicy
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.policy import (
    HTTP_HEADERS,
    RETRY_BACKOFF_BASE,
    TRANSLATE_RETRIES,
    TRANSLATE_TIMEOUT,
)

CLIENTS5_ENDPOINT = "https://clients5.google.com/translate_a/t"


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
    """Chrome 词典扩展入口（``client=dict-chrome-ex``）。"""

    name = "google_clients5"
    cache_key = "google_c5"

    def __init__(
        self,
        cache: TranslationCache,
        *,
        timeout=TRANSLATE_TIMEOUT,
        retries: int = TRANSLATE_RETRIES,
        policy: ProxyPolicy | None = None,
    ) -> None:
        self._cache = cache
        self._timeout = timeout
        self._retries = retries
        self._policy = policy

    def translate(
        self,
        text: str,
        direction: Direction = AUTO_TO_CHINESE,
    ) -> TranslationResult:
        hit = self._cache.get(self.cache_key, text, direction.variant)
        if hit is not None:
            return TranslationResult(hit)
        url = (
            f"{CLIENTS5_ENDPOINT}?client=dict-chrome-ex"
            f"&sl={quote(direction.source, safe='')}&tl={quote(direction.target, safe='')}"
            f"&q={quote(text, safe='')}"
        )
        for attempt in range(self._retries):
            try:
                resp = http_get(url, timeout=self._timeout, headers=HTTP_HEADERS, policy=self._policy)
                resp.raise_for_status()
                data = json.loads(resp.text)
                translated = parse_clients5_payload(data)
                out = translated if translated else NO_TRANSLATION_RESULT
                if out != NO_TRANSLATION_RESULT:
                    self._cache.put(self.cache_key, text, out, direction.variant)
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
