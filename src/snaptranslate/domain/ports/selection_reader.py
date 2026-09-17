"""取词端口：把"当前选中的文本"取出来。

原版做法是模拟 Ctrl+C 再读剪贴板（``main.py:949-964``），Windows 专属；
端口化之后，未来换 UIAutomation/剪贴板增强实现时应用层无需改动。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SelectionReader(Protocol):
    def read_selected_text(self) -> str:
        """返回清洗后的选中文本；取词失败返回空串。"""
        ...
