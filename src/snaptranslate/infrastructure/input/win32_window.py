"""Win32 窗口激活适配器（原 ``main.py:1208-1263``）。

在其它应用拥有焦点时，仅靠 Tk 的 ``focus_force`` 往往无效，
需要 ``AttachThreadInput`` 配合 ``SetForegroundWindow``。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

SW_RESTORE = 9


class Win32WindowActivator:
    """实现 :class:`~snaptranslate.domain.ports.window.WindowActivator`。"""

    def __init__(self, *, user32=None, kernel32=None) -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._kernel32 = kernel32 if kernel32 is not None else ctypes.windll.kernel32

    def foreground(self) -> int:
        """当前前台窗口句柄（取不到返回 0）。

        新增功能"中译英输入框"用它记住"用户按热键时正在用的那个窗口"，
        翻译返回后再把键盘焦点还回去——否则焦点会一直留在输入框里，把用户的按键吃掉。
        """
        try:
            return int(self._user32.GetForegroundWindow())
        except Exception:
            return 0

    def find_window(self, title: str) -> int:
        """按窗口标题（精确匹配）查句柄；找不到返回 0。

        新增功能"启动器"用它判断子窗口是否已开、以及把它唤到前台。
        """
        if not title:
            return 0
        try:
            return int(self._user32.FindWindowW(None, title))
        except Exception:
            return 0

    def force_foreground(self, hwnd: int) -> None:
        if hwnd <= 0:
            return
        user32 = self._user32
        kernel32 = self._kernel32
        target = wintypes.HWND(hwnd)
        try:
            user32.ShowWindow(target, SW_RESTORE)
        except Exception:
            pass
        foreground = user32.GetForegroundWindow()
        if not foreground:
            user32.SetForegroundWindow(target)
            user32.BringWindowToTop(target)
            return
        current_thread = kernel32.GetCurrentThreadId()
        process = wintypes.DWORD(0)
        foreground_thread = user32.GetWindowThreadProcessId(foreground, ctypes.byref(process))
        if foreground_thread == 0 or foreground_thread == current_thread:
            user32.SetForegroundWindow(target)
            user32.BringWindowToTop(target)
            return
        user32.AttachThreadInput(foreground_thread, current_thread, True)
        try:
            user32.SetForegroundWindow(target)
            user32.BringWindowToTop(target)
        finally:
            user32.AttachThreadInput(foreground_thread, current_thread, False)
