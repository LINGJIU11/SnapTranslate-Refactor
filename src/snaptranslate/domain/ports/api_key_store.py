"""API Key 存储端口（原版散落三处的 ``read_api_key_file`` / ``write_api_key_file``）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ApiKeyStore(Protocol):
    @property
    def path(self) -> str:
        ...

    def read(self) -> str | None:
        """返回首个非空行；文件不存在或读取失败返回 ``None``。"""
        ...

    def write(self, key: str) -> None:
        """写入（去空白 + 末尾换行，原子替换）。"""
        ...
