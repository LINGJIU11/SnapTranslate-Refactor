"""翻译错误文案格式化端口。

原版 ``main.py:307-325`` 的 ``_format_translate_failure`` 需要 ``requests`` 的异常类型，
属于基础设施知识；应用层通过本端口拿到"已经格式化好的、用户可读的一句话"。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ErrorFormatter(Protocol):
    def __call__(self, exc: BaseException) -> str:
        ...
