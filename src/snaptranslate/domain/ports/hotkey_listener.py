"""全局热键监听端口。

原版有**两套并存**的机制（这一行为被原样保留，见 KNOWN_ISSUES.md #1）：

1. ``RegisterHotKey`` + 消息循环，硬编码 ``Ctrl+L``（``main.py:1505-1528``）；
2. 8ms 轮询 ``GetAsyncKeyState``，支持 ``ctrl/shift/alt/tab`` 组合（``main.py:1410-1455``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from snaptranslate.domain.models.hotkey import Hotkey


@dataclass(frozen=True)
class HotkeyBindings:
    """三组快捷键（原 ``main_settings.json`` 的 ``hotkeys`` 字段）。"""

    translate: Hotkey
    snip: Hotkey
    save_last: Hotkey


@dataclass(frozen=True)
class HotkeyCallbacks:
    """回调在监听线程上触发，表示层负责切回 UI 线程（Tk 用 ``root.after``）。"""

    on_translate: Callable[[], None]
    on_snip: Callable[[], None]
    on_save_last: Callable[[], None]
    on_error: Callable[[str], None] | None = None


@runtime_checkable
class HotkeyListener(Protocol):
    def start(self, bindings: HotkeyBindings, callbacks: HotkeyCallbacks) -> None:
        """启动监听（非阻塞）。"""
        ...

    def update_bindings(self, bindings: HotkeyBindings) -> None:
        """更新监听中的组合，**无需重启程序**。

        原版 ``_tab_combo_loop`` 每轮都重新读取窗口上的热键字符串，因此"界面改热键 →
        立即生效"；监听器必须提供等价能力，否则用户改完热键会以为程序坏了。
        """
        ...

    def stop(self) -> None:
        """停止监听并释放系统资源。"""
        ...
