"""取词适配器测试。

覆盖三件必须成立的事：

1. **Ctrl+C 未生效时不得把剪贴板旧内容当原文**（KNOWN_ISSUES #20 的回归）；
2. **热键里的 Alt/Shift/Win 按着时先等它松开再注入**（KNOWN_ISSUES #22 的回归）；
3. 注入 Ctrl+C 时按键之间留间隔，并把"修饰键一直按着"如实带回给调用方。
"""

from __future__ import annotations

import unittest

from snaptranslate.infrastructure.input.win32_selection import (
    KEY_GAP_SEC,
    VK_ALT,
    VK_CTRL,
    VK_SHIFT,
    Win32SelectionReader,
)


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
    """可控按键状态 + 可控复制响应。

    - ``pressed``：当前按下的虚拟键码（模拟"手还按着 Alt"）；
    - ``release_after_checks``：第 N 次查询键态之后自动松开（模拟人手松开）；
    - ``on_ctrl_c``：目标应用是否真的响应了这次 Ctrl+C；
    - ``timeline``：记录 check/key 事件，用于断言"先等松开、再注入"。
    """

    def __init__(self, on_ctrl_c=None, pressed=(), release_after_checks: int | None = None) -> None:
        self._on_ctrl_c = on_ctrl_c
        self.pressed = set(pressed)
        self.release_after_checks = release_after_checks
        self.checks = 0
        self.events = 0
        self.timeline: list[tuple[str, int, bool]] = []

    def GetAsyncKeyState(self, vk: int) -> int:
        self.checks += 1
        if self.release_after_checks is not None and self.checks > self.release_after_checks:
            self.pressed.discard(vk)
        down = vk in self.pressed
        self.timeline.append(("check", vk, down))
        return 0x8000 if down else 0

    def keybd_event(self, vk: int, scan: int, flags: int, extra: int) -> None:
        self.events += 1
        self.timeline.append(("key", vk, bool(flags)))
        if self.events % 4 == 3 and self._on_ctrl_c is not None:
            self._on_ctrl_c()

    # —— 断言辅助 ——
    def first_key_index(self) -> int:
        for index, (kind, _vk, _flag) in enumerate(self.timeline):
            if kind == "key":
                return index
        return -1

    def last_modifier_down_index(self) -> int:
        for index in range(len(self.timeline) - 1, -1, -1):
            kind, vk, down = self.timeline[index]
            if kind == "check" and down and vk in (VK_ALT, VK_SHIFT):
                return index
        return -1


class FakeClock:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def stamp(self) -> str:
        return "2026-09-17_00-00-00"

    def log_time(self) -> str:
        return "00:00:00"

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def _reader(clipboard: FakeClipboard, user32: FakeUser32, **kwargs) -> Win32SelectionReader:
    kwargs.setdefault("copy_delay", 0.0)
    kwargs.setdefault("stable_wait", 0.0)
    return Win32SelectionReader(clipboard, user32=user32, **kwargs)


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
    """KNOWN_ISSUES #20 的核心：失败必须被识别出来，且**不得**返回剪贴板旧内容。"""

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


class ModifierReleaseTests(unittest.TestCase):
    """KNOWN_ISSUES #22：热键里的 Alt/Shift/Win 会"毒化"注入的 Ctrl+C。"""

    def test_waits_for_alt_release_before_injecting(self) -> None:
        clipboard = FakeClipboard("旧内容", sequence=1)
        user32 = FakeUser32(
            lambda: clipboard.simulate_copy("Selected text"),
            pressed=(VK_ALT,),
            release_after_checks=3,
        )
        clock = FakeClock()
        capture = _reader(clipboard, user32, clock=clock).read_selected_text()

        self.assertTrue(capture.copied)
        self.assertEqual(capture.text, "Selected text")
        # 注入的按键必须发生在"最后一次检测到修饰键仍按着"之后
        self.assertGreater(user32.first_key_index(), user32.last_modifier_down_index())

    def test_modifier_never_released_is_reported(self) -> None:
        """一直按着 Alt（等超时）：照旧尝试，但要把"修饰键按着"如实带回来。"""
        clipboard = FakeClipboard("旧内容", sequence=1)
        user32 = FakeUser32(pressed=(VK_ALT,))
        capture = _reader(clipboard, user32, release_timeout=0.05).read_selected_text()
        self.assertFalse(capture.copied)
        self.assertTrue(capture.modifiers_held)

    def test_no_modifier_means_no_wait(self) -> None:
        clipboard = FakeClipboard("旧内容", sequence=1)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("ok"))
        clock = FakeClock()
        _reader(clipboard, user32, clock=clock).read_selected_text()
        # 没按修饰键时不能出现"等松开"的 10ms 轮询：只应有 3 次注入间隔 + 1 次复制后等待
        self.assertEqual(clock.sleeps, [KEY_GAP_SEC, KEY_GAP_SEC, KEY_GAP_SEC, 0.0])

    def test_injection_has_gaps_between_keystrokes(self) -> None:
        clipboard = FakeClipboard("旧内容", sequence=1)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("ok"))
        clock = FakeClock()
        _reader(clipboard, user32, clock=clock).read_selected_text()
        self.assertEqual(clock.sleeps.count(KEY_GAP_SEC), 3)

    def test_ctrl_is_not_treated_as_poisoning_modifier(self) -> None:
        """Ctrl 本来就该按着（Ctrl+C 需要它），不能被当成"修饰键未松开"而空等。"""
        clipboard = FakeClipboard("旧内容", sequence=1)
        user32 = FakeUser32(lambda: clipboard.simulate_copy("selected"), pressed=(VK_CTRL,))
        capture = _reader(clipboard, user32).read_selected_text()
        self.assertTrue(capture.copied)
        self.assertFalse(capture.modifiers_held)


class SelectionCaptureTests(unittest.TestCase):
    def test_usable_requires_copied_and_text(self) -> None:
        from snaptranslate.domain.models.selection import SelectionCapture

        self.assertTrue(SelectionCapture("x", True).usable)
        self.assertFalse(SelectionCapture("", True).usable)
        self.assertFalse(SelectionCapture("x", False).usable)
        self.assertFalse(SelectionCapture("", False).usable)


if __name__ == "__main__":
    unittest.main()
