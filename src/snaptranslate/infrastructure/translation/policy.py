"""翻译网络策略常量。

收敛原版 ``main.py:46-54``、``97-99`` 以及各引擎内联的魔法数字。

**线路裁剪（2026-09-17，见 KNOWN_ISSUES.md §五 F7）**：原版竞速 5 条线路，实测
``translate.googleapis.com`` 稳定 429（限流）、两个 Lingva 镜像被 Cloudflare 挡（403），
它们只是在拖慢首字延迟，因此**只保留实际能供货的两条**：
``clients5.google.com`` 与 ``api.mymemory.translated.net``。
（被裁掉的实现可从 git tag ``stage1.4-proxy`` 取回。）
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

#: 原 ``_TRANS_OK_CACHE_MAX``
CACHE_MAX_SIZE = 2048

#: 竞速的线程池规模 = 线路条数（原版是 ``min(32, 3 + len(LINGVA_BASES))``）
RACE_MAX_WORKERS = 2

#: 竞速前检查缓存用的引擎键顺序（只含仍在用的线路）
CACHE_ENGINE_KEYS: tuple[str, ...] = ("google_c5", "mymemory")

#: 引擎键与展示标签（标签只进日志/控制台，不上悬浮卡片，见 F8）
ENGINE_LABEL_GOOGLE_CLIENTS5 = "Google（clients5）"
ENGINE_LABEL_MYMEMORY = "MyMemory"

