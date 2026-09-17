"""划词窗口的界面契约（Protocol 集合，无实现、无 Tk 调用）。

``translate_panel``（控制卡片）与 ``translate_shell``（窗口壳）都面向这些协议编程，
主窗口 ``translate_window.TranslateApp`` 负责实现：

- :class:`PanelHost` —— 控制卡片需要读写的 Tk 变量与按钮回调；
- :class:`ShellHost` —— 窗口壳额外需要的（热键提示变量、日志控件、最近列表变量、宿主钩子）。

放在单独模块是为了避免 ``translate_panel`` ↔ ``translate_shell`` 互相 import。
"""

from __future__ import annotations

import tkinter as tk
from typing import Protocol


class PanelHost(Protocol):
    """``build_control_panel`` 需要的窗口状态与回调。"""

    enable_var: tk.BooleanVar
    floating_var: tk.BooleanVar
    translate_source_var: tk.StringVar
    tts_volume_var: tk.IntVar
    hotkey_translate_var: tk.StringVar
    hotkey_snip_var: tk.StringVar
    hotkey_save_var: tk.StringVar
    status_var: tk.StringVar
    recent_vars: list[tk.StringVar]
    recent_saved_vars: list[tk.StringVar]

    def on_enable_toggle(self) -> None: ...

    def on_apply_hotkeys(self) -> None: ...

    def on_recent_save_click(self, index: int) -> None: ...

    def on_delete_saved(self, index: int) -> None: ...

    def clear_log(self) -> None: ...


class ShellHost(PanelHost, Protocol):
    """``build_translate_window`` 需要的宿主。"""

    hotkey_hint_var: tk.StringVar
    hotkeys: dict[str, str]

    def tts_volume_default(self) -> int: ...


__all__ = ["PanelHost", "ShellHost"]
