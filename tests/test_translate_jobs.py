"""结果编排测试：**锚点必须在热键按下那一刻取好**（KNOWN_ISSUES.md #23）。

``TranslateJobRunner.dispatch`` 在监听线程里被调用；本测试用假 sink 记录
"取锚点的时刻"与"结果落地时用的锚点"，不涉及 Tk。
"""

from __future__ import annotations

import unittest

from snaptranslate.application.dto import CollectKind, OutcomeKind, TranslationOutcome
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.models.translation import TranslationResult
from snaptranslate.presentation.tk.app_events import (
    ACTION_SAVE_LAST,
    ACTION_SNIP,
    ACTION_TRANSLATE,
    TranslateJobRunner,
)


class FakeUseCase:
    def __init__(self, outcome: TranslationOutcome) -> None:
        self.outcome = outcome
        self.calls: list[dict] = []

    def execute(self, *args, **kwargs) -> TranslationOutcome:
        self.calls.append(kwargs)
        return self.outcome


class FakeCollection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def collect(self, word: str, meaning: str):
        self.calls.append((word, meaning))
        return type("Outcome", (), {"kind": CollectKind.ADDED, "word": word})()


class FakeRecall:
    def __init__(self) -> None:
        self.executed = 0

    def execute(self):
        self.executed += 1
        return type("Outcome", (), {"kind": CollectKind.EMPTY, "word": ""})()


class FakeLogSink:
    """记录日志行（打包后没有控制台，日志走 log_sink）。"""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, line: str) -> None:
        self.lines.append(line)


class FakeDeps:
    def __init__(self, translate_outcome: TranslationOutcome) -> None:
        self.selection_use_case = FakeUseCase(translate_outcome)
        self.screenshot_use_case = FakeUseCase(translate_outcome)
        self.collection = FakeCollection()
        self.recall = FakeRecall()
        self.log_sink = FakeLogSink()

    def selection_usecase_factory(self, source_provider, volume_provider):
        return self.selection_use_case

    def screenshot_usecase_factory(self, source_provider, volume_provider):
        return self.screenshot_use_case

    def recall_last_factory(self, provider):
        return self.recall


class FakeSink:
    """记录每次落地的参数；鼠标位置可按脚本变化（模拟"取完词之后用户挪了鼠标"）。"""

    def __init__(self, pointer_script: list[tuple[int, int]]) -> None:
        self._positions = list(pointer_script)
        self.anchor_reads = 0
        self.results: list[dict] = []
        self.floats: list[dict] = []
        self.hotkeys = {"translate": "ctrl+f9", "snip": "tab+q", "save_last": "tab+e"}
        self.hotkey_label_value = "CTRL+F9"

    # —— 端口 ——
    def is_closing(self) -> bool:
        return False

    def is_translate_enabled(self) -> bool:
        return True

    def hotkey_label(self, key: str) -> str:
        return self.hotkey_label_value

    def current_source(self) -> str:
        return "google"

    def current_tts_volume(self) -> int:
        return 0

    def post(self, fn) -> None:
        fn()  # 测试里同步执行

    def set_status(self, message: str) -> None:
        pass

    def post_status_reset(self) -> None:
        pass

    def last_translation(self) -> tuple[str, str]:
        return ("", "")

    def append_log(self, original: str, result: str) -> None:
        pass

    def capture_anchor(self):
        self.anchor_reads += 1
        if not self._positions:
            return None
        return self._positions.pop(0)

    def show_float(self, title: str, message: str, *, anchor=None) -> None:
        self.floats.append({"title": title, "message": message, "anchor": anchor})

    def show_cursor(self, message: str, *, duration_ms=None) -> None:
        pass

    def show_result(
        self,
        original: str,
        result: str,
        *,
        save_translation=None,
        anchor=None,
        card_text=None,
    ) -> None:
        self.results.append(
            {
                "original": original,
                "result": result,
                "save": save_translation,
                "anchor": anchor,
                "card_text": card_text,
            }
        )

    def refresh_recent(self, original: str, translated: str) -> None:
        pass

    def refresh_saved(self) -> None:
        pass

    def begin_snip(self) -> None:
        pass

    def submit_screenshot(self, bbox: BBox) -> None:
        pass


class FakeFeedback:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def collect_feedback(self, kind, word, *, floating, anchor=None) -> None:
        self.calls.append({"kind": kind, "word": word, "floating": floating, "anchor": anchor})


def _ok_outcome() -> TranslationOutcome:
    return TranslationOutcome(
        kind=OutcomeKind.OK,
        source_text="hello",
        result=TranslationResult("你好", "Google"),
    )


class AnchorTests(unittest.TestCase):
    HOTKEY_POS = (400, 300)
    MOVED_POS = (1200, 800)

    def _runner(self, sink: FakeSink):
        deps = FakeDeps(_ok_outcome())
        feedback = FakeFeedback()
        return TranslateJobRunner(deps, sink, feedback), feedback, deps

    def test_anchor_taken_at_hotkey_time_not_at_display_time(self) -> None:
        """热键按下时鼠标在 A，翻译返回前用户挪到 B → 卡片必须用 A。"""
        sink = FakeSink([self.HOTKEY_POS, self.MOVED_POS])
        runner, _feedback, _deps = self._runner(sink)

        runner.dispatch(ACTION_TRANSLATE)()  # 模拟监听线程触发

        self.assertEqual(sink.anchor_reads, 1, "锚点只应在触发时取一次")
        self.assertEqual(sink.results[0]["anchor"], self.HOTKEY_POS)
        self.assertEqual(sink.results[0]["result"], "你好\n（Google 最快返回）")

    def test_engine_label_only_in_log_not_on_card(self) -> None:
        """F8：引擎标签进日志（``result``），卡片拿到的是干净译文（``card_text``）。"""
        sink = FakeSink([self.HOTKEY_POS])
        runner, _feedback, _deps = self._runner(sink)

        runner.dispatch(ACTION_TRANSLATE)()

        record = sink.results[0]
        self.assertIn("最快返回", record["result"], "日志里要保留引擎标签")
        self.assertEqual(record["card_text"], "你好", "卡片上不能带标签")
        self.assertNotIn("最快返回", record["card_text"])

    def test_error_card_uses_same_anchor(self) -> None:
        sink = FakeSink([self.HOTKEY_POS])
        deps = FakeDeps(TranslationOutcome(kind=OutcomeKind.NO_TEXT, error_message="取词失败提示"))
        runner = TranslateJobRunner(deps, sink, FakeFeedback())

        runner.dispatch(ACTION_TRANSLATE)()

        self.assertEqual(sink.floats[0]["anchor"], self.HOTKEY_POS)
        self.assertEqual(sink.floats[0]["message"], "取词失败提示")

    def test_collect_uses_anchor(self) -> None:
        sink = FakeSink([self.HOTKEY_POS])
        runner, feedback, _deps = self._runner(sink)

        runner.dispatch(ACTION_SAVE_LAST)()

        self.assertEqual(feedback.calls[0]["anchor"], self.HOTKEY_POS)
        self.assertFalse(feedback.calls[0]["floating"])

    def test_screenshot_uses_selection_corner(self) -> None:
        """截图路径用选区左下角做锚点（遮罩手势结束后鼠标可能已经移开）。"""
        sink = FakeSink([self.HOTKEY_POS])
        runner, _feedback, deps = self._runner(sink)

        bbox = BBox(100, 200, 300, 260)
        runner._run_action(ACTION_SNIP, self.HOTKEY_POS)  # noqa: SLF001 - 遮罩由窗口负责
        runner.run_screenshot(bbox)

        self.assertEqual(sink.results[0]["anchor"], (100, 260))

    def test_missing_pointer_still_works(self) -> None:
        """取不到鼠标位置（返回 None）时不该崩，只是退回"显示时再定位置"。"""
        sink = FakeSink([])
        runner, _feedback, _deps = self._runner(sink)

        runner.dispatch(ACTION_TRANSLATE)()

        self.assertIsNone(sink.results[0]["anchor"])


if __name__ == "__main__":
    unittest.main()
