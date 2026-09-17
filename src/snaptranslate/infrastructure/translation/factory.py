"""翻译器工厂：把"界面选择的翻译源"映射为具体 :class:`Translator`。

对应原版 ``main.py:584-590``（``translate``）与 ``611-615``（``_translate_resilient``）：
选择 ``mymemory`` 时只用 MyMemory 单接口；否则走"自动竞速"。

**线路已被裁剪**（F7，见 KNOWN_ISSUES.md §五）：竞速只剩 clients5 + MyMemory 两条，
原版另有 gtx 与两个 Lingva 镜像——实测前者稳定 429、后者被 Cloudflare 挡 403。
"""

from __future__ import annotations

from snaptranslate.domain.ports.translator import Translator
from snaptranslate.infrastructure.network.proxy_policy import ProxyPolicy
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.google import GoogleClients5Translator
from snaptranslate.infrastructure.translation.mymemory import MyMemoryTranslator
from snaptranslate.infrastructure.translation.racing import RacingTranslator

#: 原版单选值：``google`` = 自动竞速（默认），``mymemory`` = 仅 MyMemory
SOURCE_AUTO_RACE = "google"
SOURCE_MYMEMORY = "mymemory"
TRANSLATE_SOURCES: tuple[str, ...] = (SOURCE_MYMEMORY, SOURCE_AUTO_RACE)


def build_racing_translator(
    cache: TranslationCache,
    *,
    policy: ProxyPolicy | None = None,
) -> RacingTranslator:
    """构造"clients5 + MyMemory"竞速器（都按 ``policy`` 决定是否走代理）。"""
    return RacingTranslator(
        cache,
        GoogleClients5Translator(cache, policy=policy),
        MyMemoryTranslator(cache, policy=policy),
    )


def build_translator(
    source: str,
    cache: TranslationCache | None = None,
    *,
    policy: ProxyPolicy | None = None,
) -> Translator:
    """按翻译源名构造翻译器；未知值等同 ``google``（原版 ``translate`` 的默认分支）。"""
    cache = cache or TranslationCache()
    if source == SOURCE_MYMEMORY:
        return MyMemoryTranslator(cache, policy=policy)
    return build_racing_translator(cache, policy=policy)
