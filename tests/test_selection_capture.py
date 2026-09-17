"""取词适配器测试——**核心回归**：Ctrl+C 未生效时不得把剪贴板旧内容当原文。

对应 bug：划词翻译"返回了上次复制的网址"（KNOWN_ISSUES.md #20）。
"""

from __future__ import annotations

import unittest

from snaptranslate.infrastructure.input.win32_selection import Win32SelectionReader


class FakeClipboard:
    """可控剪贴板：``simulate_copy`` 表示目标应用真的把选区放进了剪贴板。"""

    def __init__(self, text: str = "", sequence: int = 0) -> None:
        self.text = text
        self._sequence = sequence
        self.reads = 0
        self._copy_after_reads: int | None = None
        self._pending_copy: str | None = None

    # —— Clipboard 端口 ——
    def read_text(self) -> str:
        self.reads += 1
        if self._copy_after_reads is not None and self.reads >= self._copy_after_reads:
            self.simulate_copy(self._pending_copy if self._pending_copy is not None else self.text)
            self._copy_after_reads = None
        return self.text

    def sequence(self) -> int:
        return self._sequence

    # —— 测试辅助 ——
    def simulate_copy(self, text: str) -> None:
        self.text = text
        self._sequence += 1

    def copy_after_reads(self, count: int, text: str) -> None:
        """模拟"复制响应慢"：第 ``count`` 次读剪贴板时才真正写入。"""
        self._copy_after_reads = count
        self._pending_copy = text


class FakeUser32:
    """按键照发；``on_ctrl_c`` 决定目标应用是否真的响应了复制。"""

    def __init__(self, on_ctrl_c=None) -> None:
        self._on_ctrl_c = on_ctrl_c
        self.events = 0

    def keybd_event(self, *args) -> None:
        self.events += 1
        # 一组是 4 次调用（ctrl↓、c↓、c↑、ctrl↑），在第 3 次时模拟复制完成
        if self.events % 4 == 3 and self._on_ctrl_c is not None:
            self._on_ctrl_c()


def _reader(clipboard: FakeClipboard, user32: FakeUser32) -> Win32SelectionReader:
    return Win32SelectionReader(clipboard, user32=user32, copy_delay=0.0, stable_wait=0.0)


class CopySucceededTests(unittest.TestCase):
    def test_returns_fresh_selection(self) -> None:
        clipboard = FakeClipboard("旧内容", sequence=5)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("Hello world"))
        capture = _reader(clipboard, user32).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "Hello world")

    def test_cleans_whitespace_and_newlines(self) -> None:
        clipboard = FakeClipboard("", sequence=1)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("  line1\r\nline2  "))
        capture = _reader(clipboard, user32).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "line1 line2")

    def test_same_text_as_before_is_still_a_successful_copy(self) -> None:
        """选中文本与剪贴板旧内容完全相同时，版本号仍会变化 → 必须判为"取到了"。"""
        clipboard = FakeClipboard("same text", sequence=7)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("same text"))
        capture = _reader(clipboard, user32).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "same text")

    def test_whitespace_only_copy_yields_empty_but_copied(self) -> None:
        clipboard = FakeClipboard("旧", sequence=1)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("   "))
        capture = _reader(clipboard, user32).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "")

    def test_slow_copy_is_caught_by_polling(self) -> None:
        clipboard = FakeClipboard("旧", sequence=1)
        clipboard.copy_after_reads(3, "Late selection")
        capture = _reader(clipboard, FakeUser32()).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "Late selection")


class CopyFailedTests(unittest.TestCase):
    """本次修复的核心：失败必须被识别出来，且**不得**返回剪贴板旧内容。"""

    URL = "https://code.visualstudio.com/updates/v1_138"

    def test_stale_clipboard_is_not_returned_as_selection(self) -> None:
        clipboard = FakeClipboard(self.URL, sequence=11)
        capture = _reader(clipboard, FakeUser32()).read_selected_text()
        self.assertFalse(capture.copied)
        self.assertEqual(capture.text, "")
        self.assertEqual(capture.clipboard_text, self.URL)
        self.assertFalse(capture.usable)

    def test_failure_still_polls_before_giving_up(self) -> None:
        clipboard = FakeClipboard("旧", sequence=3)
        _reader(clipboard, FakeUser32()).read_selected_text()
        # 两次基础读取 + 8 次轮询
        self.assertEqual(clipboard.reads, 10)

    def test_sequence_unavailable_falls_back_to_content_comparison(self) -> None:
        """版本号不可用（返回 0）时退回旧判据：内容变了=成功，没变=失败。"""
        unchanged = FakeClipboard("内容不变", sequence=0)
        capture = _reader(unchanged, FakeUser32()).read_selected_text()
        self.assertFalse(capture.copied)

        changed = FakeClipboard("旧内容", sequence=0)
        user32 = FakeUser32(lambda: changed.simulate_copy("新内容"))
        capture = _reader(changed, user32).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "新内容")


class SelectionCaptureTests(unittest.TestCase):
    def test_usable_requires_copied_and_text(self) -> None:
        from snaptranslate.domain.models.selection import SelectionCapture

        self.assertTrue(SelectionCapture("x", True).usable)
        self.assertFalse(SelectionCapture("", True).usable)
        self.assertFalse(SelectionCapture("x", False).usable)
        self.assertFalse(SelectionCapture("", False).usable)


if __name__ == "__main__":
    unittest.main()
