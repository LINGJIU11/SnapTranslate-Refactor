"""复习窗口「设置区」（原 ``vocab_review.py:219-360`` 的构建代码）。

只管把控件按原顺序建好并 pack 出来；选择变化后要做什么由
:class:`~snaptranslate.presentation.tk.review_window.ReviewApp` 通过回调决定。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from snaptranslate.config import theme
from snaptranslate.presentation.texts import ReviewText


class SettingsForm:
    """词表路径 + 顺序单选 + 朗读单选 + 音量滑块 + 手动重读。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        vocab_path: str,
        sort_mode_var: tk.StringVar,
        read_mode_var: tk.StringVar,
        volume_var: tk.IntVar,
        on_sort_change: Callable[[], None],
        on_browse: Callable[[], None],
        on_repeat: Callable[[], None],
    ) -> None:
        self.volume_var = volume_var
        frame = tk.Frame(
            parent,
            bg=theme.UI_CARD,
            highlightbackground=theme.UI_BORDER,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        frame.pack(fill="x", pady=(0, 10))

        path_row = tk.Frame(frame, bg=theme.UI_CARD)
        path_row.pack(fill="x", pady=(0, 8))
        tk.Label(
            path_row,
            text=ReviewText.VOCAB_LABEL,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
        ).pack(anchor="w")
        path_inner = tk.Frame(path_row, bg=theme.UI_CARD)
        path_inner.pack(fill="x", pady=(4, 0))
        self.path_label = tk.Label(
            path_inner,
            text=vocab_path,
            bg=theme.UI_LOG_BG,
            fg=theme.UI_ACCENT,
            cursor="hand2",
            font=tkfont.Font(family=theme.FONT_FAMILY_MONO, size=9),
            anchor="w",
            padx=10,
            pady=8,
            highlightbackground=theme.UI_BORDER,
            highlightthickness=1,
        )
        self.path_label.pack(side="left", fill="x", expand=True)
        self.path_label.bind("<Button-1>", lambda _event: on_browse())
        self.browse_button = tk.Button(
            path_inner,
            text=ReviewText.BROWSE,
            command=on_browse,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
            bg=theme.UI_ACCENT,
            fg="#ffffff",
            activebackground=theme.UI_ACCENT_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        )
        self.browse_button.pack(side="right", padx=(8, 0))

        sort_row = tk.Frame(frame, bg=theme.UI_CARD)
        sort_row.pack(fill="x", pady=(4, 4))
        tk.Label(
            sort_row,
            text=ReviewText.SORT_LABEL,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
        ).pack(anchor="w")
        sort_btns = tk.Frame(frame, bg=theme.UI_CARD)
        sort_btns.pack(fill="x", pady=(4, 0))
        radio_kwargs = dict(
            bg=theme.UI_CARD,
            activebackground=theme.UI_CARD,
            fg=theme.UI_TEXT,
            selectcolor=theme.UI_CHIP,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
        )
        for label, value in ReviewText.SORT_MODES:
            tk.Radiobutton(
                sort_btns,
                text=label,
                variable=sort_mode_var,
                value=value,
                command=on_sort_change,
                **radio_kwargs,
            ).pack(side="left", padx=(0, 14))

        read_row = tk.Frame(frame, bg=theme.UI_CARD)
        read_row.pack(fill="x", pady=(8, 0))
        tk.Label(
            read_row,
            text=ReviewText.READ_LABEL,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
        ).pack(anchor="w")
        read_btns = tk.Frame(frame, bg=theme.UI_CARD)
        read_btns.pack(fill="x", pady=(4, 0))
        for label, value in ReviewText.READ_MODES:
            tk.Radiobutton(
                read_btns,
                text=label,
                variable=read_mode_var,
                value=value,
                **radio_kwargs,
            ).pack(side="left", padx=(0, 14))

        tts_row = tk.Frame(frame, bg=theme.UI_CARD)
        tts_row.pack(fill="x", pady=(10, 0))
        tk.Label(
            tts_row,
            text=ReviewText.TTS_VOLUME_LABEL,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
        ).pack(anchor="w")
        tk.Scale(
            tts_row,
            from_=0,
            to=100,
            orient="horizontal",
            variable=volume_var,
            resolution=1,
            showvalue=True,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT,
            troughcolor=theme.UI_LOG_BG,
            highlightthickness=0,
            length=260,
        ).pack(anchor="w", pady=(4, 0))
        tk.Button(
            tts_row,
            text=ReviewText.MANUAL_REPEAT,
            command=on_repeat,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
            bg=theme.UI_CARD,
            fg=theme.UI_ACCENT,
            activebackground=theme.UI_CHIP,
            activeforeground=theme.UI_ACCENT_HOVER,
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(anchor="w", pady=(6, 0))


__all__ = ["SettingsForm"]
