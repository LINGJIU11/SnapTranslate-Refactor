""""用户又动了一下输入设备"的监听端口。

用途：悬浮卡片不再定时自动关闭，而是**等用户下一次按任意键或鼠标左右键**再关。
要求是全局的（不限卡片窗口内），所以只能靠系统级键态查询，而不是 Tk 的事件绑定。

约定：``start()`` 时**已经按下的键被忽略**（例如触发热键的 Alt 还没松开），
只对之后新出现的按下动作回调；每次新的按下都会回调一次，直到 ``stop()``。
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

#: 回调在监听线程上触发，表示层负责切回 UI 线程
InputCallback = Callable[[], None]


@runtime_checkable
class InputWatcher(Protocol):
    def start(self, on_input: InputCallback) -> None:
        """开始监听（非阻塞）。"""
        ...

    def stop(self) -> None:
        """停止监听并释放线程。"""
        ...
