"""窗口激活端口。

原版在 ``main.py:1208-1263`` 用 ``AttachThreadInput`` + ``SetForegroundWindow``
把截图遮罩抢到前台；这段 Win32 逻辑属于基础设施，表示层只调用本端口。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WindowActivator(Protocol):
    def force_foreground(self, hwnd: int) -> None:
        """把指定窗口推到前台（失败静默，与原版一致）。"""
        ...
