"""取词适配器：模拟 Ctrl+C 后读剪贴板（原 ``main.py:949-964``）。

**本文件修掉了一个原版会误导用户的缺陷**（见 KNOWN_ISSUES.md #20）：

原版只看"剪贴板内容有没有变"，内容没变时**不报错**，直接把剪贴板里的旧内容当原文去翻译。
于是当 Ctrl+C 没有真正生效（浏览器抢了快捷键、选区丢失、该区域禁止复制……）时，用户会看到
"上次复制过的网址 => 同一个网址"这种莫名其妙的结果，而且毫无提示。

现在的判据是**剪贴板版本号**（``GetClipboardSequenceNumber``）：只要真的发生了一次复制，
版本号必然变化，即使复制到的文本和旧内容一模一样。判据失效（版本号不可用，返回 0）时，
自动退回原来的"内容比对"，保持旧行为。
"""

from __future__ import annotations

import ctypes

from snaptranslate.domain.models.selection import SelectionCapture
from snaptranslate.domain.ports.clipboard import Clipboard
from snaptranslate.domain.ports.clock import Clock
from snaptranslate.domain.services.text_cleaning import clean_text
from snaptranslate.infrastructure.system_clock import SystemClock

VK_CTRL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002

#: 原 ``main.py:42-43``：复制后等待与轮询间隔
COPY_DELAY_SEC = 0.06
CLIPBOARD_STABLE_WAIT = 0.03
STABLE_POLL_TIMES = 8


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
    ) -> None:
        self._clipboard = clipboard
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._clock = clock or SystemClock()
        self._copy_delay = copy_delay
        self._stable_wait = stable_wait
        self._poll_times = poll_times

    def read_selected_text(self) -> SelectionCapture:
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
            return SelectionCapture(text="", copied=False, clipboard_text=before_text)
        return SelectionCapture(text=clean_text(after_text), copied=True)

    @staticmethod
    def _copied(before_seq: int, after_seq: int, before_text: str, after_text: str) -> bool:
        """是否真的发生了一次复制。

        优先用剪贴板版本号（可靠）；版本号不可用时（任一为 0）退回内容比对。
        """
        if before_seq and after_seq:
            return before_seq != after_seq
        return before_text != after_text

    def _send_ctrl_c(self) -> None:
        user32 = self._user32
        user32.keybd_event(VK_CTRL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CTRL, 0, KEYEVENTF_KEYUP, 0)
