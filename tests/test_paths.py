"""路径解析测试：源码运行 vs 打包运行（``sys.frozen``）vs 环境变量覆盖。

打包那条分支是**必须**被测到的：``--onefile`` 下 ``__file__`` 指向临时解包目录，
如果数据目录还是按 ``__file__`` 推，用户的数据会写进临时目录并在退出时消失。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from snaptranslate.config import paths


class PathResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.pop(paths.ENV_DATA_DIR, None)
        self._frozen = getattr(sys, "frozen", None)
        self._exe = sys.executable

    def tearDown(self) -> None:
        if self._env is not None:
            os.environ[paths.ENV_DATA_DIR] = self._env
        else:
            os.environ.pop(paths.ENV_DATA_DIR, None)
        if self._frozen is None:
            if hasattr(sys, "frozen"):
                del sys.frozen
        else:
            sys.frozen = self._frozen
        sys.executable = self._exe

    # —— 源码运行 ——

    def test_source_run_uses_project_root(self) -> None:
        self.assertFalse(paths.is_frozen())
        self.assertEqual(paths.data_dir(), paths.project_root())
        self.assertEqual(Path(paths.vocab_path()).name, paths.VOCAB_FILENAME)
        self.assertEqual(Path(paths.log_path()).parent, paths.data_dir())

    # —— 打包运行 ——

    def test_frozen_run_uses_exe_directory(self) -> None:
        """打包后数据目录 = exe 同级目录（便携：整个文件夹拷走即可迁移）。"""
        sys.frozen = True  # type: ignore[attr-defined]
        sys.executable = r"C:\portable\SnapTranslate\SnapTranslate.exe"
        try:
            self.assertTrue(paths.is_frozen())
            self.assertEqual(paths.base_dir(), Path(r"C:\portable\SnapTranslate"))
            self.assertEqual(paths.data_dir(), Path(r"C:\portable\SnapTranslate"))
            self.assertEqual(Path(paths.vocab_path()).parent, Path(r"C:\portable\SnapTranslate"))
            self.assertEqual(Path(paths.backup_dir()).name, paths.BACKUP_DIRNAME)
            self.assertEqual(Path(paths.log_path()).name, paths.LOG_FILENAME)
        finally:
            del sys.frozen  # type: ignore[attr-defined]

    def test_frozen_assets_come_from_bundle(self) -> None:
        """打包后图标等资源从解包目录（``sys._MEIPASS``）找。"""
        sys.frozen = True  # type: ignore[attr-defined]
        sys._MEIPASS = r"C:\portable\SnapTranslate\_internal"  # type: ignore[attr-defined]
        try:
            self.assertEqual(
                Path(paths.icon_path()), Path(r"C:\portable\SnapTranslate\_internal\assets\snaptranslate.ico")
            )
        finally:
            del sys.frozen  # type: ignore[attr-defined]
            del sys._MEIPASS  # type: ignore[attr-defined]

    # —— 环境变量覆盖（两种运行方式都优先） ——

    def test_env_override_wins(self) -> None:
        os.environ[paths.ENV_DATA_DIR] = r"D:\SnapTranslateData"
        self.assertEqual(paths.data_dir(), Path(r"D:\SnapTranslateData"))
        self.assertEqual(Path(paths.vocab_path()), Path(r"D:\SnapTranslateData") / paths.VOCAB_FILENAME)

        sys.frozen = True  # type: ignore[attr-defined]
        try:
            # 打包后依然以环境变量为准（用户可以显式指定数据目录）
            self.assertEqual(paths.data_dir(), Path(r"D:\SnapTranslateData"))
        finally:
            del sys.frozen  # type: ignore[attr-defined]

    def test_blank_env_is_ignored(self) -> None:
        os.environ[paths.ENV_DATA_DIR] = "   "
        self.assertEqual(paths.data_dir(), paths.project_root())


if __name__ == "__main__":
    unittest.main()
