"""词表备份端口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BackupResult:
    """备份结果（原版用 ``(bool, str)`` 元组，这里换成具名结构）。"""

    ok: bool
    message: str
    path: str | None = None


@runtime_checkable
class BackupWriter(Protocol):
    @property
    def directory(self) -> str:
        ...

    def list_backups(self) -> list[str]:
        """按修改时间倒序返回备份文件路径（原 ``set.py:list_backups``）。"""
        ...

    def create(self, source_path: str, entry_count: int) -> BackupResult:
        """把词表复制到备份目录，文件名含时间戳与条目数。"""
        ...

    def cleanup_keep_latest(self) -> tuple[int, str | None]:
        """删除旧备份只留最新一个，返回 ``(删除数量, 保留的文件)``。"""
        ...
