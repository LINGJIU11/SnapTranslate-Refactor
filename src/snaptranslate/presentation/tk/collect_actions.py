"""生词本收录 / 删除的界面反馈（原 ``_ui_vocab_feedback`` ``main.py:868-873``）。

职责：把"用例返回的结果种类"变成"日志 + 状态栏 + 悬浮提示"三件套。
文案一律来自 :class:`~snaptranslate.presentation.texts.CollectText`。

两个要点：

1. ``floating`` 参数必须被真正遵守——原版的取值是
   ``ADDED``/``DUPLICATE``/``FAILED`` 弹卡片、``EMPTY``/``NO_LAST`` 不弹；
2. ``anchor`` 让卡片显示在"触发时鼠标所在的位置"（见 KNOWN_ISSUES.md #23），
   卡片也不再定时消失（#24）。
"""

from __future__ import annotations

from typing import Callable

from snaptranslate.application.dto import CollectKind, DeleteKind
from snaptranslate.presentation.texts import CollectText
from snaptranslate.presentation.tk.translate_sink import FeedbackSink

#: 收录提示的标题（唯一出口在 ``texts.CollectText.TITLE``，原版是字面量 ``"生词本"``）
VOCAB_TITLE = CollectText.TITLE

Anchor = tuple[int, int] | None


class CollectionFeedback:
    """收录/删除反馈的统一出口。

    :param sink: 主窗口（实现 :class:`FeedbackSink`）。
    :param hotkey_label: 返回当前"翻译"热键标签的函数（``NO_LAST`` 文案要用）。
    :param refresh_saved: 收录成功后刷新"最近加入生词本"列表。
    :param floating_allowed: 返回"鼠标旁悬浮提示"是否勾选（关掉时一律不弹，与原版一致）。
    """

    def __init__(
        self,
        sink: FeedbackSink,
        *,
        hotkey_label: Callable[[], str],
        refresh_saved: Callable[[], None],
        floating_allowed: Callable[[], bool],
    ) -> None:
        self._sink = sink
        self._hotkey_label = hotkey_label
        self._refresh_saved = refresh_saved
        self._floating_allowed = floating_allowed

    # —— 收录（原 ``_do_save_vocab_job`` / ``_do_save_last_translation_job``）——

    def collect_feedback(
        self,
        kind: CollectKind,
        word: str,
        *,
        floating: bool,
        anchor: Anchor = None,
    ) -> None:
        """把收录结果写进日志/状态栏；``floating=True`` 时额外弹悬浮提示。"""
        texts = CollectText.for_outcome(kind, word, self._hotkey_label())
        if texts is None:
            return
        title, message = texts
        self.feedback(title, message, floating=floating, anchor=anchor)
        if kind is CollectKind.ADDED:
            self._refresh_saved()

    def feedback(self, title: str, message: str, *, floating: bool = True, anchor: Anchor = None) -> None:
        """原 ``_ui_vocab_feedback``：日志 + 状态栏（+ 可选悬浮卡片）。"""
        self._sink.append_log(title, message)
        self._sink.set_status(message)
        if floating:
            self._maybe_floating(title, message, anchor)

    # —— 删除（原 ``_delete_saved_word``）——

    def delete_feedback(self, kind: DeleteKind, word: str) -> None:
        """``DELETED`` 走"追加日志 + 状态栏"，其余分支只改状态栏（都不弹悬浮）。"""
        message, floating = CollectText.for_delete(kind, word)
        if kind is DeleteKind.DELETED:
            self._refresh_saved()
            self.feedback(VOCAB_TITLE, message, floating=floating)
            return
        self._sink.set_status(message)
        if floating:
            self._maybe_floating(VOCAB_TITLE, message)

    def _maybe_floating(self, title: str, message: str, anchor: Anchor = None) -> None:
        if not self._floating_allowed():
            return
        self._sink.show_floating(title, message, anchor=anchor)


__all__ = ["Anchor", "CollectionFeedback", "VOCAB_TITLE"]
