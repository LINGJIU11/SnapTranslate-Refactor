"""单实例守卫端口。

原版 KNOWN_ISSUES #17 记着"无单实例"：热键监听是 **8ms 轮询 ``GetAsyncKeyState``**
（不抢占按键），所以开两个划词窗口会**同时**响应同一次划词、并且互相覆盖 ``vocab.json``。
启动器用命名互斥量挡住第二个实例，并把已开的窗口唤到前台。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SingleInstanceGuard(Protocol):
    def acquire(self, name: str) -> bool:
        """尝试独占 ``name``；**返回 True 表示本次是第一个实例**。

        实现方必须持有句柄直到进程退出（或显式 :meth:`release`），否则互斥量会被系统回收。
        """
        ...

    def release(self) -> None:
        """释放（进程退出时系统也会释放）。"""
        ...
