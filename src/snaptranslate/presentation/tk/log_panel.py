"""复习窗口「生成按钮 + 状态栏 + 日志区」（原 ``vocab_review.py:500-548`` 的构建代码）。

对应原版的 ``actions`` / ``log_fr`` / ``stat_bar`` / ``log_text`` 四块控件。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext
from typing import Callable

from snaptranslate.config import theme
from snaptranslate.presentation.texts import ReviewText


class LogPanel:
    """批量生成按钮、状态栏与滚动日志。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        status_var: tk.StringVar,
        gen_label: str,
        on_generate: Callable[[], None],
    ) -> None:
        actions = tk.Frame(parent, bg=theme.UI_BG)
        actions.pack(fill="x", pady=(0, 8))

        self.gen_button = tk.Button(
            actions,
            text=gen_label,
            command=on_generate,
            bg=theme.UI_ACCENT,
            fg="#FFFFFF",
            activebackground=theme.UI_ACCENT_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            padx=14,
            pady=12,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=10, weight="bold"),
            cursor="hand2",
        )
        self.gen_button.pack(fill="x")

        log_fr = tk.Frame(parent, bg=theme.UI_BG)
        log_fr.pack(fill="both", expand=True, pady=(0, 6))
        stat_bar = tk.Frame(log_fr, bg=theme.UI_STATUS_BG, padx=10, pady=8)
        stat_bar.pack(fill="x", pady=(0, 8))
        tk.Label(
            stat_bar,
            textvariable=status_var,
            bg=theme.UI_STATUS_BG,
            fg=theme.UI_TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
            anchor="w",
        ).pack(fill="x")

        self.log_text = scrolledtext.ScrolledText(
            log_fr,
            height=6,
            wrap="word",
            state="disabled",
            font=tkfont.Font(family=theme.FONT_FAMILY_MONO, size=9),
            bg=theme.UI_LOG_BG,
            fg=theme.UI_TEXT,
            insertbackground=theme.UI_TEXT,
            relief="flat",
            bd=0,
            padx=10,
            pady=10,
            highlightthickness=0,
        )
        self.log_text.pack(fill="both", expand=True)

    def write(self, line: str) -> None:
        """原 ``_log``：临时解禁 → 追加 → 滚到底 → 重新禁用。"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def post_from_worker(self, root: tk.Misc, line: str) -> None:
        """工作线程里的日志：按原版做法 ``after(0, ...)`` 丢回主线程再写。"""
        root.after(0, lambda: self.write(line))

    def set_gen_label(self, text: str) -> None:
        self.gen_button.configure(text=text)


def build_header(parent: tk.Misc) -> None:
    """原 ``vocab_review.py:202-217``：大标题 + 副标题。"""
    header = tk.Frame(parent, bg=theme.UI_BG)
    header.pack(fill="x", pady=(0, 12))
    tk.Label(
        header,
        text=ReviewText.HEADING,
        font=tkfont.Font(family=theme.FONT_FAMILY, size=20, weight="bold"),
        bg=theme.UI_BG,
        fg=theme.UI_TEXT,
    ).pack(anchor="w")
    tk.Label(
        header,
        text=ReviewText.SUBTITLE,
        font=tkfont.Font(family=theme.FONT_FAMILY, size=10),
        bg=theme.UI_BG,
        fg=theme.UI_TEXT_MUTED,
    ).pack(anchor="w", pady=(4, 0))


__all__ = ["LogPanel", "build_header", "log_startup"]
