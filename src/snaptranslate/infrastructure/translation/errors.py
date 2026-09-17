"""翻译失败文案格式化（原 ``main.py:307-325`` ``_format_translate_failure``）。

逐分支保留原版行为：

1. DNS 类失败 → 固定中文提示；
2. ``requests`` 异常 → ``翻译请求失败（类型）：正文``（正文超 260 字截断加省略号）；
3. 其它异常 → ``str(exc)``（超 400 字截断加省略号）。
"""

from __future__ import annotations

import requests

_DNS_MARKERS: tuple[str, ...] = (
    "failed to resolve",
    "getaddrinfo failed",
    "nameresolutionerror",
    "name resolution",
    "name or service not known",
)

_DNS_MESSAGE = (
    "部分翻译线路 DNS 解析失败（常见于国内网络）。可改用「仅 MyMemory」以省并发；"
    "若使用自动竞速，请检查代理/VPN 是否对 Python 生效。"
)

_REQUEST_EXC_MAX = 260
_GENERIC_MAX = 400


def format_translate_failure(exc: BaseException) -> str:
    raw = str(exc)
    low = raw.lower()
    if any(marker in low for marker in _DNS_MARKERS):
        return _DNS_MESSAGE
    if isinstance(exc, requests.exceptions.RequestException):
        if len(raw) > _REQUEST_EXC_MAX:
            return f"翻译请求失败（{type(exc).__name__}）：{raw[:_REQUEST_EXC_MAX]}…"
        return f"翻译请求失败：{raw}"
    return raw if len(raw) <= _GENERIC_MAX else f"{raw[:_GENERIC_MAX]}…"


class RequestsErrorFormatter:
    """实现 :class:`~snaptranslate.domain.ports.error_formatter.ErrorFormatter`。"""

    def __call__(self, exc: BaseException) -> str:
        return format_translate_failure(exc)
