"""翻译器工厂：把"界面选择的翻译源"映射为具体 :class:`Translator`。

对应原版 ``main.py:584-590``（``translate``）与 ``611-615``（``_translate_resilient``）：
选择 ``mymemory`` 时只用 MyMemory 单接口；否则走"自动竞速"。
"""

from __future__ import annotations

from snaptranslate.domain.ports.translator import Translator
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.google import GoogleClients5Translator, GoogleGtxTranslator
from snaptranslate.infrastructure.translation.lingva import LingvaTranslator
from snaptranslate.infrastructure.translation.mymemory import MyMemoryTranslator
from snaptranslate.infrastructure.translation.policy import LINGVA_BASES
from snaptranslate.infrastructure.translation.racing import RacingTranslator

#: 原版单选值：``google`` = 自动竞速（默认），``mymemory`` = 仅 MyMemory
SOURCE_AUTO_RACE = "google"
SOURCE_MYMEMORY = "mymemory"
TRANSLATE_SOURCES: tuple[str, ...] = (SOURCE_MYMEMORY, SOURCE_AUTO_RACE)


def build_racing_translator(cache: TranslationCache, *, lingva_bases: tuple[str, ...] = LINGVA_BASES) -> RacingTranslator:
    """构造"Google 双线路 + MyMemory + Lingva 镜像"竞速器。"""
    lingvas = [LingvaTranslator(base, cache) for base in lingva_bases]
    return RacingTranslator(
        cache,
        GoogleGtxTranslator(cache),
        GoogleClients5Translator(cache),
        MyMemoryTranslator(cache),
        lingvas,
    )


def build_translator(source: str, cache: TranslationCache | None = None) -> Translator:
    """按翻译源名构造翻译器；未知值等同 ``google``（原版 ``translate`` 的默认分支）。"""
    cache = cache or TranslationCache()
    if source == SOURCE_MYMEMORY:
        return MyMemoryTranslator(cache)
    return build_racing_translator(cache)
