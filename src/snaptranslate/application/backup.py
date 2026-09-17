"""用例：启动时备份词表（原 ``main.py:569-582``）。

与复习端的区别：划词窗口是**重新从磁盘读一遍**再统计条数（``len(items)``，且不过滤非 dict），
复习端用的是内存里那份已加载的词表——因此这里保留"重新读取"的语义。
"""

from __future__ import annotations

from snaptranslate.domain.ports.backup_writer import BackupResult, BackupWriter
from snaptranslate.domain.ports.vocabulary_repository import VocabularyRepository

DEFAULT_MISSING_MESSAGE = "未找到 vocab.json，跳过备份"


class BackupVocabularyUseCase:
    def __init__(
        self,
        repository: VocabularyRepository,
        backup: BackupWriter,
        *,
        missing_message: str = DEFAULT_MISSING_MESSAGE,
    ) -> None:
        self._repository = repository
        self._backup = backup
        self._missing_message = missing_message

    def execute(self) -> BackupResult:
        if not self._repository.exists():
            return BackupResult(False, self._missing_message)
        # 原版直接用 len(items)，即"顶层数组长度"，不做 dict 过滤
        count = len(self._repository.load_raw())
        return self._backup.create(self._repository.path, count, missing_message=self._missing_message)
