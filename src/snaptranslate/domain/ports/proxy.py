"""代理设置端口（界面可改、请求层可读）。

放在 domain 是为了让三层都能用同一个抽象：基础设施提供实现（真正发请求时用），
应用层读写设置，表示层渲染与修改——而表示层不必 import infrastructure。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProxySettings(Protocol):
    @property
    def mode(self) -> str:
        """``off`` / ``system`` / ``custom``（取值约定见 ``config.proxy``）。"""
        ...

    @property
    def url(self) -> str:
        """``custom`` 模式下的代理地址（``http://host:port``）。"""
        ...

    def configure(self, mode: str, url: str = "") -> None:
        """改完立即生效（无需重启程序）。"""
        ...

    def effective_url(self) -> str | None:
        """当前真正会用到的代理地址；``None`` 表示直连。"""
        ...

    def describe(self) -> str:
        """给界面/日志的一行说明。"""
        ...
