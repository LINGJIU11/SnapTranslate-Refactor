"""复习卡片的「自评」三按钮（原 ``vocab_review.py:457-498``）。

抽出来的原因：这段是纯布局 + 重复三次的按钮工厂，与卡片状态流转无关。
按钮文案来自 ``ReviewText``，配色来自 :mod:`snaptranslate.config.theme`。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from snaptranslate.config import theme
from snaptranslate.domain.models.review import Grade
from snaptranslate.presentation.texts import ReviewText

#: (档位, 文案, 常态底色, 按下底色)
_GRADE_BUTTONS: tuple[tuple[Grade, str, str, str], ...] = (
    (Grade.KNOW, ReviewText.GRADE_KNOW, theme.UI_GRADE_KNOW, theme.UI_GRADE_KNOW_HOVER),
    (Grade.VAGUE, ReviewText.GRADE_VAGUE, theme.UI_GRADE_VAGUE, theme.UI_GRADE_VAGUE_HOVER),
    (Grade.UNKNOWN, ReviewText.GRADE_UNKNOWN, theme.UI_GRADE_UNKNOWN, theme.UI_GRADE_UNKNOWN_HOVER),
)


def build_grade_row(parent: tk.Misc, on_grade: Callable[[Grade], None]) -> tk.Frame:
    """在 ``parent`` 里放"提示 + 三个自评按钮"，返回按钮所在的 Frame。"""
    frame = tk.Frame(parent, bg=theme.UI_CARD)
    frame.pack(fill="x")
    tk.Label(
        frame,
        text=ReviewText.GRADE_HINT,
        bg=theme.UI_CARD,
        fg=theme.UI_TEXT_MUTED,
        font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
    ).pack(anchor="w", pady=(0, 8))
    buttons = tk.Frame(frame, bg=theme.UI_CARD)
    buttons.pack(fill="x")
    button_kwargs = dict(
        relief="flat",
        font=tkfont.Font(family=theme.FONT_FAMILY, size=10, weight="bold"),
        cursor="hand2",
        pady=10,
    )
    for order, (grade, label, bg, active_bg) in enumerate(_GRADE_BUTTONS):
        # 原版逐个 pack(side="left", expand=True, fill="x", padx=(0, 6))，最后一个不带 padx
        padx: tuple[int, int] = (0, 6) if order < len(_GRADE_BUTTONS) - 1 else (0, 0)
        tk.Button(
            buttons,
            text=label,
            command=lambda g=grade: on_grade(g),
            bg=bg,
            fg="#FFFFFF",
            activebackground=active_bg,
            activeforeground="#FFFFFF",
            **button_kwargs,
        ).pack(side="left", expand=True, fill="x", padx=padx)
    return frame


__all__ = ["build_grade_row"]
