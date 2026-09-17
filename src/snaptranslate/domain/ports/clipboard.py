"""剪贴板端口。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clipboard(Protocol):
    def read_text(self) -> str:
        """读取剪贴板文本（失败返回空串，原版依赖 ``pyperclip`` 的异常行为）。"""
        ...
