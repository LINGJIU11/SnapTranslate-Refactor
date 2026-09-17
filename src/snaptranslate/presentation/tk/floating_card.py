"""鼠标旁"翻译结果悬浮卡片"。

职责：一个 500×140 的无边框深色 ``Toplevel``，内容为 ``f"{原文}\\n=> {译文}"``，
位置=光标 ``+16/+16`` 并夹在屏内，``duration_ms`` 到点后 ``withdraw``；卡片内带一个
"收录生词本"按钮，其回调由外部注入。对应原版：``_show_floating_near_cursor``
（``main.py:669-741``）。

**行为等价要点（原版缺陷，见 KNOWN_ISSUES.md #2）**：卡片只保留最近一次传入的
``原始文本 + 译文``，而"收录生词本"按钮收录的是这一刻卡片上的文本——调用方在显示翻译
结果时会传 ``TranslationResult.display_text``（**带引擎标签**），因此从悬浮卡片收录进
生词本的 ``meaning`` 是带"（Google 最快返回）"的 display 文本；而主界面"最近 3 条"
的收录按钮走的是干净译文。这里原样保留。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from snaptranslate.config.theme import UI_FLOAT_BG
from snaptranslate.presentation.texts import WindowText
from snaptranslate.presentation.tk.ui_kit import FLOAT_BORDER_COLOR, floating_label, small_button

#: 原 ``main.py:684`` / ``main.py:729``
FLOATING_ALPHA = 0.97
POPUP_WIDTH = 500
POPUP_HEIGHT = 140
#: 原 ``main.py:699``
WRAP_LENGTH = 460
#: 原 ``main.py:733``：位置 = 光标 +16，并夹在屏内
OFFSET = 16
MARGIN = 10
#: 原 ``main.py:669`` 默认 2200ms；错误提示用 2800ms、收录反馈用 2000ms
DEFAULT_DURATION_MS = 2200


class FloatingCard:
    """悬浮卡片控件。

    :param root: 主窗口。
    :param cursor_position: 返回鼠标屏幕坐标 ``(x, y)``（注入）。
    :param is_enabled: 返回"鼠标旁悬浮提示"是否勾选（读 Tk 变量）。
    :param on_collect: "收录生词本"按钮回调（原 ``_on_floating_save_click``）。
    """

    def __init__(
        self,
        root: tk.Tk,
        *,
        cursor_position: Callable[[], tuple[int, int]],
        is_enabled: Callable[[], bool],
        on_collect: Callable[[], None],
    ) -> None:
        self._root = root
        self._cursor_position = cursor_position
        self._is_enabled = is_enabled
        self._on_collect = on_collect
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._button: tk.Button | None = None
        self._timer_id: str | None = None
        #: 原 ``_floating_original`` / ``_floating_translated``：卡片当前承载的文本
        self.original = ""
        self.translated = ""

    def show(self, original: str, translated: str, *, duration_ms: int = DEFAULT_DURATION_MS) -> None:
        """原 ``_show_floating_near_cursor``（本方法要求在主线程调用）。"""
        if not self._is_enabled():
            return

        message = f"{original}\n=> {translated}"
        self.original = original
        self.translated = translated

        if self._window is None:
            self._build(message)
        elif self._label is not None:
            self._label.configure(text=message)

        window = self._window
        if window is None:
            return
        cursor_x, cursor_y = self._cursor_position()
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = min(max(MARGIN, cursor_x + OFFSET), max(MARGIN, screen_w - POPUP_WIDTH - MARGIN))
        y = min(max(MARGIN, cursor_y + OFFSET), max(MARGIN, screen_h - POPUP_HEIGHT - MARGIN))
        window.geometry(f"{POPUP_WIDTH}x{POPUP_HEIGHT}+{x}+{y}")
        window.deiconify()
        window.lift()

        if self._timer_id is not None:
            window.after_cancel(self._timer_id)
        self._timer_id = window.after(duration_ms, window.withdraw)

    # —— 内部 ——

    def _build(self, message: str) -> None:
        top = tk.Toplevel(self._root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", FLOATING_ALPHA)
        top.configure(bg=UI_FLOAT_BG, highlightbackground=FLOAT_BORDER_COLOR, highlightthickness=1)

        body = tk.Frame(top, bg=UI_FLOAT_BG, padx=14, pady=12)
        body.pack(fill="both", expand=True)

        label = floating_label(body, message, wraplength=WRAP_LENGTH, bg=UI_FLOAT_BG)
        # Label 的 pady 在部分 Tcl 下不支持 (a, b) 元组，间距交给 pack（原版注释）
        label.pack(fill="both", expand=True, pady=(0, 10))

        button = small_button(body, command=self._on_collect, text=WindowText.FLOATING_COLLECT_BUTTON)
        button.pack(anchor="e")

        self._window = top
        self._label = label
        self._button = button
