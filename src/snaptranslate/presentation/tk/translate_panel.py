"""主窗口"控制卡片"的布局构建。

职责：纯布局，不含业务逻辑。对应原版 ``_build_ui`` 中从 ``ctrl_card`` 到状态栏的那一大段
（``main.py:1585-1843``）。文案一律取自
:class:`~snaptranslate.presentation.texts.WindowText`，控件参数块取自 ``ui_kit``。

调用方（``translate_window.TranslateApp``）实现 :class:`translate_ui.PanelHost` 提供的
变量与回调（``on_enable_toggle`` / ``on_apply_hotkeys`` / ``on_recent_save_click`` /
``on_delete_saved`` / ``clear_log``）。构建顺序与原版逐个控件一一对应，
保证 Tab 焦点顺序与视觉层级一致。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from snaptranslate.config.theme import (
    UI_BORDER,
    UI_CARD,
    UI_CHIP,
    UI_LOG_BG,
    UI_STATUS_BG,
    UI_TEXT,
    UI_TEXT_MUTED,
)
from snaptranslate.presentation.texts import WindowText
from snaptranslate.presentation.tk.translate_ui import PanelHost
from snaptranslate.presentation.tk.ui_kit import (
    CHECK_KW,
    HOTKEY_ENTRY_KW,
    SECTION_LABEL_KW,
    card_frame,
    danger_button,
    ghost_button,
    primary_button,
    ui_font,
)

#: 原 ``main.py:1660``：翻译源说明的换行宽度
SOURCE_HINT_WRAP = 520
#: 原 ``main.py:1730``：音量滑块长度
TTS_SCALE_LENGTH = 260
#: 原 ``main.py:1744`` / ``main.py:1784``：最近列表行间距
RECENT_ROW_PADY = (6, 4)


def build_control_panel(host: PanelHost, master: tk.Misc) -> tk.Frame:
    """构建控制卡片并返回它（内部 ``pack`` 到 ``master``）。"""
    card = card_frame(master, padx=16, pady=14)
    card.pack(fill="x", pady=(0, 12))
    _build_switches(host, card)
    _build_source(host, card)
    _build_proxy(host, card)
    _build_hotkeys(host, card)
    _build_tts_volume(host, card)
    _build_recent_translations(host, card)
    _build_recent_saved(host, card)
    _build_actions(host, card)
    _build_status(host, card)
    return card


# ———————————————————————————— 分块构建 ————————————————————————————


def _build_proxy(host: PanelHost, card: tk.Frame) -> None:
    """网络代理设置（本轮新增，见 KNOWN_ISSUES.md #25）。

    ``requests`` 不读 Windows 系统代理，所以"开着 Clash 也用不上"；这里把代理做进请求层：
    三种模式（直连 / 跟随系统 / 自定义）+ 两个常用预设提示 + 一个自检按钮。
    """
    wrap = tk.Frame(card, bg=UI_CARD)
    wrap.pack(fill="x", pady=(14, 0))
    tk.Label(wrap, text=WindowText.PROXY_LABEL, **SECTION_LABEL_KW).pack(anchor="w")

    row = tk.Frame(wrap, bg=UI_CARD)
    row.pack(fill="x", pady=(6, 0))
    rb_kw = dict(
        bg=UI_CARD,
        activebackground=UI_CARD,
        fg=UI_TEXT,
        selectcolor=UI_CHIP,
        font=ui_font(10),
    )
    for text, value in (
        (WindowText.PROXY_MODE_OFF, "off"),
        (WindowText.PROXY_MODE_SYSTEM, "system"),
        (WindowText.PROXY_MODE_CUSTOM, "custom"),
    ):
        tk.Radiobutton(row, text=text, variable=host.proxy_mode_var, value=value, **rb_kw).pack(
            side="left", padx=(0, 14)
        )

    edit_row = tk.Frame(wrap, bg=UI_CARD)
    edit_row.pack(fill="x", pady=(6, 0))
    tk.Entry(edit_row, textvariable=host.proxy_url_var, **HOTKEY_ENTRY_KW).pack(
        side="left", fill="x", expand=True
    )
    ghost_button(edit_row, text=WindowText.PROXY_APPLY, command=host.on_apply_proxy).pack(
        side="left", padx=(8, 0)
    )
    ghost_button(edit_row, text=WindowText.PROXY_TEST, command=host.on_test_proxy).pack(
        side="left", padx=(6, 0)
    )

    tk.Label(
        wrap,
        text=WindowText.PROXY_HINT,
        bg=UI_CARD,
        fg=UI_TEXT_MUTED,
        font=ui_font(8),
        wraplength=SOURCE_HINT_WRAP,
        justify="left",
    ).pack(anchor="w", pady=(6, 0))


def _build_switches(host: PanelHost, card: tk.Frame) -> None:
    """两个复选框：启用划词翻译 / 鼠标旁悬浮提示（原 ``main.py:1595-1619``）。"""
    row = tk.Frame(card, bg=UI_CARD)
    row.pack(fill="x")
    tk.Checkbutton(
        row,
        text=WindowText.ENABLE_CHECKBOX,
        variable=host.enable_var,
        command=host.on_enable_toggle,
        font=ui_font(10),
        **CHECK_KW,
    ).pack(side="left")
    tk.Checkbutton(
        row,
        text=WindowText.FLOATING_CHECKBOX,
        variable=host.floating_var,
        font=ui_font(10),
        **CHECK_KW,
    ).pack(side="left", padx=(20, 0))


def _build_source(host: PanelHost, card: tk.Frame) -> None:
    """翻译源单选：MyMemory 在前、自动竞速在后（原 ``main.py:1621-1662``，顺序不可改）。"""
    wrap = tk.Frame(card, bg=UI_CARD)
    wrap.pack(fill="x", pady=(14, 0))
    tk.Label(wrap, text=WindowText.SOURCE_LABEL, font=ui_font(9), **SECTION_LABEL_KW).pack(anchor="w")
    row = tk.Frame(wrap, bg=UI_CARD)
    row.pack(fill="x", pady=(6, 0))
    for text, value, padx in (
        (WindowText.SOURCE_MYMEMORY, "mymemory", (0, 18)),
        (WindowText.SOURCE_AUTO_RACE, "google", (0, 0)),
    ):
        tk.Radiobutton(
            row,
            text=text,
            variable=host.translate_source_var,
            value=value,
            font=ui_font(10),
            **CHECK_KW,
        ).pack(side="left", padx=padx)
    tk.Label(
        wrap,
        text=WindowText.SOURCE_HINT,
        font=ui_font(8),
        wraplength=SOURCE_HINT_WRAP,
        justify="left",
        **SECTION_LABEL_KW,
    ).pack(anchor="w", pady=(6, 0))


#: 热键字段键名 → ``PanelHost`` 上的 Tk 变量名（``save_last`` 的变量名与原版一致，不带 ``_last``）
HOTKEY_VAR_NAMES: dict[str, str] = {
    "translate": "hotkey_translate_var",
    "snip": "hotkey_snip_var",
    "save_last": "hotkey_save_var",
    "input": "hotkey_input_var",
}


def _build_hotkeys(host: PanelHost, card: tk.Frame) -> None:
    """热键输入框（原版三组 + 新增的"中译英"一组）+ "应用并保存"（原 ``main.py:1664-1706``）。

    字段表来自 ``WindowText.HOTKEY_FIELDS``，因此以后再加一组只需改文案表与端口声明。
    """
    wrap = tk.Frame(card, bg=UI_CARD)
    wrap.pack(fill="x", pady=(12, 0))
    tk.Label(wrap, text=WindowText.HOTKEY_LABEL, font=ui_font(9), **SECTION_LABEL_KW).pack(anchor="w")
    row = tk.Frame(wrap, bg=UI_CARD)
    row.pack(fill="x", pady=(5, 0))
    for label, key in WindowText.HOTKEY_FIELDS:
        variable = getattr(host, HOTKEY_VAR_NAMES[key])
        tk.Label(row, text=label, font=ui_font(9), **SECTION_LABEL_KW).pack(side="left")
        tk.Entry(row, textvariable=variable, font=ui_font(9, mono=True), **HOTKEY_ENTRY_KW).pack(
            side="left", padx=(4, 10)
        )
    ghost_button(
        row, command=host.on_apply_hotkeys, text=WindowText.HOTKEY_APPLY, borderwidth=1, padx=8, pady=3
    ).pack(side="left")


def _build_tts_volume(host: PanelHost, card: tk.Frame) -> None:
    """英文朗读音量滑块（原 ``main.py:1708-1731``）。"""
    wrap = tk.Frame(card, bg=UI_CARD)
    wrap.pack(fill="x", pady=(12, 0))
    tk.Label(wrap, text=WindowText.TTS_VOLUME_LABEL, font=ui_font(9), **SECTION_LABEL_KW).pack(anchor="w")
    tk.Scale(
        wrap,
        from_=0,
        to=100,
        orient="horizontal",
        variable=host.tts_volume_var,
        resolution=1,
        showvalue=True,
        bg=UI_CARD,
        fg=UI_TEXT,
        troughcolor=UI_LOG_BG,
        highlightthickness=0,
        length=TTS_SCALE_LENGTH,
    ).pack(anchor="w", pady=(4, 0))


def _recent_row(master: tk.Misc, variable: tk.StringVar, *, first: bool) -> tk.Frame:
    """一条"最近记录"行：左侧只读文本 + 右侧操作按钮（原版两处循环体）。"""
    row = tk.Frame(master, bg=UI_CARD)
    row.pack(fill="x", pady=(RECENT_ROW_PADY[0] if first else RECENT_ROW_PADY[1], 0))
    tk.Label(
        row,
        textvariable=variable,
        bg=UI_LOG_BG,
        fg=UI_TEXT,
        anchor="w",
        justify="left",
        padx=10,
        pady=7,
        font=ui_font(9),
        highlightbackground=UI_BORDER,
        highlightthickness=1,
    ).pack(side="left", fill="x", expand=True)
    return row


def _build_recent_translations(host: PanelHost, card: tk.Frame) -> None:
    """最近 3 条翻译 + "收录"按钮（原 ``main.py:1733-1771``）。"""
    wrap = tk.Frame(card, bg=UI_CARD)
    wrap.pack(fill="x", pady=(12, 0))
    tk.Label(wrap, text=WindowText.RECENT_TRANSLATIONS_LABEL, font=ui_font(9), **SECTION_LABEL_KW).pack(anchor="w")
    for index in range(3):
        row = _recent_row(wrap, host.recent_vars[index], first=index == 0)
        primary_button(row, command=_make_callback(host.on_recent_save_click, index), text=WindowText.COLLECT_BUTTON).pack(
            side="left", padx=(8, 0)
        )


def _build_recent_saved(host: PanelHost, card: tk.Frame) -> None:
    """最近加入生词本 5 条 + "删除"按钮（原 ``main.py:1773-1811``）。"""
    wrap = tk.Frame(card, bg=UI_CARD)
    wrap.pack(fill="x", pady=(12, 0))
    tk.Label(wrap, text=WindowText.RECENT_SAVED_LABEL, font=ui_font(9), **SECTION_LABEL_KW).pack(anchor="w")
    for index in range(5):
        row = _recent_row(wrap, host.recent_saved_vars[index], first=index == 0)
        danger_button(row, command=_make_callback(host.on_delete_saved, index), text=WindowText.DELETE_BUTTON).pack(
            side="left", padx=(8, 0)
        )


def _build_actions(host: PanelHost, card: tk.Frame) -> None:
    """清空记录按钮（原 ``main.py:1813-1831``）。"""
    row = tk.Frame(card, bg=UI_CARD)
    row.pack(fill="x", pady=(12, 0))
    ghost_button(row, command=host.clear_log, text=WindowText.CLEAR_LOG, padx=14, pady=6).pack(side="left")


def _build_status(host: PanelHost, card: tk.Frame) -> None:
    """底部状态栏（原 ``main.py:1833-1843``）。"""
    wrap = tk.Frame(card, bg=UI_STATUS_BG, padx=12, pady=10)
    wrap.pack(fill="x", pady=(14, 0))
    tk.Label(
        wrap,
        textvariable=host.status_var,
        bg=UI_STATUS_BG,
        fg=UI_TEXT_MUTED,
        font=ui_font(9),
        anchor="w",
        justify="left",
    ).pack(fill="x")


# ———————————————————————————— 头部与日志区 ————————————————————————————
# （``build_header`` / ``build_log_card`` 与 Tk 变量创建一起放在 ``translate_shell``）


def _make_callback(callback: Callable[[int], None], index: int) -> Callable[[], None]:
    """把 ``lambda n=i: cb(n)`` 的闭包捕获写法显式化（原版用默认参数捕获 ``i``）。"""
    return lambda: callback(index)


#: 未使用（保留说明）：原版热键校验失败的文案用的是**内部键名**而非界面标签，
#: 因此不需要"键名 → 中文标签"映射，见 ``hotkey_controls.HotkeyManager.validate``。
