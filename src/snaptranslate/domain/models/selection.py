"""取词结果值对象。

原版的取词（``main.py:949-964``）只返回一个字符串，**无法区分**"取到了选中文本"与
"Ctrl+C 没生效、读到的其实是剪贴板里的旧内容"——这正是"划词翻译返回了上次复制的网址"
这个 bug 的根源（见 KNOWN_ISSUES.md #20）。

重构后把"是否真的发生了一次复制"作为显式字段：
- ``copied=True`` + 非空 ``text``  → 正常取词；
- ``copied=True`` + 空 ``text``    → 复制到了空内容（如空白选区）；
- ``copied=False``                 → **取词失败**：剪贴板未发生变化，不得把旧内容当原文。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionCapture:
    """一次取词的结果。"""

    text: str
    copied: bool
    #: 取词失败时保留当时的剪贴板内容，仅用于日志/诊断，**绝不参与翻译**
    clipboard_text: str = ""

    @property
    def usable(self) -> bool:
        """是否可以拿去翻译。"""
        return self.copied and bool(self.text)
