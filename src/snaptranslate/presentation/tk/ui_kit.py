"""Tk 通用控件工厂 + UI 线程调度。

职责
----
1. **控件工厂**：原版把 ``tkfont.Font(family=FONT_FAMILY, size=...)`` 与按钮/输入框的参数块
   在 ``main.py:690-731、1577-1583、1598-1612、1675-1706、1745-1811、1863-1879``
   复制了十几遍；这里收敛成函数 + 字典常量，颜色全部取自 :mod:`snaptranslate.config.theme`。
2. **UI 线程调度**：工作线程绝不允许直接碰 Tk（原版靠 ``root.after(0, ...)`` 到处手写，
   见 ``main.py:592-600、849-852``）；这里统一封装成 :class:`UiDispatcher`。

对应原版：``main.py:328-348``（主题常量）、``main.py:592-600``（``_set_status_safe``）。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Callable, Protocol

from snaptranslate.application.progress import Stage
from snaptranslate.config.theme import (
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    UI_ACCENT,
    UI_ACCENT_HOVER,
    UI_BG,
    UI_BORDER,
    UI_CARD,
    UI_CHIP,
    UI_DANGER_BG,
    UI_DANGER_BG_HOVER,
    UI_DANGER_FG,
    UI_DANGER_FG_HOVER,
    UI_FLOAT_BG,
    UI_FLOAT_BTN,
    UI_FLOAT_BTN_HOVER,
    UI_FLOAT_FG,
    UI_LOG_BG,
    UI_TEXT,
    UI_TEXT_MUTED,
)
from snaptranslate.presentation.texts import StatusText

#: 主窗口底色（导出给窗口构建函数，避免各处再 import theme）
WINDOW_BG = UI_BG
WHITE = "#ffffff"

#: 主窗口几何（原 ``main.py:1554-1555``）
WINDOW_GEOMETRY = "760x740"
WINDOW_MIN_WIDTH = 620
WINDOW_MIN_HEIGHT = 520

#: 浮层边框色（原 ``main.py:685`` / ``main.py:756``）
FLOAT_BORDER_COLOR = "#334155"

# ———————————————————————————— 字体工厂 ————————————————————————————


def ui_font(size: int, *, weight: str = "normal", mono: bool = False) -> tkfont.Font:
    """``tkfont.Font(family=..., size=...)``（原版每个控件各建一个 Font 实例）。

    保留"每次调用返回新 Font"这一原版行为：Font 是有名字的 Tcl 资源，
    共享实例会改变其销毁时机。
    """
    return tkfont.Font(family=FONT_FAMILY_MONO if mono else FONT_FAMILY, size=size, weight=weight)


# ———————————————————————————— 参数块常量 ————————————————————————————

#: 卡片外框（原版 ``ctrl_card`` / ``log_card`` 的边框参数）
CARD_FRAME_KW: dict[str, Any] = {"bg": UI_CARD, "highlightbackground": UI_BORDER, "highlightthickness": 1}

#: 复选 / 单选按钮公共参数（原版 ``chk_kw`` / ``rb_kw``）
CHECK_KW: dict[str, Any] = {
    "bg": UI_CARD,
    "fg": UI_TEXT,
    "activebackground": UI_CARD,
    "activeforeground": UI_TEXT,
    "selectcolor": UI_CHIP,
}

#: 热键输入框公共参数（原版 ``hk_ent_kw``）
HOTKEY_ENTRY_KW: dict[str, Any] = {
    "bg": UI_LOG_BG,
    "fg": UI_TEXT,
    "insertbackground": UI_TEXT,
    "relief": "solid",
    "borderwidth": 1,
    "highlightthickness": 0,
    "width": 10,
}

#: 卡片内的小号灰色标签（原版十几处 ``fg=UI_TEXT_MUTED``）
SECTION_LABEL_KW: dict[str, Any] = {"bg": UI_CARD, "fg": UI_TEXT_MUTED}


# ———————————————————————————— 控件工厂 ————————————————————————————


def card_frame(master: tk.Misc, **kwargs: Any) -> tk.Frame:
    """白底描边卡片 Frame（原版 ``tk.Frame(..., **CARD_FRAME_KW)``）。"""
    options = dict(CARD_FRAME_KW)
    options.update(kwargs)
    return tk.Frame(master, **options)


def primary_button(master: tk.Misc, *, command: Callable[[], None], **kwargs: Any) -> tk.Button:
    """实心主按钮（原版"收录"：``UI_ACCENT`` 底 + 白字 + flat）。"""
    options: dict[str, Any] = {
        "command": command,
        "font": ui_font(9, weight="bold"),
        "bg": UI_ACCENT,
        "fg": WHITE,
        "activebackground": UI_ACCENT_HOVER,
        "activeforeground": WHITE,
        "relief": "flat",
        "padx": 10,
        "pady": 6,
        "cursor": "hand2",
    }
    options.update(kwargs)
    return tk.Button(master, **options)


def ghost_button(master: tk.Misc, *, command: Callable[[], None], **kwargs: Any) -> tk.Button:
    """描边幽灵按钮（原版"应用并保存"/"清空记录"：白底 + 主题色字 + solid 边框）。"""
    options: dict[str, Any] = {
        "command": command,
        "font": ui_font(9),
        "bg": UI_CARD,
        "fg": UI_ACCENT,
        "activebackground": UI_CHIP,
        "activeforeground": UI_ACCENT_HOVER,
        "relief": "solid",
        "borderwidth": 1,
        "highlightthickness": 0,
        "padx": 8,
        "pady": 3,
        "cursor": "hand2",
    }
    options.update(kwargs)
    return tk.Button(master, **options)


def danger_button(master: tk.Misc, *, command: Callable[[], None], **kwargs: Any) -> tk.Button:
    """浅红危险按钮（原版"删除"：``UI_DANGER_*`` 四色）。"""
    options: dict[str, Any] = {
        "command": command,
        "font": ui_font(9, weight="bold"),
        "bg": UI_DANGER_BG,
        "fg": UI_DANGER_FG,
        "activebackground": UI_DANGER_BG_HOVER,
        "activeforeground": UI_DANGER_FG_HOVER,
        "relief": "flat",
        "padx": 10,
        "pady": 6,
        "cursor": "hand2",
    }
    options.update(kwargs)
    return tk.Button(master, **options)


def small_button(master: tk.Misc, *, command: Callable[[], None], **kwargs: Any) -> tk.Button:
    """深色浮层上的小号按钮（原版悬浮卡片"收录生词本"）。"""
    options: dict[str, Any] = {
        "command": command,
        "relief": "flat",
        "bd": 0,
        "padx": 14,
        "pady": 6,
        "bg": UI_FLOAT_BTN,
        "fg": WHITE,
        "activebackground": UI_FLOAT_BTN_HOVER,
        "activeforeground": WHITE,
        "font": ui_font(9, weight="bold"),
        "cursor": "hand2",
    }
    options.update(kwargs)
    return tk.Button(master, **options)


def floating_label(master: tk.Misc, text: str, **kwargs: Any) -> tk.Label:
    """深色浮层正文 Label（原版 ``_show_floating_near_cursor`` 里的 ``lbl`` 与光标状态条 ``lbl``）。"""
    options: dict[str, Any] = {
        "text": text,
        "justify": "left",
        "anchor": "w",
        "padx": 0,
        "pady": 0,
        "bg": UI_FLOAT_BG,
        "fg": UI_FLOAT_FG,
        "font": ui_font(10),
    }
    options.update(kwargs)
    return tk.Label(master, **options)


# ———————————————————————————— UI 线程调度 ————————————————————————————


class UiDispatcher:
    """把"工作线程 → 主线程"的切换收口（原版到处手写 ``root.after(0, fn)``）。

    :param root: ``tk.Tk`` 主窗口。
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._status_var: tk.StringVar | None = None

    @property
    def root(self) -> tk.Tk:
        return self._root

    def bind_status_var(self, status_var: tk.StringVar) -> None:
        """``_build_ui()`` 创建 ``status_var`` 之后接上（原版是直接读 ``self.status_var``）。"""
        self._status_var = status_var

    def post(self, fn: Callable[[], None]) -> None:
        """把 ``fn`` 排到主线程空闲时执行（原 ``_set_status_safe`` 的 ``after(0, apply)``）。"""
        self._root.after(0, fn)

    def set_status(self, message: str) -> None:
        """线程安全地设置状态栏（原版多处 ``status_var.set``）。"""
        var = self._status_var
        if var is None:
            return
        self.post(lambda: var.set(message))

    def after(self, delay_ms: int, fn: Callable[[], None]) -> str:
        return self._root.after(delay_ms, fn)


class StatusBridge:
    """阶段 → 文案 的唯一落点（原版把这段逻辑散在 ``main.py:969-974、1074-1079`` 等处）。

    对应 :meth:`StatusText.texts` 的三元组：``(状态栏文案, 光标文案, 自动隐藏毫秒)``。
    **状态栏文案为 ``None`` 时不改动状态栏**，与原版不调用 ``_set_status_safe`` 的写法一致。
    """

    def __init__(self, dispatcher: UiDispatcher, cursor: "CursorTextSink") -> None:
        self._dispatcher = dispatcher
        self._cursor = cursor

    def status(self, stage: Stage) -> None:
        self._apply(stage, with_status=True)

    def cursor(self, stage: Stage) -> None:
        self._apply(stage, with_status=False)

    def _apply(self, stage: Stage, *, with_status: bool) -> None:
        status_text, cursor_text, duration = StatusText.texts(stage)
        if with_status and status_text is not None:
            self._dispatcher.set_status(status_text)
        self._cursor.show_cursor_text(cursor_text, duration_ms=duration)

    def report(self, stage: Stage) -> None:
        """状态栏与光标提示条一起刷新（原版 OCR 分支会同时设置两者）。"""
        status_text, cursor_text, duration = StatusText.texts(stage)
        if status_text is not None:
            self._dispatcher.set_status(status_text)
        self._cursor.show_cursor_text(cursor_text, duration_ms=duration)


class CursorTextSink(Protocol):
    """``StatusBridge`` 需要的光标提示出口（由 :class:`CursorStatusWindow` 实现）。"""

    def show_cursor_text(self, message: str, *, duration_ms: int | None = None) -> None:
        ...

