"""划词翻译主窗口（原版 ``main.py:350-1918`` 的 ``TranslatorApp``）。

对外接口：``from snaptranslate.presentation.tk.translate_window import TranslateApp``，
构造 ``TranslateApp(deps)`` 后调用 ``run()``。

本文件只做"窗口壳 + 装配 + 面板回调 + 取值方法"；其余职责全部外置：

============================  ==========================================
模块                           内容
============================  ==========================================
``translate_shell``           Tk 变量创建 + 窗口几何 + 头部/日志区装配
``translate_panel``           控制卡片布局
``translate_ui``              面板/窗口壳的 Protocol 契约
``translate_sink``            ``ResultSink``/``FeedbackSink`` 契约 + ``ResultPresenter``
``app_events``                热键回调 → 线程调度 → 用例调用 → 结果落地
``hotkey_controls`` / ``collect_actions``   热键校验 + 收录/删除反馈
``translate_transcript``      翻译记录文本框 + 最近 3 条翻译
``floating_card`` / ``cursor_status`` / ``snip_overlay``   三个浮层
``ui_kit``                    控件工厂 + UI 线程调度
============================  ==========================================

对应原版：``__init__`` ``351-409`` · ``run`` ``1895-1909`` · ``_build_ui`` ``1537-1883``
· ``_on_close`` ``1885-1893`` · ``_on_enable_toggle`` ``626-634`` · ``_on_apply_hotkeys`` ``636-657``
· ``_on_tts_volume_change`` ``453-459`` · ``_refresh_recent_saved_ui`` ``906-914``
· ``_delete_saved_word`` ``916-934`` · ``_on_recent_save_click`` ``936-942``
· ``_on_floating_save_click`` ``944-947``

保留的原版缺陷（见 ``KNOWN_ISSUES.md``）：悬浮卡片"收录生词本"写入的是**带引擎标签的
display 文本**（原 ``_floating_translated``），与"最近 3 条"的收录按钮存干净译文不同。
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import scrolledtext

from snaptranslate.application.deps import TranslateAppDeps
from snaptranslate.application.dto import DeleteKind
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.ports.hotkey_listener import HotkeyBindings, HotkeyCallbacks
from snaptranslate.domain.services.text_cleaning import clean_text
from snaptranslate.presentation.texts import CollectText, WindowText
from snaptranslate.presentation.tk.app_events import (
    ACTION_SAVE_LAST,
    ACTION_SNIP,
    ACTION_TRANSLATE,
    TranslateJobRunner,
)
from snaptranslate.presentation.tk.collect_actions import CollectionFeedback
from snaptranslate.presentation.tk.cursor_status import CursorStatusWindow
from snaptranslate.presentation.tk.floating_card import FloatingCard
from snaptranslate.presentation.tk.hotkey_controls import HotkeyManager
from snaptranslate.presentation.tk.snip_overlay import SnipOverlay
from snaptranslate.presentation.tk.translate_shell import build_translate_window
from snaptranslate.presentation.tk.translate_sink import ResultPresenter
from snaptranslate.presentation.tk.translate_transcript import RecentList, TranscriptPanel
from snaptranslate.presentation.tk.ui_kit import StatusBridge, UiDispatcher

#: 原 ``_load_recent_saved_words`` 取 5 条
RECENT_SAVED_LIMIT = 5


class TranslateApp:
    """``deps`` 是唯一入参；对外接口只有 :meth:`run`。"""

    def __init__(self, deps: TranslateAppDeps) -> None:
        self.deps = deps
        # Tk 变量必须在创建 root 之后绑定，否则报错：Too early to create variable（原版注释）
        self.root: tk.Tk | None = None
        self.status_var: tk.StringVar | None = None
        self.enable_var: tk.BooleanVar | None = None
        self.floating_var: tk.BooleanVar | None = None
        self.translate_source_var: tk.StringVar | None = None
        self.tts_volume_var: tk.IntVar | None = None
        self.hotkey_translate_var: tk.StringVar | None = None
        self.hotkey_snip_var: tk.StringVar | None = None
        self.hotkey_save_var: tk.StringVar | None = None
        self.hotkey_hint_var: tk.StringVar | None = None
        self.log_text: scrolledtext.ScrolledText | None = None
        self.recent_vars: list[tk.StringVar] = []
        self.recent_saved_vars: list[tk.StringVar] = []
        self.recent_saved_words: list[str] = []

        self.hotkeys: dict[str, str] = dict(deps.settings.load_hotkeys())
        self._hotkeys = HotkeyManager(self.hotkeys)
        self._tts_volume_default = deps.settings.load_tts_volume()
        self._last_lock = threading.Lock()
        self._last_original: str | None = None
        self._last_translated: str | None = None
        self._closing = False

        self._dispatcher: UiDispatcher | None = None
        self._bridge: StatusBridge | None = None
        self._presenter: ResultPresenter | None = None
        self._feedback: CollectionFeedback | None = None
        self._runner: TranslateJobRunner | None = None
        self._floating: FloatingCard | None = None
        self._cursor: CursorStatusWindow | None = None
        self._snip: SnipOverlay | None = None

    # ———————————————————————— 启动 / 关闭（原 1895-1909 / 1885-1893）——————————————————

    def run(self) -> None:
        """原 ``run``：建界面 → 启动备份 → 启动热键监听 → 进消息循环。"""
        self._build_ui()
        result = self.deps.startup_backup()
        if result.ok:
            self._log_line(f"生词本已备份：{result.message}")
        else:
            self._log_line(result.message)
        # 只启动轮询监听器；原版 ``hotkey_loop``（RegisterHotKey）从未被启动（KNOWN_ISSUES.md #1）
        self.deps.hotkey_listener.start(self._build_bindings(), self._hotkey_callbacks())
        self.on_enable_toggle()
        assert self.root is not None
        self.root.mainloop()

    def _on_close(self) -> None:
        """原 ``_on_close``：停监听 → 销毁 root（轮询线程收尾归监听器实现）。"""
        self._closing = True
        try:
            self.deps.hotkey_listener.stop()
        except Exception:
            pass
        if self._floating is not None:
            # 停掉"任意键/鼠标键"监听线程，避免退出后还有线程在查键态
            self._floating.shutdown()
        if self.root is not None:
            self.root.destroy()

    # ———————————————————————— 界面构建（原 1537-1883）————————————————————————

    def _build_ui(self) -> None:
        """原 ``_build_ui``：变量与控件由 ``translate_shell`` 建好，这里装配浮层与编排器。"""
        root = tk.Tk()
        self.root = root
        self.log_text = build_translate_window(self, root)
        transcript = TranscriptPanel(self.log_text, RecentList())
        self.tts_volume_var.trace_add("write", self.on_tts_volume_change)

        self._dispatcher = UiDispatcher(root)
        self._dispatcher.bind_status_var(self.status_var)
        self._cursor = CursorStatusWindow(root, cursor_position=self._cursor_position, is_enabled=self.floating_enabled)
        self._floating = FloatingCard(
            root,
            pointer=self.deps.pointer,
            is_enabled=self.floating_enabled,
            on_collect=self.on_floating_save_click,
            input_watcher=self.deps.input_watcher,
            marshal=lambda fn: root.after(0, fn),
        )
        self._bridge = StatusBridge(self._dispatcher, self._cursor)
        self._presenter = ResultPresenter(
            root=root, transcript=transcript, cursor=self._cursor, floating=self._floating, host=self
        )
        self._snip = SnipOverlay(
            root,
            window_activator=self.deps.window_activator,
            set_status=self._presenter.set_status,
            on_bbox=self.submit_screenshot,
        )
        self._feedback = CollectionFeedback(
            self._presenter,
            hotkey_label=lambda: self.hotkey_label(ACTION_TRANSLATE),
            refresh_saved=self._refresh_recent_saved_ui,
            floating_allowed=self.floating_enabled,
        )
        self._runner = TranslateJobRunner(self.deps, self._presenter, self._feedback)

        self._refresh_hotkey_hint()
        self._refresh_recent_saved_ui()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ———————————————————————— 热键（原 626-657 / 1410-1455）————————————————————————

    def _hotkey_callbacks(self) -> HotkeyCallbacks:
        """热键回调（在监听线程触发）→ 编排器负责切主线程。"""
        runner = self._require_runner()
        return HotkeyCallbacks(
            on_translate=runner.dispatch(ACTION_TRANSLATE),
            on_snip=runner.dispatch(ACTION_SNIP),
            on_save_last=runner.dispatch(ACTION_SAVE_LAST),
            on_error=self._on_hotkeys_error,
        )

    def _build_bindings(self) -> HotkeyBindings:
        """把当前热键设置解析成监听端口需要的三组 :class:`Hotkey`。"""
        parsed = self._hotkeys.bindings()
        self.hotkeys = self._hotkeys.hotkeys
        return HotkeyBindings(translate=parsed["translate"], snip=parsed["snip"], save_last=parsed["save_last"])

    def _on_hotkeys_error(self, message: str) -> None:
        """监听器报告的错误（原 ``_show_hotkey_fail``：只写状态栏）。"""
        if self._closing:
            return
        self._require_presenter().set_status(message)

    def on_apply_hotkeys(self) -> None:
        """原 ``_on_apply_hotkeys``：校验失败**不改动**当前热键；成功则落盘并刷新提示。"""
        if self.hotkey_translate_var is None or self.hotkey_snip_var is None or self.hotkey_save_var is None:
            return
        pending = {
            ACTION_TRANSLATE: HotkeyManager.normalize(self.hotkey_translate_var.get()),
            ACTION_SNIP: HotkeyManager.normalize(self.hotkey_snip_var.get()),
            ACTION_SAVE_LAST: HotkeyManager.normalize(self.hotkey_save_var.get()),
        }
        error = self._hotkeys.validate(pending)
        if error is not None:
            self._require_presenter().set_status(error)
            return
        self._hotkeys.set(pending)
        self.hotkeys = self._hotkeys.hotkeys
        self.deps.settings.save_hotkeys(pending)
        # 原版每轮轮询都重新读窗口上的热键，所以**改完立即生效**；监听器必须同步更新，
        # 否则用户会以为"改了热键没反应"（重构阶段一漏了这一步，见 KNOWN_ISSUES.md #21）
        self.deps.hotkey_listener.update_bindings(self._build_bindings())
        self._refresh_hotkey_hint()
        self._require_presenter().post_status_reset()

    def _refresh_hotkey_hint(self) -> None:
        if self.hotkey_hint_var is not None:
            self.hotkey_hint_var.set(self._hotkeys.hint())

    # ———————————————————————— 开关 / 音量（原 626-634 / 453-459）————————————————————————

    def on_enable_toggle(self) -> None:
        """原 ``_on_enable_toggle``。"""
        if self.enable_var is not None and self.status_var is not None:
            self.status_var.set(self.status_message())

    def on_tts_volume_change(self, *_: object) -> None:
        """原 ``_on_tts_volume_change``：滑块变化即落盘，异常静默。"""
        if self.tts_volume_var is None:
            return
        try:
            self.deps.settings.save_tts_volume(int(self.tts_volume_var.get()))
        except (tk.TclError, TypeError, ValueError):
            return

    # ———————————————————————— 面板回调（原 916-947）————————————————————————

    def on_recent_save_click(self, index: int) -> None:
        """原 ``_on_recent_save_click``：收录"最近 3 条"里的**干净译文**。"""
        pair = self._require_presenter().recent.get(index)
        if pair is None:
            self._require_presenter().set_status(CollectText.for_delete(DeleteKind.EMPTY, "")[0])
            return
        self._require_runner().submit_collect(pair[0], pair[1])

    def on_floating_save_click(self) -> None:
        """原 ``_on_floating_save_click``：收录卡片当前的**原文 + display 文本**。

        **行为等价：保留原版缺陷（见 KNOWN_ISSUES.md #6）** —— 卡片上的译文是
        ``TranslationResult.display_text``（可能带"（Google 最快返回）"标签），
        原版把这段带标签的文本原样写进生词本的 ``meaning``。

        锚点用卡片当前位置：收录反馈就地弹出，不会跳到别处（见 KNOWN_ISSUES.md #23）。
        """
        card = self._require_floating()
        self._require_runner().submit_collect(
            clean_text(card.original), clean_text(card.translated), anchor=card.current_anchor()
        )

    def on_delete_saved(self, index: int) -> None:
        """原 ``_delete_saved_word``（主线程直接执行，与原版一致）。"""
        assert self._feedback is not None
        outcome = self.deps.collection.delete_recent(index, RECENT_SAVED_LIMIT)
        self._feedback.delete_feedback(outcome.kind, outcome.word or "")

    def clear_log(self) -> None:
        """原 ``_clear_log``。"""
        assert self._presenter is not None
        self._presenter.clear_log()

    def _refresh_recent_saved_ui(self) -> None:
        """原 ``_refresh_recent_saved_ui``：重新从词表读最近 5 条（用例内部从磁盘读）。"""
        if not self.recent_saved_vars:
            return
        self.recent_saved_words = self.deps.collection.recent_saved_words(RECENT_SAVED_LIMIT)
        words = self.recent_saved_words
        for index in range(RECENT_SAVED_LIMIT):
            self.recent_saved_vars[index].set(words[index] if index < len(words) else WindowText.EMPTY_RECENT)

    # ———————————————————————— 取值（PresenterHost / 面板契约）————————————————————————

    def tts_volume_default(self) -> int:
        return self._tts_volume_default

    def is_closing(self) -> bool:
        return self._closing

    def is_translate_enabled(self) -> bool:
        """原 ``_is_translate_enabled``：读复选框。"""
        return True if self.enable_var is None else bool(self.enable_var.get())

    def floating_enabled(self) -> bool:
        """原版各处读 ``floating_var`` 的等价封装。"""
        if self.floating_var is None:
            return False
        try:
            return bool(self.floating_var.get())
        except tk.TclError:
            return False

    def status_message(self) -> str:
        """原 ``_status_enabled_text`` / ``_status_disabled_text`` 的分支。"""
        return self._hotkeys.status_enabled() if self.is_translate_enabled() else self._hotkeys.status_disabled()

    def hotkey_label(self, key: str) -> str:
        """原 ``_hotkey_label``。"""
        return self._hotkeys.label(key)

    def current_source(self) -> str:
        """原 ``_translate_primary_source``：读失败回退 ``google``。"""
        if self.translate_source_var is None:
            return "google"
        try:
            return self.translate_source_var.get()
        except tk.TclError:
            return "google"

    def current_tts_volume(self) -> int:
        if self.tts_volume_var is None:
            return 100
        try:
            return max(0, min(100, int(self.tts_volume_var.get())))
        except (tk.TclError, TypeError, ValueError):
            return 100

    def remember_last_translation(self, original: str, translated: str) -> None:
        with self._last_lock:
            self._last_original = original
            self._last_translated = translated

    def refresh_saved_ui(self) -> None:
        self._refresh_recent_saved_ui()

    # ———————————————————————— 截图 ————————————————————————

    def begin_snip(self) -> None:
        """原 ``root.after(0, self._begin_screen_snip)``。"""
        if self._snip is not None:
            self._snip.begin()

    def submit_screenshot(self, bbox: BBox) -> None:
        """遮罩松手后开 worker 线程跑 OCR（原版 ``threading.Thread(...).start()``）。"""
        self._require_runner().submit_screenshot(bbox)

    # ———————————————————————— 小工具 ————————————————————————

    def _cursor_position(self) -> tuple[int, int]:
        """当前鼠标屏幕坐标（原 ``get_cursor_pos``，``main.py:617-620``）。

        走注入的 :class:`~snaptranslate.domain.ports.pointer.Pointer`（Win32 ``GetCursorPos``），
        因此**监听线程也能安全调用**——悬浮卡片的锚点就是靠它在热键按下瞬间取的。
        """
        try:
            return self.deps.pointer.position()
        except Exception:
            return (0, 0)

    def pointer_position(self) -> tuple[int, int]:
        """``PresenterHost`` 契约：``ResultPresenter.capture_anchor`` 用它取锚点。"""
        return self._cursor_position()

    @staticmethod
    def _log_line(message: str) -> None:
        """控制台日志，格式与原版 ``print(f"[{time.strftime('%H:%M:%S')}] ...")`` 一致。"""
        print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _require_runner(self) -> TranslateJobRunner:
        assert self._runner is not None
        return self._runner

    def _require_presenter(self) -> ResultPresenter:
        assert self._presenter is not None
        return self._presenter

    def _require_floating(self) -> FloatingCard:
        assert self._floating is not None
        return self._floating
