"""指针位置适配器（``GetCursorPos``，原 ``main.py:617-620``）。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes


class Win32Pointer:
    """实现 :class:`~snaptranslate.domain.ports.pointer.Pointer`。"""

    def __init__(self, *, user32=None) -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32

    def position(self) -> tuple[int, int]:
        point = wintypes.POINT()
        try:
            if not self._user32.GetCursorPos(ctypes.byref(point)):
                return (0, 0)
        except Exception:
            return (0, 0)
        return (int(point.x), int(point.y))
