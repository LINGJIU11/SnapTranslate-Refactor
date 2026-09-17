"""测试用临时目录：统一放在**工程内**的 ``.tmp-tests/``。

两个环境适配点（都踩过坑）：

1. 不用系统临时目录（``%TEMP%``）——受限沙箱下子进程对该目录不可写；
2. **不用 ``tempfile.TemporaryDirectory``/``mkdtemp``**——在受限令牌下它建出来的目录
   连写和删都会被拒绝（``PermissionError``，连 ``rmtree`` 都失败）。改用
   ``os.makedirs`` 建目录 + ``shutil.rmtree(..., ignore_errors=True)`` 清理。
"""

from __future__ import annotations

import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = PROJECT_ROOT / ".tmp-tests"

_WRITABLE: bool | None = None


def _ensure_root() -> Path:
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TEMP_ROOT


def require_writable() -> None:
    """确认当前环境允许子进程写文件；不允许则跳过相关用例。

    探针必须写在 ``os.makedirs`` 建出来的**子目录**里——直接写 ``TEMP_ROOT`` 会掩盖
    "mkdtemp 产物不可写"这一受限场景。
    """
    global _WRITABLE
    if _WRITABLE is None:
        probe_dir = _ensure_root() / f"probe-{uuid.uuid4().hex[:8]}"
        try:
            probe_dir.mkdir(parents=True, exist_ok=True)
            (probe_dir / "write-probe").write_text("ok", encoding="utf-8")
            (probe_dir / "write-probe").unlink()
            _WRITABLE = True
        except Exception:  # noqa: BLE001
            _WRITABLE = False
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)
    if not _WRITABLE:
        raise unittest.SkipTest("当前沙箱不允许子进程写文件系统，跳过需要落盘的用例")


@contextmanager
def temp_dir() -> Iterator[Path]:
    """产出一个自动清理的临时目录（位于工程内，``os.makedirs`` 创建）。"""
    require_writable()
    directory = _ensure_root() / f"tmp-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def nonexistent_path(name: str) -> Path:
    """返回一个位于工程临时区内、**保证不存在**的路径（用于"文件缺失"分支）。"""
    require_writable()
    return _ensure_root() / f"missing-{uuid.uuid4().hex}-{name}"
