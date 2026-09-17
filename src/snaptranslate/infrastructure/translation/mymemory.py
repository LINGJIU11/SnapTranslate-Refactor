"""MyMemory 免费接口（原 ``main.py:129-182``）。

它是**翻译记忆库**而非机器翻译引擎：免密钥、国内多数网络可直连，但
① 有每日匿名额度，超限时在“译文”里返回 ``MYMEMORY WARNING`` 文案；
② 纯英文短词有时会原样返回，因此原版会按内容猜 ``langpair`` 顺序重试。
"""

from __future__ import annotations

import json
import re
import time

import requests

from snaptranslate.domain.errors import TranslationError
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

MYMEMORY_ENDPOINT = "https://api.mymemory.translated.net/get"


class TranslationQuotaError(TranslationError):
    """MyMemory 免费额度用尽（原版抛 ``RuntimeError(提示文案)``，竞速层优先抛出它）。"""


def parse_mymemory_response(resp: requests.Response) -> str:
    """解析响应；返回空串表示"没翻出来"；额度提示文案抛 :class:`TranslationQuotaError`。"""
    data = resp.json()
    block = data.get("responseData") or {}
    out = (block.get("translatedText") or "").strip()
    if not out:
        return ""
    upper = out.upper()
    if "MYMEMORY WARNING" in upper or ("QUOTA" in upper and "EXCEED" in upper):
        raise RuntimeError(out)
    return out


def langpairs_for(text: str, direction: Direction = AUTO_TO_CHINESE) -> tuple[str, ...]:
    """解释 ``langpair`` 的取值顺序。

    - ``direction.langpair`` 显式给出时（如中译英的 ``zh-CN|en``）直接用它；
    - 否则沿用原版语义：含拉丁字母时优先 ``en|zh-CN``，否则先试自动检测
      （原 ``_mymemory_langpairs``）。
    """
    if direction.langpair:
        return (direction.langpair,)
    if re.search(r"[A-Za-z]", text):
        return ("en|zh-CN", "Autodetect|zh-CN")
    return ("Autodetect|zh-CN", "en|zh-CN")


class MyMemoryTranslator:
    name = "mymemory"
    cache_key = "mymemory"

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
        for langpair in langpairs_for(text, direction):
            for attempt in range(self._retries):
                try:
                    resp = http_get(
                        MYMEMORY_ENDPOINT,
                        params={"q": text, "langpair": langpair},
                        timeout=self._timeout,
                        headers=HTTP_HEADERS,
                        policy=self._policy,
                    )
                    resp.raise_for_status()
                    out = parse_mymemory_response(resp)
                    if out:
                        self._cache.put(self.cache_key, text, out, direction.variant)
                        return TranslationResult(out)
                    break
                except RuntimeError as exc:
                    # 额度提示：原版向上抛，竞速层优先展示它
                    raise TranslationQuotaError(str(exc)) from exc
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                    if attempt + 1 < self._retries:
                        time.sleep(RETRY_BACKOFF_BASE * (attempt + 1))
                        continue
                    break
                except requests.exceptions.HTTPError:
                    break
                except (json.JSONDecodeError, KeyError, ValueError):
                    break
        return TranslationResult(NO_TRANSLATION_RESULT)
