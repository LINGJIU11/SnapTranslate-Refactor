"""翻译网络策略常量。

收敛原版 ``main.py:46-54``、``97-99`` 以及各引擎内联的魔法数字。
"""

from __future__ import annotations

#: 原 ``TRANSLATE_RETRIES``
TRANSLATE_RETRIES = 2
#: 原 ``TRANSLATE_TIMEOUT = (6, 22)``：连接超时 6s / 读取超时 22s
TRANSLATE_TIMEOUT: tuple[float, float] = (6, 22)
#: 重试退避基数：``0.75 * (attempt + 1)`` 秒
RETRY_BACKOFF_BASE = 0.75

#: 原 ``HTTP_HEADERS``
HTTP_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SnapTranslate/1.0",
}

#: 原 ``LINGVA_BASES``（注释：部分实例在国内可能 403）
LINGVA_BASES: tuple[str, ...] = (
    "https://lingva.ml",
    "https://translate.plausibility.cloud",
)

#: 原 ``_TRANS_OK_CACHE_MAX``
CACHE_MAX_SIZE = 2048

#: 原 ``_translate_lingva_mirror`` 中的 URL 长度上限
LINGVA_MAX_QUERY_LEN = 1400

#: 原 ``_translate_parallel_race_zh`` 的线程池规模公式 ``min(32, 3 + len(LINGVA_BASES))``
RACE_MAX_WORKERS = min(32, 3 + len(LINGVA_BASES))

#: 竞速前检查缓存时使用的引擎键顺序（原 ``main.py:267``）
CACHE_ENGINE_KEYS: tuple[str, ...] = ("google", "google_c5", "mymemory", "lingva")

#: 引擎键与展示标签（原 ``main.py:276-285``）
ENGINE_LABEL_GOOGLE = "Google"
ENGINE_LABEL_GOOGLE_CLIENTS5 = "Google（clients5）"
ENGINE_LABEL_MYMEMORY = "MyMemory"
