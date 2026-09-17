"""用例：词表后台管理（原 ``set.py``）。"""

from __future__ import annotations

from typing import Callable

from snaptranslate.application.dto import AdminStatus
from snaptranslate.domain.errors import VocabularyFileMissingError
from snaptranslate.domain.models.vocab_entry import Vocabulary
from snaptranslate.domain.ports.backup_writer import BackupWriter
from snaptranslate.domain.ports.vocabulary_repository import VocabularyRepository
from snaptranslate.domain.services.scoring import DEFAULT_SCORE

#: 原 ``set.py:10``
DEFAULT_REVIEWS = 0


class VocabularyAdminUseCase:
    """界面允许用户手填词表路径与备份目录，因此仓储/备份写入器按路径现建。"""

    def __init__(
        self,
        repository_factory: Callable[[str], VocabularyRepository],
        backup_writer_factory: Callable[[str], BackupWriter],
    ) -> None:
        self._repository_factory = repository_factory
        self._backup_writer_factory = backup_writer_factory

    def status(self, vocab_path: str, backup_dir: str) -> AdminStatus:
        """原 ``AdminApp.refresh_status``：词表读取失败不影响备份信息展示。"""
        total: int | None = None
        with_example: int | None = None
        pending: int | None = None
        read_error: str | None = None
        try:
            vocabulary = Vocabulary(self._repository_factory(vocab_path).load_strict())
            total = len(vocabulary)
            with_example = vocabulary.with_example_count()
            pending = total - with_example
        except Exception as exc:  # noqa: BLE001 - 原版就是整段 try/except
            read_error = str(exc)

        backups = self._backup_writer_factory(backup_dir).list_backups()
        return AdminStatus(
            total=total,
            with_example=with_example,
            pending=pending,
            backup_count=len(backups),
            latest_backup=backups[0] if backups else None,
            read_error=read_error,
        )

    def reset_scores(self, vocab_path: str) -> int:
        """把所有词条重置为 ``score=50.0``、``reviews=0``，返回条数。"""
        repository = self._repository_factory(vocab_path)
        if not repository.exists():
            raise VocabularyFileMissingError(vocab_path)
        vocabulary = Vocabulary(repository.load_strict())
        for entry in vocabulary:
            entry.score = float(DEFAULT_SCORE)
            entry.reviews = int(DEFAULT_REVIEWS)
        repository.save(vocabulary.raw)
        return len(vocabulary)

    def cleanup_backups(self, backup_dir: str) -> tuple[int, str | None]:
        """删除旧备份仅保留最新一个。"""
        return self._backup_writer_factory(backup_dir).cleanup_keep_latest()
