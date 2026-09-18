"""进程控制端口（启动器的"关闭/重启"用到）。

只做两件事：**某个窗口属于哪个进程**、**结束那个进程**。
把 Win32 细节挡在基础设施层后面，表示层只说"结束这一路"。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProcessController(Protocol):
    def pid_of_window(self, hwnd: int) -> int:
        """窗口所属进程 ID（取不到返回 0）。"""
        ...

    def terminate_pid(self, pid: int) -> bool:
        """结束指定进程；返回是否成功。"""
        ...

    def is_pid_alive(self, pid: int) -> bool:
        """进程是否还在运行。"""
        ...
