"""鼠标旁"光标状态条"浮窗。

职责：一个无边框 ``Toplevel``，在鼠标右下角显示一行状态文字，可跟随鼠标移动，
并在 ``duration_ms`` 到点后自动隐藏。对应原版：

- ``_show_cursor_status_near_cursor``  ``main.py:743-793``
- ``_start_cursor_status_follow``      ``main.py:795-827``（70ms 重定位）
- ``_hide_cursor_status``              ``main.py:829-847``
- ``_set_cursor_status_safe``          ``main.py:849-852``（切主线程 → 见 ``ui_kit.UiDispatcher``）

与原版一致的行为细节：
- 创建一次后复用，只改 Label 文案；
- 尺寸按 ``winfo_reqwidth/reqheight`` 自适应，并有 100×26 下限；
- 位置 = 光标 ``+14 / +18``，并夹取在屏幕内（``max(8, sw - w - 8)``）；
- 每次显示都会重启 follow 定时器，并在重设 ``duration_ms`` 之前先取消旧定时器；
- ``"鼠标旁悬浮提示"`` 复选框关闭时**完全不显示**（原版在入口处提前返回）。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from snaptranslate.config.theme import (
    UI_CURSOR_STATUS_BG,
    UI_CURSOR_STATUS_FG,
)
from snaptranslate.domain.services.text_cleaning import clean_text
from snaptranslate.presentation.tk.ui_kit import ui_font

#: 原 ``main.py:755`` / ``main.py:777-778`` / ``main.py:825``
CURSOR_STATUS_ALPHA = 0.92
FOLLOW_INTERVAL_MS = 70
MIN_WIDTH = 100
MIN_HEIGHT = 26
MARGIN = 8
OFFSET_X = 14
OFFSET_Y = 18
BORDER_COLOR = "#334155"


class CursorStatusWindow:
    """光标状态条控件。

    :param root: 主窗口（``Toplevel`` 的 parent）。
    :param cursor_position: 返回当前鼠标屏幕坐标 ``(x, y)``（注入，避免表示层直接调 Win32）。
    :param is_enabled: 返回"鼠标旁悬浮提示"是否勾选（读 Tk 变量）。
    """

    def __init__(
        self,
        root: tk.Tk,
        *,
        cursor_position: Callable[[], tuple[int, int]],
        is_enabled: Callable[[], bool],
    ) -> None:
        self._root = root
        self._cursor_position = cursor_position
        self._is_enabled = is_enabled
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._hide_timer_id: str | None = None
        self._follow_timer_id: str | None = None

    # —— 对外入口 ——

    def show_cursor_text(self, message: str, *, duration_ms: int | None = None) -> None:
        """原 ``_show_cursor_status_near_cursor``（本方法要求在主线程调用）。"""
        if not self._is_enabled():
            return
        text = clean_text(message)
        if not text:
            return

        window = self._ensure_window(text)
        window.update_idletasks()
        width = max(MIN_WIDTH, window.winfo_reqwidth())
        height = max(MIN_HEIGHT, window.winfo_reqheight())
        cursor_x, cursor_y = self._cursor_position()
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = min(max(MARGIN, cursor_x + OFFSET_X), max(MARGIN, screen_w - width - MARGIN))
        y = min(max(MARGIN, cursor_y + OFFSET_Y), max(MARGIN, screen_h - height - MARGIN))
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.deiconify()
        window.lift()

        if self._hide_timer_id is not None:
            window.after_cancel(self._hide_timer_id)
            self._hide_timer_id = None
        self._start_follow()
        if duration_ms is not None:
            self._hide_timer_id = window.after(duration_ms, self._hide)

    # —— 内部 ——

    def _ensure_window(self, text: str) -> tk.Toplevel:
        if self._window is None:
            top = tk.Toplevel(self._root)
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.attributes("-alpha", CURSOR_STATUS_ALPHA)
            top.configure(bg=UI_CURSOR_STATUS_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
            label = tk.Label(
                top,
                text=text,
                justify="left",
                anchor="w",
                bg=UI_CURSOR_STATUS_BG,
                fg=UI_CURSOR_STATUS_FG,
                padx=8,
                pady=5,
                font=ui_font(9, weight="bold"),
            )
            label.pack(fill="both", expand=True)
            self._window = top
            self._label = label
        elif self._label is not None:
            self._label.configure(text=text)
        return self._window

    def _start_follow(self) -> None:
        """原 ``_start_cursor_status_follow``：每 70ms 把浮窗贴到鼠标旁。"""
        window = self._window
        if window is None:
            return
        if self._follow_timer_id is not None:
            try:
                window.after_cancel(self._follow_timer_id)
            except Exception:
                pass
            self._follow_timer_id = None

        def tick() -> None:
            if self._window is None:
                self._follow_timer_id = None
                return
            if not self._window.winfo_viewable():
                self._follow_timer_id = None
                return
            try:
                self._window.update_idletasks()
                width = max(MIN_WIDTH, self._window.winfo_reqwidth())
                height = max(MIN_HEIGHT, self._window.winfo_reqheight())
                cursor_x, cursor_y = self._cursor_position()
                screen_w = self._root.winfo_screenwidth()
                screen_h = self._root.winfo_screenheight()
                x = min(max(MARGIN, cursor_x + OFFSET_X), max(MARGIN, screen_w - width - MARGIN))
                y = min(max(MARGIN, cursor_y + OFFSET_Y), max(MARGIN, screen_h - height - MARGIN))
                self._window.geometry(f"{width}x{height}+{x}+{y}")
            except Exception:
                self._follow_timer_id = None
                return
            self._follow_timer_id = self._window.after(FOLLOW_INTERVAL_MS, tick)

        self._follow_timer_id = window.after(FOLLOW_INTERVAL_MS, tick)

    def _hide(self) -> None:
        """原 ``_hide_cursor_status``：取消两个定时器后 ``withdraw``。"""
        window = self._window
        if window is None:
            return
        if self._follow_timer_id is not None:
            try:
                window.after_cancel(self._follow_timer_id)
            except Exception:
                pass
            self._follow_timer_id = None
        if self._hide_timer_id is not None:
            try:
                window.after_cancel(self._hide_timer_id)
            except Exception:
                pass
            self._hide_timer_id = None
        try:
            window.withdraw()
        except Exception:
            pass
