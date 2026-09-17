"""剪贴板读取适配器（``pyperclip`` + Win32 版本号）。"""

from __future__ import annotations

import ctypes

import pyperclip


class PyperclipClipboard:
    """实现 :class:`~snaptranslate.domain.ports.clipboard.Clipboard`。"""

    def __init__(self, *, user32=None) -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32

    def read_text(self) -> str:
        return pyperclip.paste()

    def sequence(self) -> int:
        """``GetClipboardSequenceNumber``：剪贴板内容每次被重新设置都会变化。

        取不到时返回 ``0``（调用方据此退回"比较内容"的旧判据）。
        """
        try:
            return int(self._user32.GetClipboardSequenceNumber())
        except Exception:
            return 0
