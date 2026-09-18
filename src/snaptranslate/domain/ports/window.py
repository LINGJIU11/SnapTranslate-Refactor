"""窗口激活端口。

原版在 ``main.py:1208-1263`` 用 ``AttachThreadInput`` + ``SetForegroundWindow``
把截图遮罩抢到前台；这段 Win32 逻辑属于基础设施，表示层只调用本端口。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WindowActivator(Protocol):
    def foreground(self) -> int:
        """当前前台窗口句柄；取不到返回 0。

        **新增功能**（中译英输入框）用它记住"按热键时用户正在用的窗口"，
        翻译返回后把键盘焦点还回去。
        """
        ...

    def find_window(self, title: str) -> int:
        """按窗口标题查句柄；找不到返回 0。

        **新增功能**（启动器）用它判断"某个子窗口是否已经开着"，以及把它唤到前台。
        """
        ...

    def force_foreground(self, hwnd: int) -> None:
        """把指定窗口推到前台（失败静默，与原版一致）。"""
        ...
