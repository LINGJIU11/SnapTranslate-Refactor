"""备份写入器测试（命名、缺失文案、清理策略）。"""

from __future__ import annotations

import os
import time
import unittest
from pathlib import Path

from snaptranslate.infrastructure.persistence.backup import (
    DEFAULT_MISSING_MESSAGE,
    WEB_MISSING_MESSAGE,
    FileBackupWriter,
)
from tests._tmp import nonexistent_path, temp_dir


class _FakeClock:
    def __init__(self, stamp_value: str = "2026-09-17_16-27-59") -> None:
        self._stamp = stamp_value

    def stamp(self) -> str:
        return self._stamp

    def log_time(self) -> str:
        return "16:27:59"

    def sleep(self, seconds: float) -> None:
        pass


class BackupWriterTests(unittest.TestCase):
    def test_missing_source_message(self) -> None:
        with temp_dir() as tmp:
            writer = FileBackupWriter(str(tmp), _FakeClock())
            result = writer.create(str(tmp / "nope.json"), 3)
            self.assertFalse(result.ok)
            self.assertEqual(result.message, DEFAULT_MISSING_MESSAGE)
            web_result = writer.create(str(tmp / "nope.json"), 3, missing_message=WEB_MISSING_MESSAGE)
            self.assertEqual(web_result.message, WEB_MISSING_MESSAGE)

    def test_create_names_file_with_stamp_and_count(self) -> None:
        with temp_dir() as tmp:
            source = tmp / "vocab.json"
            source.write_text('[{"word":"a"}]', encoding="utf-8")
            writer = FileBackupWriter(str(tmp / "backups"), _FakeClock())
            result = writer.create(str(source), 117)
            self.assertTrue(result.ok)
            self.assertEqual(Path(result.message).name, "vocab_backup_2026-09-17_16-27-59_entries-117.json")
            self.assertEqual(Path(result.message).read_text(encoding="utf-8"), '[{"word":"a"}]')

    def test_list_backups_only_json_sorted_desc(self) -> None:
        with temp_dir() as tmp:
            old, new, other = tmp / "old.json", tmp / "new.json", tmp / "notes.txt"
            for path in (old, new, other):
                path.write_text("{}", encoding="utf-8")
            os.utime(old, (time.time() - 100, time.time() - 100))
            os.utime(new, (time.time(), time.time()))
            writer = FileBackupWriter(str(tmp), _FakeClock())
            self.assertEqual([Path(p).name for p in writer.list_backups()], ["new.json", "old.json"])

    def test_cleanup_keeps_latest(self) -> None:
        with temp_dir() as tmp:
            for index, name in enumerate(["a.json", "b.json", "c.json"]):
                path = tmp / name
                path.write_text("{}", encoding="utf-8")
                os.utime(path, (time.time() - (10 - index), time.time() - (10 - index)))
            writer = FileBackupWriter(str(tmp), _FakeClock())
            removed, keep = writer.cleanup_keep_latest()
            self.assertEqual(removed, 2)
            self.assertEqual(Path(keep).name, "c.json")
            self.assertEqual([Path(p).name for p in writer.list_backups()], ["c.json"])

    def test_cleanup_with_zero_or_one_backup(self) -> None:
        with temp_dir() as tmp:
            writer = FileBackupWriter(str(tmp), _FakeClock())
            self.assertEqual(writer.cleanup_keep_latest(), (0, None))
            single = tmp / "only.json"
            single.write_text("{}", encoding="utf-8")
            removed, keep = writer.cleanup_keep_latest()
            self.assertEqual(removed, 0)
            self.assertEqual(Path(keep).name, "only.json")

    def test_list_backups_missing_directory(self) -> None:
        writer = FileBackupWriter(str(nonexistent_path("backups")), _FakeClock())
        self.assertEqual(writer.list_backups(), [])


if __name__ == "__main__":
    unittest.main()
