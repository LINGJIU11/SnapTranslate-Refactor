"""单实例守卫：Win32 命名互斥量（``CreateMutexW``）。

``CreateMutexW`` 返回句柄；若 ``GetLastError() == ERROR_ALREADY_EXISTS``，
说明已经有进程占着这个名字——这正是"第二个实例"的判定方式。
"""

from __future__ import annotations

import ctypes

ERROR_ALREADY_EXISTS = 183
#: 互斥量名字统一加前缀，避免和别的软件撞名
NAME_PREFIX = r"Local\SnapTranslate."


class Win32SingleInstance:
    """实现 :class:`~snaptranslate.domain.ports.single_instance.SingleInstanceGuard`。"""

    def __init__(self, *, kernel32=None) -> None:
        self._kernel32 = kernel32 if kernel32 is not None else ctypes.windll.kernel32
        self._handle = 0
        self._name = ""

    @property
    def name(self) -> str:
        return self._name

    def acquire(self, name: str) -> bool:
        if self._handle:
            return True
        full_name = NAME_PREFIX + name
        try:
            self._kernel32.SetLastError(0)
            handle = self._kernel32.CreateMutexW(None, False, full_name)
        except Exception:  # pragma: no cover - 非 Windows
            return True
        if not handle:
            # 拿不到句柄时**不要**挡住用户：宁可允许启动，也不要"点了没反应"
            return True
        already = self._kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        self._handle = int(handle)
        self._name = full_name
        if already:
            # 名字已被占用：立刻关掉自己这份句柄，避免影响真正持有者
            self.release()
            return False
        return True

    def release(self) -> None:
        if not self._handle:
            return
        try:
            self._kernel32.CloseHandle(self._handle)
        except Exception:
            pass
        self._handle = 0


__all__ = ["ERROR_ALREADY_EXISTS", "NAME_PREFIX", "Win32SingleInstance"]
