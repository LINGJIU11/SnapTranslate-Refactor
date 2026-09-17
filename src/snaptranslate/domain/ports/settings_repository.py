"""设置仓储端口。

两种写入语义同样要分开（见 ARCHITECTURE.md §4.3）：

- ``merge(patch)``：读取现有 dict → update → 写回（原 ``main.py:_save_settings``）；
- ``replace(payload)``：整体覆盖，失败时删除临时文件（原 ``vocab_review.py:_save_tts_volume``）。
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class SettingsRepository(Protocol):
    @property
    def path(self) -> str:
        ...

    def read(self) -> dict[str, Any]:
        """读取设置；文件缺失或损坏返回空 dict（原版语义）。"""
        ...

    def merge(self, patch: Mapping[str, Any]) -> None:
        ...

    def replace(self, payload: Mapping[str, Any]) -> None:
        ...
