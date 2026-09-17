"""时间端口。

原版直接用 ``time.strftime`` 生成备份文件名与日志时间戳；抽成端口后可在测试里固定时间。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def stamp(self) -> str:
        """文件名时间戳：``2026-09-17_16-27-59``（原 ``%Y-%m-%d_%H-%M-%S``）。"""
        ...

    def log_time(self) -> str:
        """日志时间：``16:27:59``（原 ``%H:%M:%S``）。"""
        ...

    def sleep(self, seconds: float) -> None:
        ...
