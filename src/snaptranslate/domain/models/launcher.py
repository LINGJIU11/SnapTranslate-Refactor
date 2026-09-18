"""启动器要管理的"子应用"描述（纯值对象）。

为什么放在 **domain** 而不是 application：这份清单要同时被三层使用——
``bootstrap`` 填值（窗口标题取自 ``presentation/texts.py``）、``presentation`` 显示、
``infrastructure`` 照单启动/唤起。而基础设施层**不允许** import application
（``scripts/check_layering.py`` 会当场拦下），所以共享的值对象放 domain 最合适。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LauncherAppItem:
    """一个可被启动/唤起的子应用。"""

    #: 内部键名（托盘菜单 id、子进程参数都用它）
    key: str
    #: 面板按钮上的文字
    label: str
    #: 一句话说明
    hint: str
    #: 传给子进程的参数，例如 ``--app=translate``
    arg: str
    #: 该窗口的标题（用于"是否已开"判定与唤起，必须与窗口真实标题一字不差）
    window_title: str


__all__ = ["LauncherAppItem"]
