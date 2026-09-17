"""复习窗口「卡片区」（原 ``vocab_review.py:362-498`` 的构建代码）。

进度 / 得分 / 词条大字 / 三个揭示按钮 / 释义标签 / 例句面板 / 自评三按钮。
只负责搭建；状态由会话驱动，见
:class:`~snaptranslate.presentation.tk.review_window.ReviewApp` 的 ``_show_card`` 等。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

from snaptranslate.config import theme
from snaptranslate.domain.models.review import Grade
from snaptranslate.domain.models.vocab_entry import VocabEntry
from snaptranslate.domain.services.review_session import RevealState
from snaptranslate.presentation.texts import ReviewText
from snaptranslate.presentation.tk import example_panel
from snaptranslate.presentation.tk.grade_buttons import build_grade_row


class CardForm:
    """一张复习卡片的全部控件。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        progress_var: tk.StringVar,
        score_var: tk.StringVar,
        word_var: tk.StringVar,
        meaning_var: tk.StringVar,
        on_toggle_meaning: Callable[[], None],
        on_toggle_example: Callable[[], None],
        on_toggle_example_zh: Callable[[], None],
        on_grade: Callable[[Grade], None],
    ) -> None:
        card = tk.Frame(
            parent,
            bg=theme.UI_CARD,
            highlightbackground=theme.UI_BORDER,
            highlightthickness=1,
            padx=18,
            pady=16,
        )
        card.pack(fill="both", expand=True, pady=(0, 10))

        card_hdr = tk.Frame(card, bg=theme.UI_CARD)
        card_hdr.pack(fill="x")
        tk.Label(
            card_hdr,
            textvariable=progress_var,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9),
        ).pack(side="left")
        tk.Label(
            card_hdr,
            textvariable=score_var,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=9, weight="bold"),
        ).pack(side="right")

        tk.Label(
            card,
            textvariable=word_var,
            bg=theme.UI_CARD,
            fg=theme.UI_TEXT,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=20, weight="bold"),
            wraplength=520,
            justify="center",
        ).pack(pady=(8, 12))

        reveal_row = tk.Frame(card, bg=theme.UI_CARD)
        reveal_row.pack(fill="x", pady=(0, 8))
        reveal_kwargs = dict(
            font=tkfont.Font(family=theme.FONT_FAMILY, size=10),
            bg=theme.UI_CHIP,
            fg=theme.UI_ACCENT,
            activebackground=theme.UI_ACCENT,
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
        )
        self.meaning_button = tk.Button(
            reveal_row,
            text=ReviewText.SHOW_MEANING,
            command=on_toggle_meaning,
            **reveal_kwargs,
        )
        self.meaning_button.pack(side="left")
        self.example_button = tk.Button(
            reveal_row,
            text=ReviewText.SHOW_EXAMPLE,
            command=on_toggle_example,
            **reveal_kwargs,
        )
        self.example_button.pack(side="left", padx=(8, 0))
        # 例句翻译按钮**不**在这里 pack：未显示例句时原版保持隐藏（见 _refresh_reveal_ui）
        self.example_zh_button = tk.Button(
            reveal_row,
            text=ReviewText.SHOW_EXAMPLE_ZH,
            command=on_toggle_example_zh,
            **reveal_kwargs,
        )

        tk.Label(
            card,
            textvariable=meaning_var,
            bg=theme.UI_CARD,
            fg=theme.UI_MEANING,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=12),
            wraplength=520,
            justify="center",
        ).pack(pady=(0, 8))

        self.example_text = example_panel.create_panel(card)

        sep = tk.Frame(card, bg=theme.UI_BORDER, height=1)
        sep.pack(fill="x", pady=(14, 10))

        build_grade_row(card, on_grade)

    def refresh_reveal_ui(self, show_example: bool) -> None:
        """原 ``_refresh_reveal_ui``：例句翻译按钮仅在例句已显示时才 pack。"""
        if show_example:
            self.example_zh_button.pack(side="left", padx=(8, 0))
        else:
            self.example_zh_button.pack_forget()

    def clear_example(self) -> None:
        """原 ``_clear_example_display``。"""
        example_panel.clear_panel(self.example_text)

    def render_example(self, entry: VocabEntry | None, reveal: RevealState) -> None:
        """原 ``_render_example_display``：按揭示状态重画例句面板。"""
        example_panel.render_panel(self.example_text, entry, reveal)


__all__ = ["CardForm"]
