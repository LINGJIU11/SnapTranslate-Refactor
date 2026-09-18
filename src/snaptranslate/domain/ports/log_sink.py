"""日志端口。

原版把日志直接 ``print`` 到控制台；打包成窗口程序后没有控制台，日志必须有落点。
表示层只依赖本端口，具体写到文件还是同时回显由基础设施决定。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LogSink(Protocol):
    def write(self, line: str) -> None:
        """写一行日志（实现方保证线程安全，且写失败不打断业务流程）。"""
        ...
