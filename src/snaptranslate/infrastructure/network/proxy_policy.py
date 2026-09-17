"""代理策略：三种模式 + 预设，并负责"这个主机要不要走代理"。

模式（存在 ``main_settings.json`` 的 ``proxy_mode``）::

    off     直连（默认；实测 clients5 与 MyMemory 直连就能用）
    system  跟随 Windows 系统代理（Clash Verge 开"系统代理"时就是它 → 127.0.0.1:7897）
    custom  自定义，例如 http://127.0.0.1:7897（本地 Clash）或 http://10.8.0.6:8080（香港出口）

两个约定：

1. **内网/回环地址永远直连**（10.* / 192.168.* / 172.16-31.* / localhost），
   避免把访问门户、WG 节点、内网服务的请求也塞进代理；
2. 代理连不上时由 :mod:`snaptranslate.infrastructure.network.http` 回退直连一次，
   所以"跟随系统代理"不会因为 Clash 被关掉而把翻译拖死。
"""

from __future__ import annotations

import ipaddress
from typing import Callable
from urllib.parse import urlsplit

from snaptranslate.config.proxy import (
    DEFAULT_MODE,
    MODE_CUSTOM,
    MODE_OFF,
    MODE_SYSTEM,
    MODES,
    PRESET_CLASH,
    PRESET_HONGKONG,
    normalize_proxy_url,
)

_PRIVATE_HINTS = ("localhost", ".local")


def is_private_host(host: str) -> bool:
    """内网/回环主机 → 直连（不经过代理）。"""
    name = (host or "").strip().lower()
    if not name or name in _PRIVATE_HINTS or name.endswith(_PRIVATE_HINTS):
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return "." not in name  # 单段主机名（内网短名）也当内网
    return address.is_private or address.is_loopback or address.is_link_local


class ProxyPolicy:
    """当前生效的代理设置（界面改完立即生效，无需重启）。"""

    def __init__(
        self,
        mode: str = DEFAULT_MODE,
        url: str = "",
        *,
        system_reader: Callable[[], str | None] | None = None,
    ) -> None:
        self._mode = mode if mode in MODES else DEFAULT_MODE
        self._url = normalize_proxy_url(url)
        self._system_reader = system_reader

    # —— 配置 ——
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def url(self) -> str:
        return self._url

    def configure(self, mode: str, url: str = "") -> None:
        self._mode = mode if mode in MODES else DEFAULT_MODE
        self._url = normalize_proxy_url(url)

    def effective_url(self) -> str | None:
        """当前真正会用到的代理地址（``off`` 或解析不到系统代理时返回 ``None``）。"""
        if self._mode == MODE_OFF:
            return None
        if self._mode == MODE_SYSTEM:
            raw = self._read_system()
            if not raw:
                return None
            return normalize_proxy_url(raw)
        return self._url or None

    def describe(self) -> str:
        """给界面/日志看的一行说明。"""
        url = self.effective_url()
        if url:
            return f"代理：{url}（{self._mode}）"
        if self._mode == MODE_SYSTEM:
            return "代理：跟随系统，但系统未启用代理 → 直连"
        return "代理：直连"

    # —— 使用 ——
    def proxies_for(self, host: str) -> dict[str, str] | None:
        """给 ``requests`` 用的 proxies 字典；返回 ``None`` 表示直连。"""
        if is_private_host(host):
            return None
        url = self.effective_url()
        if not url:
            return None
        return {"http": url, "https": url}

    def proxies_for_url(self, url: str) -> dict[str, str] | None:
        try:
            host = urlsplit(url).hostname or ""
        except Exception:
            host = ""
        return self.proxies_for(host)

    def _read_system(self) -> str | None:
        if self._system_reader is None:
            from snaptranslate.infrastructure.network.system_proxy import read_system_proxy

            self._system_reader = read_system_proxy
        try:
            return self._system_reader()
        except Exception:
            return None
