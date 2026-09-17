"""翻译结果悬浮卡片（原 ``_show_floating_near_cursor``，``main.py:669-741``）。

与原版的差异（都是用户明确要求的改动，见 KNOWN_ISSUES.md #23 / #24）：

1. **锚点 = 热键按下瞬间的鼠标位置**（``anchor``），而不是"翻译返回时鼠标在哪"。
   原版是在结果回来后才读光标，于是"选中单词后手一动、卡片就飘到别处"。
2. **不再定时自动关闭**：卡片一直显示，直到用户**下一次按任意键或鼠标左/右键**才消失
   （全局判定，不限于卡片窗口内；点在卡片上——例如"收录生词本"按钮——不算关闭信号）。

保留的原版行为（见 KNOWN_ISSUES.md #6）：卡片承载的是调用方传入的文本，
翻译结果那一路传的是带引擎标签的 ``display_text``。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from snaptranslate.config.theme import UI_FLOAT_BG
from snaptranslate.domain.ports.input_watcher import InputWatcher
from snaptranslate.domain.ports.pointer import Pointer
from snaptranslate.presentation.texts import WindowText
from snaptranslate.presentation.tk.overlay_geometry import Bounds, place_near
from snaptranslate.presentation.tk.overlay_geometry import is_inside  # noqa: F401  (对外沿用旧导入路径)
from snaptranslate.presentation.tk.ui_kit import FLOAT_BORDER_COLOR, floating_label, small_button

#: 原 ``main.py:684`` / ``main.py:729``
FLOATING_ALPHA = 0.97
POPUP_WIDTH = 500
POPUP_HEIGHT = 140
#: 原 ``main.py:699``
WRAP_LENGTH = 460
#: 原 ``main.py:733``：位置 = 锚点 +16，并夹在屏内（几何计算见 ``overlay_geometry``）
OFFSET = 16
MARGIN = 10


class FloatingCard:
    """悬浮卡片控件。

    :param root: 主窗口。
    :param pointer: 取鼠标屏幕坐标（Win32，线程安全）。
    :param is_enabled: 返回"鼠标旁悬浮提示"是否勾选（读 Tk 变量）。
    :param on_collect: "收录生词本"按钮回调（原 ``_on_floating_save_click``）。
    :param input_watcher: 监听"任意键 / 鼠标左右键"，用于关闭卡片。
    :param marshal: 把回调切回主线程（``root.after(0, ...)``）。
    """

    def __init__(
        self,
        root: tk.Tk,
        *,
        pointer: Pointer,
        is_enabled: Callable[[], bool],
        on_collect: Callable[[], None],
        input_watcher: InputWatcher,
        marshal: Callable[[Callable[[], None]], None],
    ) -> None:
        self._root = root
        self._pointer = pointer
        self._is_enabled = is_enabled
        self._on_collect = on_collect
        self._input_watcher = input_watcher
        self._marshal = marshal
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._button: tk.Button | None = None
        #: 当前卡片的屏幕矩形（主线程写、监听线程读，只做整体替换，天然安全）
        self._bounds: Bounds | None = None
        #: 原 ``_floating_original`` / ``_floating_translated``：卡片当前承载的文本
        self.original = ""
        self.translated = ""

    # ———————————————————————————— 对外 ————————————————————————————

    def show(
        self,
        original: str,
        translated: str,
        *,
        anchor: tuple[int, int] | None = None,
    ) -> None:
        """显示卡片（要求主线程调用）。

        :param anchor: 锚点坐标（一般是**热键按下瞬间**的鼠标位置）；为 ``None`` 时退回当前鼠标位置。
        """
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

        point = anchor if anchor is not None else self._pointer.position()
        x, y = self._place(point)
        window.geometry(f"{POPUP_WIDTH}x{POPUP_HEIGHT}+{x}+{y}")
        window.deiconify()
        window.lift()
        self._arm_dismiss_watcher()

    def hide(self) -> None:
        """关闭卡片（要求主线程调用）；同时停掉输入监听。"""
        self._input_watcher.stop()
        window = self._window
        if window is None:
            return
        try:
            window.withdraw()
        except tk.TclError:
            pass

    def shutdown(self) -> None:
        """程序退出时清理：停掉监听线程，不再碰 Tk。"""
        self._input_watcher.stop()

    def current_anchor(self) -> tuple[int, int] | None:
        """卡片当前左上角（用于"收录"反馈就地显示）。"""
        if self._bounds is None:
            return None
        return (self._bounds[0], self._bounds[1])

    def is_visible(self) -> bool:
        return self._bounds is not None and self._window is not None and bool(self._window.winfo_viewable())

    # ———————————————————————————— 内部 ————————————————————————————

    def _place(self, point: tuple[int, int]) -> tuple[int, int]:
        """按锚点算出卡片左上角：``+16`` 偏移并夹在屏内（原 ``main.py:733-734``）。"""
        x, y, bounds = place_near(
            point,
            (POPUP_WIDTH, POPUP_HEIGHT),
            (self._root.winfo_screenwidth(), self._root.winfo_screenheight()),
            offset=OFFSET,
            margin=MARGIN,
        )
        self._bounds = bounds
        return x, y

    def _arm_dismiss_watcher(self) -> None:
        self._input_watcher.stop()
        self._input_watcher.start(self._on_any_input)

    def _on_any_input(self) -> None:
        """输入监听线程的回调：用户在卡片**之外**按键/点鼠标 → 关闭卡片。"""
        if self._pointer_inside_card():
            return
        self._marshal(self.hide)

    def _pointer_inside_card(self) -> bool:
        bounds = self._bounds
        if bounds is None:
            return False
        return is_inside(bounds, self._pointer.position())

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


__all__ = ["FloatingCard", "Bounds", "is_inside", "FLOATING_ALPHA", "OFFSET", "POPUP_HEIGHT", "POPUP_WIDTH"]
