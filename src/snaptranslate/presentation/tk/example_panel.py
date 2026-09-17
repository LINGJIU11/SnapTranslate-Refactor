"""复习卡片「例句面板」渲染（原 ``vocab_review.py`` 的 ``_clear_example_display`` /
``_insert_text_with_keyword_bold`` / ``_render_example_display`` 三个方法，734-784 行）。

从复习窗口里拆出来，是为了让"例句面板怎么画"与"卡片状态怎么流转"各自成立：
本模块只依赖 ``tkinter``、领域值对象与文案表，不碰用例与网络。
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont

from snaptranslate.config import theme
from snaptranslate.domain.models.vocab_entry import VocabEntry
from snaptranslate.domain.services.review_session import RevealState
from snaptranslate.presentation.texts import ReviewText


def create_panel(parent: tk.Misc) -> tk.Text:
    """按原版 ``vocab_review.py:428-451`` 建例句面板（自带三个 tag 与两个字体）。"""
    font_example = tkfont.Font(family=theme.FONT_FAMILY, size=11)
    font_example_bold = tkfont.Font(family=theme.FONT_FAMILY, size=11, weight="bold")
    wrap = tk.Frame(
        parent,
        bg=theme.UI_EXAMPLE_PANEL,
        highlightbackground=theme.UI_BORDER,
        highlightthickness=1,
    )
    wrap.pack(fill="x", pady=(0, 4))
    text = tk.Text(
        wrap,
        height=6,
        width=58,
        wrap="word",
        state="disabled",
        bg=theme.UI_EXAMPLE_PANEL,
        fg=theme.UI_KEYWORD,
        insertbackground=theme.UI_KEYWORD,
        relief="flat",
        padx=10,
        pady=10,
        cursor="arrow",
        font=font_example,
        highlightthickness=0,
    )
    text.tag_configure("keyword", font=font_example_bold, foreground=theme.UI_KEYWORD)
    text.tag_configure("zh_line", foreground=theme.UI_ZH)
    text.tag_configure("muted", foreground=theme.UI_TEXT_MUTED)
    text.pack(fill="x")
    return text


def insert_text_with_keyword_bold(
    widget: tk.Text,
    body: str,
    keyword: str,
    tag: str = "keyword",
) -> None:
    """写入 ``body``，把其中与 ``keyword`` **大小写不敏感**相等的片段打上 ``tag``。

    逐行等价于原 ``_insert_text_with_keyword_bold``：同样的
    ``re.split(f"({re.escape(keyword)})", body, flags=re.IGNORECASE)``、
    同样的 ``re.error`` 兜底、同样跳过空片段。
    """
    keyword = (keyword or "").strip()
    body = body or ""
    if not keyword:
        widget.insert("end", body)
        return
    pattern = re.escape(keyword)
    try:
        parts = re.split(f"({pattern})", body, flags=re.IGNORECASE)
    except re.error:
        widget.insert("end", body)
        return
    kw_lower = keyword.lower()
    for part in parts:
        if not part:
            continue
        if part.lower() == kw_lower:
            widget.insert("end", part, (tag,))
        else:
            widget.insert("end", part)


def clear_panel(widget: tk.Text) -> None:
    """原 ``_clear_example_display``：临时解禁 → 清空 → 重新禁用。"""
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.configure(state="disabled")


def render_panel(widget: tk.Text, entry: VocabEntry | None, reveal: RevealState) -> None:
    """原 ``_render_example_display``：只依据会话的揭示状态决定画什么。"""
    word_kw = "" if entry is None else entry.word.strip()
    example_trimmed = "" if entry is None else str(entry.example or "").strip()
    example_zh_trimmed = "" if entry is None else str(entry.example_zh or "").strip()

    widget.configure(state="normal")
    widget.delete("1.0", "end")
    if not reveal.show_example:
        widget.configure(state="disabled")
        return
    if not example_trimmed and not example_zh_trimmed:
        # 行为等价：原版此处用 "例句：（暂无）"（EXAMPLE_EN_PREFIX 是 "例句（英）："）
        widget.insert("end", ReviewText.EXAMPLE_EMPTY, ("muted",))
    else:
        widget.insert("end", ReviewText.EXAMPLE_EN_PREFIX)
        if example_trimmed:
            insert_text_with_keyword_bold(widget, example_trimmed, word_kw)
        else:
            widget.insert("end", ReviewText.EXAMPLE_MISSING, ("muted",))
        if reveal.show_example_zh:
            widget.insert("end", "\n" + ReviewText.EXAMPLE_ZH_PREFIX, ("zh_line",))
            widget.insert("end", example_zh_trimmed or ReviewText.EXAMPLE_MISSING, ("zh_line",))
    widget.configure(state="disabled")


__all__ = [
    "clear_panel",
    "create_panel",
    "insert_text_with_keyword_bold",
    "render_panel",
]
