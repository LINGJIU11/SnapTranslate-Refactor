"""代理设置的取值约定（叶子层，各层都能读）。

放在 ``config`` 是因为它同时被基础设施（真正发请求）、应用层（读写设置）、
表示层（界面单选）使用，而这三层都要能 import 它。
"""

from __future__ import annotations

MODE_OFF = "off"
MODE_SYSTEM = "system"
MODE_CUSTOM = "custom"
MODES: tuple[str, ...] = (MODE_OFF, MODE_SYSTEM, MODE_CUSTOM)
DEFAULT_MODE = MODE_OFF

#: 预设一：本地 Clash Verge（mixed 端口，实测 127.0.0.1:7897）
PRESET_CLASH = "http://127.0.0.1:7897"
#: 预设二：香港出口（走 WireGuard，需在服务器上起一个 HTTP 代理）
PRESET_HONGKONG = "http://10.8.0.6:8080"


def normalize_proxy_url(raw: str) -> str:
    """把用户输入整理成 ``scheme://host:port``；不带 scheme 时补 ``http://``。"""
    text = (raw or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    return text.rstrip("/")
