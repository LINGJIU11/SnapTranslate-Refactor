"""划词窗口的任务编排：热键回调 → 线程调度 → 用例调用 → 结果落地。

对应原版 ``TranslatorApp`` 里"跑任务"的那一半：

- ``_tab_combo_loop`` 的触发段   ``main.py:1445-1450``（实际生效的热键循环）
- ``_do_translate_job``          ``main.py:1043-1048``
- ``_translate_text_job``        ``main.py:966-1011``
- ``_do_save_last_translation_job`` ``main.py:1050-1067``
- ``_do_screen_ocr_translate_job``（用例调用段）``main.py:1069-1174``
- ``_do_save_vocab_job``         ``main.py:1473-1503``
- ``_ui_show_result``            ``main.py:854-861``
- ``_ui_show_error``             ``main.py:863-866``

与原版一致的三条触发语义：

1. 翻译需要"启用划词翻译"打开（``_is_translate_enabled``）；
2. 收录"最近一条翻译"**不检查启用开关**（原版直接开线程调 ``_do_save_last_translation_job``）；
3. 截图先切主线程开遮罩，再由遮罩松手回调开 worker 线程跑 OCR。
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from snaptranslate.application.deps import TranslateAppDeps
from snaptranslate.application.dto import (
    CollectKind,
    ErrorKind,
    OutcomeKind,
    TranslationOutcome,
)
from snaptranslate.application.progress import ProgressReporter, Stage
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.models.hotkey import Hotkey
from snaptranslate.presentation.texts import ErrorTitle, StatusText, WindowText
from snaptranslate.presentation.tk.collect_actions import (
    ERROR_FLOAT_DURATION_MS,
    CollectionFeedback,
)
from snaptranslate.presentation.tk.translate_sink import ResultSink

#: 原 ``main.py:995``：翻译完成后光标提示"翻译完成"显示 1000ms
DONE_CURSOR_DURATION_MS = 1000
#: 热键动作名（原版 ``hotkeys`` 字典的三个键）
ACTION_TRANSLATE = "translate"
ACTION_SNIP = "snip"
ACTION_SAVE_LAST = "save_last"


def resolve_hotkey_action(
    action: str,
    *,
    enabled: bool,
    hotkeys: dict[str, str],
) -> str | None:
    """原 ``_tab_combo_loop`` 的按键分发判定。

    - ``translate`` / ``snip``：开关关闭时不响应（返回 ``None``）；
    - ``save_last``：**不受开关影响**（原版如此，行为等价保留）；
    - 组合非法：不响应。
    """
    if action in (ACTION_TRANSLATE, ACTION_SNIP) and not enabled:
        return None
    if Hotkey.parse(hotkeys.get(action, "")) is None:
        return None
    return action


class TranslateJobRunner:
    """热键回调与用例调用的编排者。

    :param deps: 已装配的用例（``bootstrap`` 注入）。
    :param sink: 主窗口（实现 :class:`ResultSink`）。
    :param feedback: 收录/删除反馈出口。
    """

    def __init__(self, deps: TranslateAppDeps, sink: ResultSink, feedback: CollectionFeedback) -> None:
        self._deps = deps
        self._sink = sink
        self._feedback = feedback

    # ———————————————————————————— 热键入口 ————————————————————————————

    def dispatch(self, action: str) -> Callable[[], None]:
        """返回监听线程可直接调用的回调：先切主线程，再执行任务。"""

        def callback() -> None:
            if self._sink.is_closing():
                return
            resolved = resolve_hotkey_action(
                action, enabled=self._sink.is_translate_enabled(), hotkeys=self._sink.hotkeys
            )
            if resolved is None:
                return
            self._sink.post(lambda: self._run_action(resolved))

        return callback

    def _run_action(self, action: str) -> None:
        if self._sink.is_closing():
            return
        if action == ACTION_TRANSLATE:
            self.run_translate()
        elif action == ACTION_SAVE_LAST:
            self.run_save_last()
        else:
            # 截图：主线程开遮罩，遮罩松手后再开 worker 线程
            self._sink.begin_snip()

    # ———————————————————————————— 三个用例 ————————————————————————————

    def run_translate(self) -> None:
        """原 ``_do_translate_job`` + ``_translate_text_job``。"""
        if not self._sink.is_translate_enabled():
            return
        use_case = self._deps.selection_usecase_factory(
            self._sink.current_source, self._sink.current_tts_volume
        )
        outcome = use_case.execute(
            progress=self._progress_reporter(),
            no_text_hint=WindowText.no_selection_hint(self._sink.hotkey_label(ACTION_TRANSLATE)),
            capture_failed_hint=WindowText.capture_failed_hint(self._sink.hotkey_label(ACTION_TRANSLATE)),
        )
        self._sink.post_status_reset()
        self.handle_outcome(outcome)

    def run_save_last(self) -> None:
        """原 ``_do_save_last_translation_job``：收录"最近一条翻译"（干净译文）。

        ``NO_LAST``（暂无可收录内容）与原版一致地走 ``floating=False``（``main.py:1058-1065``）。
        """
        outcome = self._deps.recall_last_factory(self._sink.last_translation).execute()
        word = outcome.word or self._sink.last_translation()[0]
        self.post_collect(outcome.kind, word, floating=False)

    def run_screenshot(self, bbox: BBox) -> None:
        """原 ``_do_screen_ocr_translate_job`` 的用例调用段（worker 线程）。"""
        if not self._sink.is_translate_enabled():
            return
        use_case = self._deps.screenshot_usecase_factory(
            self._sink.current_source, self._sink.current_tts_volume
        )
        outcome = use_case.execute(
            bbox,
            progress=self._progress_reporter(),
            no_text_hint=WindowText.NO_SNIP_TEXT_HINT,
        )
        self.handle_outcome(outcome)

    def run_collect(self, word: str, meaning: str) -> None:
        """原 ``_do_save_vocab_job``：判空/判重/落盘在用例里，这里只做反馈。

        **floating 取值对照原版**（``main.py:1473-1503``）：只有"暂无可记录内容"这一条
        （``EMPTY``）走 ``floating=False``；``ADDED`` / ``DUPLICATE`` / ``FAILED`` 都是
        默认的 ``floating=True`` —— 即**收录成功也会弹悬浮卡片**（2000ms）。
        """
        outcome = self._deps.collection.collect(word, meaning)
        self.post_collect(
            outcome.kind, outcome.word or word, floating=outcome.kind is not CollectKind.EMPTY
        )

    # ———————————————————————————— 结果落地 ————————————————————————————

    def handle_outcome(self, outcome: TranslationOutcome) -> None:
        """把 :class:`TranslationOutcome` 变成日志 + 最近列表 + 悬浮卡片 + 错误提示。"""
        if outcome.kind is OutcomeKind.OK:
            self._post_result(outcome)
            return
        if outcome.kind is OutcomeKind.BUSY:
            # 原版 OCR 互斥分支只提示状态栏/光标提示条，不写日志、不弹卡片
            return
        message = outcome.error_message or ""
        if outcome.kind is OutcomeKind.NO_TEXT:
            if outcome.capture_failed:
                # 新增：取词失败时打一行控制台日志便于排查（原版失败分支不打印任何东西，
                # 而且根本区分不出"没取到词"与"取到了剪贴板里的旧内容"）。见 KNOWN_ISSUES.md #20。
                self._log_line("取词失败：Ctrl+C 未生效（已放弃翻译，未使用剪贴板旧内容）")
            self._post_error(ErrorTitle.HINT, message)
        elif outcome.error_kind is ErrorKind.OCR_UNAVAILABLE:
            self._post_error(ErrorTitle.OCR_UNAVAILABLE, message)
        else:
            self._post_error(ErrorTitle.for_kind(outcome.error_kind, outcome.source_text), message)

    def post_collect(self, kind: CollectKind, word: str, *, floating: bool) -> None:
        """收录反馈：原 ``_ui_vocab_feedback`` 必须回主线程执行。"""

        def apply() -> None:
            if self._sink.is_closing():
                return
            self._feedback.collect_feedback(kind, word, floating=floating)
            if kind is CollectKind.ADDED:
                self._sink.refresh_saved()

        self._sink.post(apply)

    def submit_collect(self, word: str, meaning: str) -> None:
        """开 worker 线程收录（原版 ``threading.Thread(target=self._do_save_vocab_job, ...)``）。"""
        threading.Thread(target=self.run_collect, args=(word, meaning), daemon=True).start()

    def submit_screenshot(self, bbox: BBox) -> None:
        """开 worker 线程跑 OCR（原版松手回调里的 ``threading.Thread(...).start()``）。"""
        threading.Thread(target=self.run_screenshot, args=(bbox,), daemon=True).start()

    # ———————————————————————————— 内部 ————————————————————————————

    def _progress_reporter(self) -> ProgressReporter:
        """进度出口：状态栏与光标提示条都按 ``StatusText.texts(stage)`` 走。"""
        return ProgressReporter(
            on_status=self._on_progress_status,
            on_cursor=self._on_progress_cursor,
        )

    def _on_progress_status(self, stage: Stage) -> None:
        status_text, _cursor_text, _duration = StatusText.texts(stage)
        if status_text is not None:
            self._sink.set_status(status_text)

    def _on_progress_cursor(self, stage: Stage) -> None:
        _status_text, cursor_text, duration = StatusText.texts(stage)
        self._sink.show_cursor(cursor_text, duration_ms=duration)

    def _post_result(self, outcome: TranslationOutcome) -> None:
        """成功分支：控制台日志 ``原文 => display`` + ``_ui_show_result`` + 光标提示。"""
        result = outcome.result
        if result is None:
            return
        source = outcome.source_text
        display = result.display_text
        self._log_line(f"{source} => {display}")

        def apply() -> None:
            if self._sink.is_closing():
                return
            self._sink.show_result(source, display, save_translation=result.text)
            # 原 ``main.py:995``：光标提示"翻译完成"1000ms —— 文案与时长都取自统一文案表
            _status_text, done_text, done_duration = StatusText.texts(Stage.DONE)
            self._sink.show_cursor(done_text, duration_ms=done_duration or DONE_CURSOR_DURATION_MS)
            self._sink.post_status_reset()

        self._sink.post(apply)

    def _post_error(self, title: str, message: str) -> None:
        """失败分支：原 ``_ui_show_error``（``main.py:863-866``）。

        原版失败分支**不打印控制台日志**（只有成功分支 ``main.py:990`` 会 print），
        因此这里只追加记录 + 弹简短的悬浮卡片。
        """

        def apply() -> None:
            if self._sink.is_closing():
                return
            self._sink.append_log(title, message)
            self._sink.show_float(title, message, duration_ms=ERROR_FLOAT_DURATION_MS)

        self._sink.post(apply)

    @staticmethod
    def _log_line(message: str) -> None:
        """控制台日志，格式与原版 ``print(f"[{time.strftime('%H:%M:%S')}] ...")`` 一致。"""
        print(f"[{time.strftime('%H:%M:%S')}] {message}")


__all__ = [
    "ACTION_SAVE_LAST",
    "ACTION_SNIP",
    "ACTION_TRANSLATE",
    "DONE_CURSOR_DURATION_MS",
    "ResultSink",
    "TranslateJobRunner",
    "resolve_hotkey_action",
]
