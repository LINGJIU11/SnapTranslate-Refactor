"""热键监听器测试——回归"界面改热键后要立即生效"（KNOWN_ISSUES.md #21）。

用假 ``user32`` 喂按键状态，不需要真实键盘、不需要 Tk。
"""

from __future__ import annotations

import time
import unittest

from snaptranslate.domain.models.hotkey import Hotkey
from snaptranslate.domain.ports.hotkey_listener import HotkeyBindings, HotkeyCallbacks
from snaptranslate.infrastructure.input.win32_hotkeys import Win32PollingHotkeyListener
from snaptranslate.infrastructure.input.win32_keys import VK_ALT, VK_CTRL, VK_L

VK_Z = 0x5A


class FakeUser32:
    """按虚拟键码返回按下状态。"""

    def __init__(self) -> None:
        self.pressed: set[int] = set()

    def GetAsyncKeyState(self, vk: int) -> int:
        return 0x8000 if vk in self.pressed else 0

    def press(self, *vks: int) -> None:
        self.pressed = set(vks)

    def release(self) -> None:
        self.pressed.clear()


def _bindings(translate: str) -> HotkeyBindings:
    return HotkeyBindings(
        translate=Hotkey.parse(translate),
        snip=Hotkey.parse("tab+q"),
        save_last=Hotkey.parse("tab+e"),
    )


def _wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class PollingHotkeyListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user32 = FakeUser32()
        self.fired: list[str] = []
        self.callbacks = HotkeyCallbacks(
            on_translate=lambda: self.fired.append("translate"),
            on_snip=lambda: self.fired.append("snip"),
            on_save_last=lambda: self.fired.append("save_last"),
        )
        self.listener = Win32PollingHotkeyListener(user32=self.user32, poll_interval=0.001)

    def tearDown(self) -> None:
        self.listener.stop()

    def _press_once(self, *vks: int) -> None:
        self.user32.press(*vks)
        time.sleep(0.05)
        self.user32.release()
        time.sleep(0.05)

    def test_binding_fires(self) -> None:
        self.listener.start(_bindings("ctrl+l"), self.callbacks)
        self._press_once(VK_CTRL, VK_L)
        self.assertTrue(_wait_for(lambda: self.fired == ["translate"]))

    def test_update_bindings_takes_effect_without_restart(self) -> None:
        """原版每轮重新读热键 → 改完立即生效；重构版必须等价。"""
        self.listener.start(_bindings("ctrl+l"), self.callbacks)
        self._press_once(VK_CTRL, VK_L)
        self.assertTrue(_wait_for(lambda: self.fired == ["translate"]))

        # 改热键：ctrl+l → alt+z（不重启监听器）
        self.listener.update_bindings(_bindings("alt+z"))

        # 旧组合不再触发
        self.fired.clear()
        self._press_once(VK_CTRL, VK_L)
        time.sleep(0.1)
        self.assertEqual(self.fired, [])

        # 新组合立即生效
        self._press_once(VK_ALT, VK_Z)
        self.assertTrue(_wait_for(lambda: self.fired == ["translate"]))

    def test_three_bindings_are_independent(self) -> None:
        self.listener.start(_bindings("ctrl+l"), self.callbacks)
        self._press_once(VK_CTRL, VK_L)
        self.assertTrue(_wait_for(lambda: "translate" in self.fired))

        self.fired.clear()
        self.user32.press(0x09, 0x51)  # Tab + Q
        time.sleep(0.06)
        self.user32.release()
        self.assertTrue(_wait_for(lambda: "snip" in self.fired))

    def test_stop_ends_loop(self) -> None:
        self.listener.start(_bindings("ctrl+l"), self.callbacks)
        self.listener.stop()
        self._press_once(VK_CTRL, VK_L)
        time.sleep(0.05)
        self.assertEqual(self.fired, [])


if __name__ == "__main__":
    unittest.main()
