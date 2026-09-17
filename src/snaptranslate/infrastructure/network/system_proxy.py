"""读取 Windows 系统代理（原版完全没有这一步，见 KNOWN_ISSUES.md #1）。

``requests`` 只认 ``HTTP_PROXY`` / ``HTTPS_PROXY`` 环境变量，**不读** Windows 的
"Internet 选项 → 代理服务器"（Clash Verge 的"系统代理"就是写在那里的注册表键）。
这就是"开着梯子，Python 却连不上 Google"的原因。
"""

from __future__ import annotations

import winreg

_INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def read_system_proxy() -> str | None:
    """返回系统代理 ``host:port``（未启用返回 ``None``）。

    只取第一个 ``ProxyServer`` 条目；注册表里形如 ``127.0.0.1:7897`` 或
    ``http=127.0.0.1:7897;https=127.0.0.1:7897`` 的写法都能解析。
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INTERNET_SETTINGS) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not int(enabled):
                return None
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    except Exception:
        return None

    text = str(server or "").strip()
    if not text:
        return None
    if "=" in text:  # http=host:port;https=host:port
        for part in text.split(";"):
            if "=" in part:
                _, _, value = part.partition("=")
                value = value.strip()
                if value:
                    return value
        return None
    return text
