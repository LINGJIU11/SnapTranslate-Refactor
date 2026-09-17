"""主窗口的"窗口壳"：Tk 变量创建 + 控件装配顺序。

职责：对应原版 ``_build_ui``（``main.py:1537-1600`` 与 ``1845-1883``）中最机械的那部分——
在 ``tk.Tk()`` 之后创建全部 ``StringVar/BooleanVar/IntVar``、设置标题与几何、按原版顺序
拼出"头部 → 控制卡片 → 日志区"。控制卡片内部布局在 ``translate_panel``。

顺序与原版逐行对应，因此 Tab 焦点顺序、控件层级与初始文案都与原版一致。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext

from snaptranslate.config.theme import (
    LOG_TAG_ORIG,
    LOG_TAG_TRANS,
    UI_CARD,
    UI_LOG_BG,
    UI_TEXT,
    UI_TEXT_MUTED,
)
from snaptranslate.presentation.texts import WindowText
from snaptranslate.presentation.tk.translate_panel import build_control_panel
from snaptranslate.presentation.tk.translate_ui import ShellHost
from snaptranslate.presentation.tk.ui_kit import (
    WINDOW_BG,
    WINDOW_GEOMETRY,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    card_frame,
    ui_font,
)

#: 原 ``main.py:1550`` / ``main.py:1551``
RECENT_TRANSLATION_ROWS = 3
RECENT_SAVED_ROWS = 5


def build_translate_window(host: ShellHost, root: tk.Tk) -> scrolledtext.ScrolledText:
    """创建全部 Tk 变量与控件，返回翻译记录文本框。

    与原版一样，**变量必须在 ``root`` 存在之后创建**（否则 ``Too early to create variable``）。
    """
    _create_variables(host, root)
    root.title(WindowText.TITLE)
    root.geometry(WINDOW_GEOMETRY)
    root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
    root.configure(bg=WINDOW_BG)

    outer = tk.Frame(root, bg=WINDOW_BG, padx=18, pady=16)
    outer.pack(fill="both", expand=True)
    build_header(outer, host.hotkey_hint_var)
    build_control_panel(host, outer)
    return build_log_card(outer)


def _create_variables(host: ShellHost, root: tk.Tk) -> None:
    """原 ``main.py:1540-1551``。"""
    host.status_var = tk.StringVar(master=root, value=WindowText.READY)
    host.enable_var = tk.BooleanVar(master=root, value=True)
    host.floating_var = tk.BooleanVar(master=root, value=True)
    host.translate_source_var = tk.StringVar(master=root, value="google")
    host.tts_volume_var = tk.IntVar(master=root, value=host.tts_volume_default())
    host.hotkey_translate_var = tk.StringVar(master=root, value=host.hotkeys["translate"])
    host.hotkey_snip_var = tk.StringVar(master=root, value=host.hotkeys["snip"])
    host.hotkey_save_var = tk.StringVar(master=root, value=host.hotkeys["save_last"])
    host.hotkey_hint_var = tk.StringVar(master=root, value="")
    host.recent_vars = [
        tk.StringVar(master=root, value=WindowText.EMPTY_RECENT) for _ in range(RECENT_TRANSLATION_ROWS)
    ]
    host.recent_saved_vars = [
        tk.StringVar(master=root, value=WindowText.EMPTY_RECENT) for _ in range(RECENT_SAVED_ROWS)
    ]


# ———————————————————————————— 头部与日志区 ————————————————————————————


def build_header(master: tk.Misc, hint_var: tk.StringVar) -> tk.Frame:
    """标题 / 副标题 / 热键提示行（原 ``main.py:1561-1583``）。"""
    header = tk.Frame(master, bg=WINDOW_BG)
    header.pack(fill="x", pady=(0, 14))
    tk.Label(
        header, text=WindowText.TITLE, font=ui_font(20, weight="bold"), bg=WINDOW_BG, fg=UI_TEXT
    ).pack(anchor="w")
    tk.Label(header, text=WindowText.SUBTITLE, font=ui_font(10), bg=WINDOW_BG, fg=UI_TEXT_MUTED).pack(
        anchor="w", pady=(4, 0)
    )
    tk.Label(header, textvariable=hint_var, font=ui_font(9), bg=WINDOW_BG, fg=UI_TEXT_MUTED).pack(
        anchor="w", pady=(2, 0)
    )
    return header


def build_log_card(master: tk.Misc) -> scrolledtext.ScrolledText:
    """翻译记录区（原 ``main.py:1845-1879``），返回已配置好 tag 的文本框。"""
    card = card_frame(master, padx=14, pady=14)
    card.pack(fill="both", expand=True)
    tk.Label(card, text=WindowText.LOG_TITLE, font=ui_font(11, weight="bold"), bg=UI_CARD, fg=UI_TEXT).pack(
        anchor="w", pady=(0, 10)
    )
    log_text = scrolledtext.ScrolledText(
        card,
        wrap="word",
        state="disabled",
        font=ui_font(10),
        bg=UI_LOG_BG,
        fg=UI_TEXT,
        insertbackground=UI_TEXT,
        relief="flat",
        bd=0,
        padx=12,
        pady=12,
        highlightthickness=0,
    )
    log_text.pack(fill="both", expand=True)
    log_text.tag_configure("orig", foreground=LOG_TAG_ORIG)
    log_text.tag_configure("trans", foreground=LOG_TAG_TRANS)
    return log_text
