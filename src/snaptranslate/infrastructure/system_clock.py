"""系统时钟适配器（原版直接调用 ``time.strftime`` / ``time.sleep``）。"""

from __future__ import annotations

import time


class SystemClock:
    """实现 :class:`~snaptranslate.domain.ports.clock.Clock`。"""

    def stamp(self) -> str:
        return time.strftime("%Y-%m-%d_%H-%M-%S")

    def log_time(self) -> str:
        return time.strftime("%H:%M:%S")

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
