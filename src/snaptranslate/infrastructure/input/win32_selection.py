"""取词适配器：模拟 Ctrl+C 后读剪贴板（原 ``main.py:949-964``）。

已知副作用（原样保留，见 KNOWN_ISSUES.md #4）：会覆盖用户剪贴板内容且不还原。
"""

from __future__ import annotations

import ctypes

from snaptranslate.domain.ports.clipboard import Clipboard
from snaptranslate.domain.ports.clock import Clock
from snaptranslate.domain.services.text_cleaning import clean_text
from snaptranslate.infrastructure.system_clock import SystemClock

VK_CTRL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002

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

    def read_selected_text(self) -> str:
        before = self._clipboard.read_text()
        self._send_ctrl_c()
        self._clock.sleep(self._copy_delay)
        copied = self._clipboard.read_text()
        if copied == before:
            # 某些应用复制响应慢，短暂轮询几次，降低误判"未选中"的概率。
            for _ in range(self._poll_times):
                self._clock.sleep(self._stable_wait)
                copied = self._clipboard.read_text()
                if copied != before:
                    break
        return clean_text(copied)

    def _send_ctrl_c(self) -> None:
        user32 = self._user32
        user32.keybd_event(VK_CTRL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CTRL, 0, KEYEVENTF_KEYUP, 0)
