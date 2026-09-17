"""结果落地与对外能力端口（原 ``TranslatorApp`` 的"结果 → 界面"那一半）。

本模块把三件事收敛到一处：

1. :class:`ResultSink` —— ``app_events.TranslateJobRunner`` 依赖的能力集合；
2. :class:`FeedbackSink` —— ``collect_actions.CollectionFeedback`` 依赖的能力集合；
3. :class:`ResultPresenter` —— 上述两个协议的唯一实现，同时持有"最近一条翻译"
   （原 ``_last_original`` / ``_last_translated``）、"最近 3 条翻译"与翻译记录文本框。

线程安全（等价于原版 ``_set_status_safe`` ``main.py:592-600`` 与
``_set_cursor_status_safe`` ``849-852``）：worker 线程（用例的进度回调、收录线程）调用
:meth:`ResultPresenter.set_status` / ``show_cursor`` / ``show_float`` 时一律经
``root.after(0, ...)``；主线程调用则立即生效，以保持原版时序。
"""

from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable, Protocol

from snaptranslate.domain.models.geometry import BBox
from snaptranslate.presentation.tk.cursor_status import CursorStatusWindow
from snaptranslate.presentation.tk.floating_card import FloatingCard
from snaptranslate.presentation.tk.translate_transcript import RecentList, TranscriptPanel


class ResultSink(Protocol):
    """``TranslateJobRunner`` 依赖的能力集合。"""

    @property
    def hotkeys(self) -> dict[str, str]: ...

    def is_closing(self) -> bool: ...

    def is_translate_enabled(self) -> bool: ...

    def hotkey_label(self, key: str) -> str: ...

    def current_source(self) -> str: ...

    def current_tts_volume(self) -> int: ...

    def post(self, fn: Callable[[], None]) -> None: ...

    def set_status(self, message: str) -> None: ...

    def post_status_reset(self) -> None: ...

    def last_translation(self) -> tuple[str, str]: ...

    def append_log(self, original: str, result: str) -> None: ...

    def capture_anchor(self) -> tuple[int, int] | None:
        """取"当前鼠标位置"作为浮层锚点（在**热键按下瞬间**调用，见 KNOWN_ISSUES.md #23）。"""
        ...

    def show_float(self, title: str, message: str, *, anchor: tuple[int, int] | None = None) -> None: ...

    def show_cursor(self, message: str, *, duration_ms: int | None = None) -> None: ...

    def show_result(
        self,
        original: str,
        result: str,
        *,
        save_translation: str | None = None,
        anchor: tuple[int, int] | None = None,
        card_text: str | None = None,
    ) -> None: ...

    def refresh_recent(self, original: str, translated: str) -> None: ...

    def refresh_saved(self) -> None: ...

    def begin_snip(self) -> None: ...

    def submit_screenshot(self, bbox: BBox) -> None: ...


class FeedbackSink(Protocol):
    """``CollectionFeedback`` 依赖的能力集合。"""

    def append_log(self, original: str, result: str) -> None: ...

    def set_status(self, message: str) -> None: ...

    def show_floating(self, title: str, message: str, *, anchor: tuple[int, int] | None = None) -> None: ...


class PresenterHost(Protocol):
    """``ResultPresenter`` 需要窗口注入的取值、Tk 控件与动作。"""

    hotkeys: dict[str, str]
    status_var: tk.StringVar | None
    recent_vars: list[tk.StringVar]

    def is_closing(self) -> bool: ...

    def is_translate_enabled(self) -> bool: ...

    def hotkey_label(self, key: str) -> str: ...

    def current_source(self) -> str: ...

    def current_tts_volume(self) -> int: ...

    def status_message(self) -> str: ...

    def floating_enabled(self) -> bool: ...

    def pointer_position(self) -> tuple[int, int]: ...

    def refresh_saved_ui(self) -> None: ...

    def begin_snip(self) -> None: ...

    def submit_screenshot(self, bbox: BBox) -> None: ...

    def remember_last_translation(self, original: str, translated: str) -> None: ...


class ResultPresenter:
    """把用例结果落到界面，并对外提供 :class:`ResultSink` / :class:`FeedbackSink`。"""

    def __init__(
        self,
        *,
        root: tk.Tk,
        transcript: TranscriptPanel,
        cursor: CursorStatusWindow,
        floating: FloatingCard,
        host: PresenterHost,
    ) -> None:
        self._root = root
        self._transcript = transcript
        self._cursor = cursor
        self._floating = floating
        self._host = host
        self._last_lock = threading.Lock()
        self._last_original: str | None = None
        self._last_translated: str | None = None

    # ———————————————————————————— 端口：取值 ————————————————————————————

    @property
    def hotkeys(self) -> dict[str, str]:
        return self._host.hotkeys

    @property
    def recent(self) -> RecentList:
        return self._transcript.recent

    def is_closing(self) -> bool:
        return self._host.is_closing()

    def is_translate_enabled(self) -> bool:
        return self._host.is_translate_enabled()

    def hotkey_label(self, key: str) -> str:
        return self._host.hotkey_label(key)

    def current_source(self) -> str:
        return self._host.current_source()

    def current_tts_volume(self) -> int:
        return self._host.current_tts_volume()

    def last_translation(self) -> tuple[str, str]:
        with self._last_lock:
            return self._last_original or "", self._last_translated or ""

    def capture_anchor(self) -> tuple[int, int] | None:
        """当前鼠标位置（Win32 调用，监听线程里也能用）。"""
        try:
            return self._host.pointer_position()
        except Exception:
            return None

    # ———————————————————————————— 端口：线程调度与状态 ————————————————————————————

    def post(self, fn: Callable[[], None]) -> None:
        """切回主线程（原版各处 ``root.after(0, ...)``）。"""
        self._root.after(0, fn)

    def set_status(self, message: str) -> None:
        """线程安全地设置状态栏。

        worker 侧对应原版 ``_set_status_safe``（固定 ``after(0, ...)``）；主线程侧
        （面板回调、遮罩）保持立即生效，以免改变原有时序。
        """
        var = self._host.status_var
        if var is None:
            return
        if threading.current_thread() is threading.main_thread():
            var.set(message)
        else:
            self.post(lambda: var.set(message))

    def post_status_reset(self) -> None:
        """任务结束后复位状态栏（原版在每个分支末尾都写一次）。"""
        message = self._host.status_message()
        if threading.current_thread() is threading.main_thread():
            self.set_status(message)
        else:
            self.post(lambda: self.set_status(message))

    # ———————————————————————————— 端口：日志 / 浮层 ————————————————————————————

    def append_log(self, original: str, result: str) -> None:
        """原 ``_append_log``（要求主线程）。"""
        self._transcript.append(original, result)

    def clear_log(self) -> None:
        """原 ``_clear_log``。"""
        self._transcript.clear()

    def show_float(self, title: str, message: str, *, anchor: tuple[int, int] | None = None) -> None:
        """线程安全地弹悬浮卡片（关掉"鼠标旁悬浮提示"时内部直接返回）。

        卡片不再定时消失：等用户下一次按键/点鼠标才关（见 KNOWN_ISSUES.md #24）。
        """

        def apply() -> None:
            if self._host.floating_enabled():
                self._floating.show(title, message, anchor=anchor)

        self.post(apply)

    def show_cursor(self, message: str, *, duration_ms: int | None = None) -> None:
        """线程安全地设光标提示条（原 ``_set_cursor_status_safe``）。"""
        self.post(lambda: self._cursor.show_cursor_text(message, duration_ms=duration_ms))

    # ———————————————————————————— 端口：结果落地 ————————————————————————————

    def show_result(
        self,
        original: str,
        result: str,
        *,
        save_translation: str | None = None,
        anchor: tuple[int, int] | None = None,
        card_text: str | None = None,
    ) -> None:
        """原 ``_ui_show_result``：记住"最近一条翻译" → 日志 → 最近 3 条 → 悬浮卡片。

        ``result``（可带引擎标签）进日志；``card_text``（干净译文）上卡片 —— 见 F8。
        """
        stored = save_translation if save_translation is not None else result
        with self._last_lock:
            self._last_original = original
            self._last_translated = stored
        self._host.remember_last_translation(original, stored)
        self.append_log(original, result)
        self.refresh_recent(original, stored)
        self._floating.show(original, card_text if card_text is not None else result, anchor=anchor)

    def refresh_recent(self, original: str, translated: str) -> None:
        """原 ``_push_recent_translation`` + ``_refresh_recent_ui``（存**干净译文**）。"""
        if self._transcript.push_translation(original, translated):
            self._transcript.refresh_recent(self._host.recent_vars)

    def refresh_saved(self) -> None:
        """原 ``_refresh_recent_saved_ui``（收录成功后调用）。"""
        self._host.refresh_saved_ui()

    # ———————————————————————————— 端口：截图 ————————————————————————————

    def begin_snip(self) -> None:
        self._host.begin_snip()

    def submit_screenshot(self, bbox: BBox) -> None:
        self._host.submit_screenshot(bbox)


__all__ = ["FeedbackSink", "PresenterHost", "ResultPresenter", "ResultSink"]
