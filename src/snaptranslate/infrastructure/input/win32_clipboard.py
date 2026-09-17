"""剪贴板读取适配器（``pyperclip``）。"""

from __future__ import annotations

import pyperclip


class PyperclipClipboard:
    """实现 :class:`~snaptranslate.domain.ports.clipboard.Clipboard`。"""

    def read_text(self) -> str:
        return pyperclip.paste()
