"""取词适配器：模拟 Ctrl+C 后读剪贴板（原 ``main.py:949-964``）。

本文件修掉了原版两个会误导用户的缺陷（见 KNOWN_ISSUES.md #20、#22）：

**F1（#20）失败被当成成功**：原版只比较"剪贴板内容有没有变"，没变时不报错，
直接把剪贴板里的旧内容当原文翻译 —— 于是"上次复制的网址 => 同一个网址"。
现在用**剪贴板版本号**判断是否真的发生了一次复制，失败就明确返回 ``copied=False``。

**F3（#22）热键里的修饰键"毒化"注入的 Ctrl+C**：监听器在热键按下那一刻就注入 Ctrl+C，
若热键是 Alt+Z 而手还没松开 Alt，目标程序看到的是 **Ctrl+Alt+C**（不是复制），
剪贴板毫无变化 → 取词必然失败（受控实验：按住 Alt 时 4/4 失败，按住 Ctrl 时全部成功）。
现在注入前先等 Alt/Shift/Win 松开（Ctrl 除外，它本来就是 Ctrl+C 的一部分），
并且每次按键之间留一点间隔，避免目标程序处理到 C 键时异步键态已经变化。
"""

from __future__ import annotations

import ctypes
import time

from snaptranslate.domain.models.selection import SelectionCapture
from snaptranslate.domain.ports.clipboard import Clipboard
from snaptranslate.domain.ports.clock import Clock
from snaptranslate.domain.services.text_cleaning import clean_text
from snaptranslate.infrastructure.system_clock import SystemClock

VK_SHIFT = 0x10
VK_CTRL = 0x11
VK_ALT = 0x12
VK_C = 0x43
VK_LWIN = 0x5B
VK_RWIN = 0x5C
KEYEVENTF_KEYUP = 0x0002

#: 原 ``main.py:42-43``：复制后等待与轮询间隔
COPY_DELAY_SEC = 0.06
CLIPBOARD_STABLE_WAIT = 0.03
STABLE_POLL_TIMES = 8
#: 注入 Ctrl+C 时每次按键之间的间隔（原版是零延迟）
KEY_GAP_SEC = 0.015
#: 等待修饰键松开的上限；超时也照样尝试（失败会被如实报出来）
MODIFIER_RELEASE_TIMEOUT_SEC = 0.6

#: 会"毒化" Ctrl+C 的修饰键；**故意不含 Ctrl**（Ctrl+C 需要它）
POISONING_MODIFIER_VKS: tuple[int, ...] = (VK_SHIFT, VK_ALT, VK_LWIN, VK_RWIN)


class Win32SelectionReader:
    """实现 :class:`~snaptranslate.domain.ports.selection_reader.SelectionReader`。"""

    def __init__(
        self,
        clipboard: Clipboard,
        *,
        user32=None,
        clock: Clock | None = None,
        copy_delay: float = COPY_DELAY_SEC,
        stable_wait: float = CLIPBOARD_STABLE_WAIT,
        poll_times: int = STABLE_POLL_TIMES,
        key_gap: float = KEY_GAP_SEC,
        release_timeout: float = MODIFIER_RELEASE_TIMEOUT_SEC,
    ) -> None:
        self._clipboard = clipboard
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._clock = clock or SystemClock()
        self._copy_delay = copy_delay
        self._stable_wait = stable_wait
        self._poll_times = poll_times
        self._key_gap = key_gap
        self._release_timeout = release_timeout

    def read_selected_text(self) -> SelectionCapture:
        # 先等修饰键松开：热键是 Alt+Z 时，手还没松开的 Alt 会让注入的 Ctrl+C 变成 Ctrl+Alt+C
        modifiers_released = self._wait_for_modifiers_released()

        before_text = self._clipboard.read_text()
        before_seq = self._clipboard.sequence()

        self._send_ctrl_c()
        self._clock.sleep(self._copy_delay)
        after_text = self._clipboard.read_text()
        after_seq = self._clipboard.sequence()

        copied = self._copied(before_seq, after_seq, before_text, after_text)
        if not copied:
            # 某些应用复制响应慢，短暂轮询几次（原版同样轮询，只是它把失败当成了成功）
            for _ in range(self._poll_times):
                self._clock.sleep(self._stable_wait)
                after_text = self._clipboard.read_text()
                after_seq = self._clipboard.sequence()
                if self._copied(before_seq, after_seq, before_text, after_text):
                    copied = True
                    break

        if not copied:
            return SelectionCapture(
                text="",
                copied=False,
                clipboard_text=before_text,
                modifiers_held=not modifiers_released,
            )
        return SelectionCapture(text=clean_text(after_text), copied=True)

    # —— 内部 ——
    @staticmethod
    def _copied(before_seq: int, after_seq: int, before_text: str, after_text: str) -> bool:
        """是否真的发生了一次复制。

        优先用剪贴板版本号（可靠）；版本号不可用时（任一为 0）退回内容比对。
        """
        if before_seq and after_seq:
            return before_seq != after_seq
        return before_text != after_text

    def _modifiers_down(self) -> bool:
        for vk in POISONING_MODIFIER_VKS:
            try:
                if self._user32.GetAsyncKeyState(vk) & 0x8000:
                    return True
            except Exception:
                return False  # 取不到键态（例如非 Windows）就不等
        return False

    def _wait_for_modifiers_released(self) -> bool:
        """等 Alt/Shift/Win 全部松开；返回是否等到了（超时返回 False）。"""
        if not self._modifiers_down():
            return True
        deadline = time.monotonic() + self._release_timeout
        while time.monotonic() < deadline:
            self._clock.sleep(0.01)
            if not self._modifiers_down():
                return True
        return False

    def _send_ctrl_c(self) -> None:
        user32 = self._user32
        gap = self._key_gap
        user32.keybd_event(VK_CTRL, 0, 0, 0)
        self._clock.sleep(gap)
        user32.keybd_event(VK_C, 0, 0, 0)
        self._clock.sleep(gap)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        self._clock.sleep(gap)
        user32.keybd_event(VK_CTRL, 0, KEYEVENTF_KEYUP, 0)
