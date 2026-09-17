"""词表备份与备份清理（原 ``main.py:569-582``、``vocab_review.py:881-893``、``set.py:41-76``）。

注意：原版三处对"源文件不存在"的提示文案并不一致（划词窗口是"未找到 vocab.json，跳过备份"，
复习端是"未找到词表文件，跳过备份"），因此这里把文案作为参数保留，默认取划词窗口的写法。
"""

from __future__ import annotations

import os
import shutil

from snaptranslate.domain.ports.backup_writer import BackupResult
from snaptranslate.domain.ports.clock import Clock

DEFAULT_MISSING_MESSAGE = "未找到 vocab.json，跳过备份"
#: Web 端（``vocab_review_web.py:152``）用了另一句文案
WEB_MISSING_MESSAGE = "未找到词表文件，跳过备份"


class FileBackupWriter:
    """实现 :class:`~snaptranslate.domain.ports.backup_writer.BackupWriter`。"""

    def __init__(self, directory: str, clock: Clock) -> None:
        self._directory = directory
        self._clock = clock

    @property
    def directory(self) -> str:
        return self._directory

    def list_backups(self) -> list[str]:
        """按修改时间倒序返回 ``*.json`` 备份（原 ``set.py:list_backups``）。"""
        if not os.path.isdir(self._directory):
            return []
        found: list[tuple[float, str]] = []
        for name in os.listdir(self._directory):
            path = os.path.join(self._directory, name)
            if os.path.isfile(path) and name.lower().endswith(".json"):
                found.append((os.path.getmtime(path), path))
        found.sort(key=lambda pair: pair[0], reverse=True)
        return [path for _, path in found]

    def create(
        self,
        source_path: str,
        entry_count: int,
        *,
        missing_message: str = DEFAULT_MISSING_MESSAGE,
    ) -> BackupResult:
        if not os.path.isfile(source_path):
            return BackupResult(False, missing_message)
        self._make_dir()
        name = f"vocab_backup_{self._clock.stamp()}_entries-{entry_count}.json"
        target = os.path.join(self._directory, name)
        try:
            shutil.copy2(source_path, target)
        except Exception as exc:
            return BackupResult(False, f"备份失败：{exc}")
        return BackupResult(True, target, target)

    def cleanup_keep_latest(self) -> tuple[int, str | None]:
        """删除旧备份只留最新一个（原 ``set.py:cleanup_backups_keep_latest``）。"""
        backups = self.list_backups()
        if len(backups) <= 1:
            return 0, backups[0] if backups else None
        keep = backups[0]
        removed = 0
        for path in backups[1:]:
            try:
                os.remove(path)
                removed += 1
            except Exception:
                continue
        return removed, keep

    def _make_dir(self) -> None:
        os.makedirs(self._directory, exist_ok=True)
