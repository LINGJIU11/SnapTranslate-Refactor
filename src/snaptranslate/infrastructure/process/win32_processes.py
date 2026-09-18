"""Win32 进程控制适配器：按窗口标题结束那个进程。

为什么需要它：启动器能"打开"子窗口，也必须能**结束**它——否则一旦子窗口卡住、或者
它是上一次会话留下的（甚至窗口已隐藏），用户就没有任何出口了（"关不掉"的实际体验）。

优先用我们自己记住的子进程句柄（``Popen.terminate()``）；句柄不在手上时
（例如用户是从快捷方式直接启动的），就按窗口标题找到窗口 → 取 PID → ``TerminateProcess``。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

PROCESS_TERMINATE = 0x0001


class Win32ProcessController:
    """实现 :class:`~snaptranslate.domain.ports.process_control.ProcessController`。"""

    def __init__(self, *, user32=None, kernel32=None) -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._kernel32 = kernel32 if kernel32 is not None else ctypes.windll.kernel32

    def pid_of_window(self, hwnd: int) -> int:
        """窗口所属进程 ID（失败返回 0）。"""
        if hwnd <= 0:
            return 0
        pid = wintypes.DWORD(0)
        try:
            self._user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
        except Exception:
            return 0
        return int(pid.value)

    def terminate_pid(self, pid: int) -> bool:
        """结束指定进程（返回是否成功）。"""
        if pid <= 0:
            return False
        handle = 0
        try:
            handle = self._kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if not handle:
                return False
            return bool(self._kernel32.TerminateProcess(handle, 0))
        except Exception:
            return False
        finally:
            if handle:
                try:
                    self._kernel32.CloseHandle(handle)
                except Exception:
                    pass

    def is_pid_alive(self, pid: int) -> bool:
        """进程是否还活着（用 ``GetExitCodeProcess`` 判 ``STILL_ACTIVE``）。"""
        if pid <= 0:
            return False
        handle = 0
        try:
            handle = self._kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            code = wintypes.DWORD(0)
            if not self._kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        except Exception:
            return False
        finally:
            if handle:
                try:
                    self._kernel32.CloseHandle(handle)
                except Exception:
                    pass


__all__ = ["PROCESS_TERMINATE", "Win32ProcessController"]
