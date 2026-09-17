"""剪贴板端口。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clipboard(Protocol):
    def read_text(self) -> str:
        """读取剪贴板文本（失败返回空串，原版依赖 ``pyperclip`` 的异常行为）。"""
        ...

    def sequence(self) -> int:
        """剪贴板**版本号**：内容每次被重新设置都会变化。

        用于可靠判断"模拟 Ctrl+C 是否真的复制到了东西"——只看内容是否变化是不够的
        （内容可能恰好与旧值相同）。实现不支持时返回 ``0``，调用方应退回内容比对。
        """
        ...
