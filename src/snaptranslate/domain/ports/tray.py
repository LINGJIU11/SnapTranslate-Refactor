"""托盘图标端口（"常驻任务栏"的那个小图标）。

启动器面板需要一个"随时唤起其它窗口"的常驻入口，本端口把这件事与 Win32 解耦：
表示层只说"给我一个带菜单的托盘图标"，具体用 ``Shell_NotifyIcon`` 还是别的实现由基础设施决定。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class TrayMenuItem:
    """一个托盘菜单项。"""

    id: str
    label: str
    #: 左侧是否显示勾选标记
    checked: bool = False
    #: 是否在它之前插一条分隔线
    separator_before: bool = False
    enabled: bool = True


@runtime_checkable
class TrayIcon(Protocol):
    def start(
        self,
        tooltip: str,
        icon_path: str,
        items: Sequence[TrayMenuItem],
        on_select: Callable[[str], None],
    ) -> bool:
        """注册托盘图标并启动它自己的消息循环线程。

        :return: 是否注册成功。**失败不是错误**——没有托盘时面板窗口仍然可用，
            调用方据此决定"关闭窗口 = 退出"还是"缩小到托盘"。
        """
        ...

    def update(self, items: Sequence[TrayMenuItem]) -> None:
        """更新菜单项（勾选状态/可用性变化时调用）。"""
        ...

    def notify(self, title: str, message: str) -> None:
        """气泡提示（注册失败时静默忽略）。"""
        ...

    def stop(self) -> None:
        """移除图标并结束消息循环线程。"""
        ...
