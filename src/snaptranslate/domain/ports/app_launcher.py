"""子应用监管端口（启动器用）。

启动器负责四件事：**看状态 / 打开（或唤起）/ 关闭 / 重启**。
把这套动作抽成端口，表示层就完全不认识 ``subprocess`` 与 Win32。

状态刻意分成 5 种（第一版只有"运行中/未运行"两态，于是"进程刚起来、窗口还没画出来"
也被显示成"运行中"，用户以为已经开好了却点不动；"隐藏到托盘"同样被误判为运行中
——见 KNOWN_ISSUES.md §七 N5）：

=================  ==========================================================
``stopped``        没有任何进程/窗口
``starting``       我们刚把它拉起来，窗口还没出现（**不等于运行中**）
``running``        有**可见**窗口，正常可用
``hidden``         窗口存在但不可见（例如隐藏到托盘）——打开时应先显示出来
``stuck``          进程活着却迟迟没有窗口（或窗口不见了）——允许"关闭/重启"
=================  ==========================================================
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class AppState(str, Enum):
    """子应用的运行状态（字符串枚举，便于直接显示与测试）。"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    HIDDEN = "hidden"
    STUCK = "stuck"

    @property
    def label(self) -> str:
        return {
            "stopped": "未运行",
            "starting": "启动中…",
            "running": "运行中",
            "hidden": "已隐藏",
            "stuck": "无响应",
        }[self.value]


@runtime_checkable
class AppLauncher(Protocol):
    def state(self, key: str) -> AppState:
        """当前状态（见 :class:`AppState`）。"""
        ...

    def open_or_focus(self, key: str) -> bool:
        """已运行则显示并唤到前台，没运行则启动它。

        :return: 是否**确认**已经有一个可见窗口（``False`` = 没打开成功，
            调用方应当把这件事如实告诉用户，而不是假装成功）。
        """
        ...

    def close(self, key: str) -> bool:
        """结束该子应用（我们拉起的用进程句柄，否则按窗口标题找到进程结束）。"""
        ...

    def restart(self, key: str) -> bool:
        """先关闭再启动（卡住时的出口）。"""
        ...

    def running_keys(self) -> tuple[str, ...]:
        """当前**有可见窗口**的子应用键名。"""
        ...

    def terminate_all(self) -> None:
        """结束由本启动器拉起的全部子进程（点"退出"时调用）。"""
        ...
