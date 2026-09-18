"""子应用监管端口（启动器用）。

启动器自己不是翻译器/复习器，它只做三件事：**判断某个子窗口开没开 / 打开它 / 把它唤到前台**。
把这套动作抽成端口，表示层就完全不认识 ``subprocess`` 与 Win32。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AppLauncher(Protocol):
    def is_running(self, key: str) -> bool:
        """该子应用是否已经在运行（有窗口，或进程刚起来还没画完）。"""
        ...

    def open_or_focus(self, key: str) -> None:
        """已运行则唤到前台，没运行则启动它（启动后再唤一次，省得用户以为没反应）。"""
        ...

    def running_keys(self) -> tuple[str, ...]:
        """当前在运行的子应用键名（面板用它刷新"运行中/未运行"）。"""
        ...

    def terminate_all(self) -> None:
        """结束由本启动器拉起的全部子进程（点"退出"时调用）。"""
        ...
