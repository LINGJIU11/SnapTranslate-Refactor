"""鼠标指针位置端口。

原版用 ``user32.GetCursorPos``（``main.py:617-620``）；阶段一为了方便改成了 Tk 的
``winfo_pointerxy``。现在需要**在热键按下的瞬间**（监听线程里）取一次坐标，而 Tk 调用
必须留在主线程，所以这里把"取指针位置"抽成端口，由基础设施层用 Win32 实现（线程安全）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Pointer(Protocol):
    def position(self) -> tuple[int, int]:
        """返回当前鼠标屏幕坐标 ``(x, y)``（物理像素）。可被任意线程调用。"""
        ...
