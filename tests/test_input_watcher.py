"""全局输入监听器测试（悬浮卡片"按任意键/鼠标键才关闭"的底层）。

不需要真实键盘：用假 ``user32`` 提供按键状态。
"""

from __future__ import annotations

import threading
import time
import unittest

from snaptranslate.infrastructure.input.win32_input_watcher import (
    MOUSE_BUTTON_VKS,
    Win32InputWatcher,
)

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_ALT = 0x12
VK_A = 0x41


class FakeUser32:
    """可按需设置"当前按下的键"。"""

    def __init__(self) -> None:
        self.pressed: set[int] = set()

    def GetAsyncKeyState(self, vk: int) -> int:
        return 0x8000 if vk in self.pressed else 0


class _Recorder:
    def __init__(self) -> None:
        self.count = 0
        self._event = threading.Event()

    def __call__(self) -> None:
        self.count += 1
        self._event.set()

    def wait(self, timeout: float = 2.0) -> bool:
        return self._event.wait(timeout)

    def reset(self) -> None:
        self.count = 0
        self._event.clear()


class InputWatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user32 = FakeUser32()
        self.watcher = Win32InputWatcher(user32=self.user32, poll_interval=0.001)
        self.recorder = _Recorder()

    def tearDown(self) -> None:
        self.watcher.stop()

    def test_keys_held_at_start_are_ignored(self) -> None:
        """触发用的热键（例如 alt+z 的 Alt）在启动时就按着，不能算"用户新动作"。"""
        self.user32.pressed.add(VK_ALT)
        self.watcher.start(self.recorder)
        time.sleep(0.1)
        self.assertEqual(self.recorder.count, 0)

        # 松开再按，才算新动作
        self.user32.pressed.discard(VK_ALT)
        time.sleep(0.05)
        self.user32.pressed.add(VK_ALT)
        self.assertTrue(self.recorder.wait())
        self.assertGreaterEqual(self.recorder.count, 1)

    def test_any_key_press_fires(self) -> None:
        self.watcher.start(self.recorder)
        time.sleep(0.05)
        self.user32.pressed.add(VK_A)
        self.assertTrue(self.recorder.wait())

    def test_mouse_buttons_fire(self) -> None:
        for vk in (VK_LBUTTON, VK_RBUTTON):
            with self.subTest(button=vk):
                self.user32.pressed = {vk}
                recorder = _Recorder()
                self.watcher.start(recorder)
                time.sleep(0.05)
                self.user32.pressed = set()
                time.sleep(0.05)
                self.user32.pressed = {vk}
                self.assertTrue(recorder.wait(), msg=f"鼠标键 {vk} 未触发")
                self.watcher.stop()

    def test_holding_a_key_does_not_repeat_fire(self) -> None:
        self.watcher.start(self.recorder)
        time.sleep(0.05)
        self.user32.pressed.add(VK_A)
        self.assertTrue(self.recorder.wait())
        time.sleep(0.1)
        self.assertEqual(self.recorder.count, 1, "同一个键一直按着不应重复回调")

    def test_new_presses_fire_again(self) -> None:
        self.watcher.start(self.recorder)
        time.sleep(0.05)
        self.user32.pressed.add(VK_A)
        self.assertTrue(self.recorder.wait())
        self.user32.pressed.discard(VK_A)
        time.sleep(0.05)
        self.recorder.reset()
        self.user32.pressed.add(VK_A)
        self.assertTrue(self.recorder.wait())
        self.assertEqual(self.recorder.count, 1)

    def test_stop_ends_listening(self) -> None:
        self.watcher.start(self.recorder)
        self.watcher.stop()
        self.user32.pressed.add(VK_A)
        time.sleep(0.1)
        self.assertEqual(self.recorder.count, 0)
        self.assertFalse(self.watcher.is_running())

    def test_watched_codes_cover_mouse_buttons(self) -> None:
        self.assertTrue(set(MOUSE_BUTTON_VKS) >= {VK_LBUTTON, VK_RBUTTON})


if __name__ == "__main__":
    unittest.main()
