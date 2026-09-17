"""全局输入监听适配器：轮询"任意键 / 鼠标左右键"是否被按下。

用于让悬浮卡片"不自动消失，直到用户下一次动键盘或点鼠标"。
用轮询 ``GetAsyncKeyState`` 而不是 ``SetWindowsHookEx``：与工程里既有的热键监听保持同一套
机制（无钩子、无消息泵、不干扰其它程序），代价是一个 25ms 轮询线程，开销可忽略。

**启动时已经按下的键会被忽略**——否则用 ``alt+z`` 触发时，卡片一出现就会因为"Alt 还按着"
被立刻关掉。
"""

from __future__ import annotations

import ctypes
import threading
import time
from typing import Callable, Iterable

#: 鼠标左/右/中/侧键（虚拟键码 0x01-0x06）
MOUSE_BUTTON_VKS: tuple[int, ...] = (0x01, 0x02, 0x04, 0x05, 0x06)
#: 键盘按键（0x08-0xFF，跳过未定义的 0x07）
KEY_VKS: tuple[int, ...] = tuple(range(0x08, 0x100))
WATCHED_VKS: tuple[int, ...] = MOUSE_BUTTON_VKS + KEY_VKS

#: 轮询间隔：足够跟上人的操作，又不浪费 CPU
POLL_INTERVAL_SEC = 0.025


class Win32InputWatcher:
    """实现 :class:`~snaptranslate.domain.ports.input_watcher.InputWatcher`。"""

    def __init__(
        self,
        *,
        user32=None,
        poll_interval: float = POLL_INTERVAL_SEC,
        watched_vks: Iterable[int] = WATCHED_VKS,
    ) -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._poll_interval = poll_interval
        self._watched_vks = tuple(watched_vks)
        self._thread: threading.Thread | None = None
        self._stopping = False

    def start(self, on_input: Callable[[], None]) -> None:
        if self._thread is not None:
            return
        self._stopping = False
        self._thread = threading.Thread(
            target=self._loop,
            args=(on_input,),
            daemon=True,
            name="snaptranslate-input-watcher",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=0.5)

    def is_running(self) -> bool:
        return self._thread is not None

    # —— 内部 ——
    def _loop(self, on_input: Callable[[], None]) -> None:
        # 第一次采样只作为基线：此刻按着的键（例如热键里的 Alt）不算"用户新动作"
        previous = self._down_keys()
        while not self._stopping:
            time.sleep(self._poll_interval)
            current = self._down_keys()
            fresh = current - previous
            previous = current
            if fresh and not self._stopping:
                on_input()

    def _down_keys(self) -> set[int]:
        down: set[int] = set()
        for vk in self._watched_vks:
            try:
                if self._user32.GetAsyncKeyState(vk) & 0x8000:
                    down.add(vk)
            except Exception:
                continue
        return down


__all__ = ["KEY_VKS", "MOUSE_BUTTON_VKS", "POLL_INTERVAL_SEC", "WATCHED_VKS", "Win32InputWatcher"]
