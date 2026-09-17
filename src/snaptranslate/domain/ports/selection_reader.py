"""取词端口：把"当前选中的文本"取出来。

原版做法是模拟 Ctrl+C 再读剪贴板（``main.py:949-964``），Windows 专属；
端口化之后，未来换 UIAutomation/剪贴板增强实现时应用层无需改动。

**注意**：返回值是 :class:`SelectionCapture` 而不是裸字符串——调用方必须能区分
"没取到词"与"读到了剪贴板里的旧内容"。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from snaptranslate.domain.models.selection import SelectionCapture


@runtime_checkable
class SelectionReader(Protocol):
    def read_selected_text(self) -> SelectionCapture:
        """取词。失败（Ctrl+C 未生效）时返回 ``copied=False``，绝不返回剪贴板旧内容当结果。"""
        ...
