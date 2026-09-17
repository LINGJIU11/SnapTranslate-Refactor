"""划词窗口的"翻译记录"文本框与"最近 3 条翻译"展示态。

职责：

- :class:`TranscriptPanel` —— 原 ``_append_log``（``main.py:659-667``）与 ``_clear_log``（``1530-1535``）；
- :class:`RecentList` —— 原 ``_push_recent_translation``（``875-881``）与 ``_refresh_recent_ui``（``883-891``）
  在窗口上维护的那份"最近 3 条"状态（**存的是干净译文**，与悬浮卡片不同）。

``RecentList`` 不依赖 Tk，便于对照原版逻辑单测（``tests/test_tk_translate.py``）；
``TranscriptPanel`` 只包一层已建好的 ``ScrolledText``，不做布局。
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import scrolledtext

from snaptranslate.domain.services.text_cleaning import clean_text
from snaptranslate.presentation.texts import WindowText

#: 原 ``_push_recent_translation`` 只保留 3 条
RECENT_LIMIT = 3


class RecentList:
    """最近 3 条翻译（原 ``self.recent_items``）。"""

    def __init__(self, limit: int = RECENT_LIMIT) -> None:
        self._limit = limit
        self._items: list[tuple[str, str]] = []

    def __len__(self) -> int:
        return len(self._items)

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def items(self) -> list[tuple[str, str]]:
        return self._items

    def push(self, original: str, translated: str) -> bool:
        """清洗后插入队首并截断；任一侧清洗后为空则**不记录**（原版语义）。

        返回是否真的写入（调用方据此决定要不要刷界面）。
        """
        pair = (clean_text(original), clean_text(translated))
        if not pair[0] or not pair[1]:
            return False
        self._items.insert(0, pair)
        self._items = self._items[: self._limit]
        return True

    def get(self, index: int) -> tuple[str, str] | None:
        """原 ``_on_recent_save_click`` 的越界判定 + 取词。"""
        if index < 0 or index >= len(self._items):
            return None
        return self._items[index]

    def labels(self) -> list[str]:
        """渲染成 ``["原文 => 译文", ...]``，不足补齐"（暂无）"（原 ``_refresh_recent_ui``）。"""
        labels = [f"{word} => {meaning}" for word, meaning in self._items]
        while len(labels) < self._limit:
            labels.append(WindowText.EMPTY_RECENT)
        return labels[: self._limit]


class TranscriptPanel:
    """翻译记录文本框（原 ``self.log_text``）。"""

    def __init__(self, log_text: scrolledtext.ScrolledText, recent: RecentList) -> None:
        self._log_text = log_text
        self._recent = recent

    @property
    def recent(self) -> RecentList:
        return self._recent

    def append(self, original: str, result: str) -> None:
        """原 ``_append_log``：``[{ts}] 原文：{x}\\n     译文：{y}\\n\\n``。"""
        ts = time.strftime("%H:%M:%S")
        self._log_text.configure(state="normal")
        self._log_text.insert("end", f"[{ts}] 原文：{original}\n", "orig")
        self._log_text.insert("end", f"     译文：{result}\n\n", "trans")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def clear(self) -> None:
        """原 ``_clear_log``（只清文本框，不动"最近 3 条"列表）。"""
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def push_translation(self, original: str, translated: str) -> bool:
        """写入"最近 3 条"（原 ``_push_recent_translation``）。"""
        return self._recent.push(original, translated)

    def refresh_recent(self, variables: list[tk.StringVar]) -> None:
        """把最近 3 条写进 Tk 变量（原 ``_refresh_recent_ui``）。"""
        if not variables:
            return
        for index, label in enumerate(self._recent.labels()):
            variables[index].set(label)
