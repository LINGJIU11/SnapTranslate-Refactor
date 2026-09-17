"""JSON 词表仓储（三种加载语义，见 ARCHITECTURE.md §4.2 与端口文档）。"""

from __future__ import annotations

import json
import os
from typing import Any

from snaptranslate.domain.errors import VocabularyIoError


class JsonVocabularyRepository:
    """实现 :class:`~snaptranslate.domain.ports.vocabulary_repository.VocabularyRepository`。"""

    def __init__(self, path: str) -> None:
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def exists(self) -> bool:
        return os.path.isfile(self._path)

    # —— 三种加载语义 ——
    def load_raw(self) -> list[dict]:
        """原 ``main.py:_load_vocab``：顶层是 list 就原样返回（**不过滤非 dict 元素**）。"""
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, list) else []
        except FileNotFoundError:
            return []
        except Exception:
            return []

    def load_tolerant(self) -> list[dict]:
        """原 ``vocab_review.py / vocab_review_web.py:load_vocab``：过滤非 dict 元素。"""
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, list):
                return []
            return [item for item in data if isinstance(item, dict)]
        except FileNotFoundError:
            return []
        except Exception:
            return []

    def load_strict(self) -> list[dict]:
        """原 ``set.py:load_vocab``：读取失败或顶层非数组直接抛错（管理界面据此显示"读取失败"）。"""
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            raise VocabularyIoError(str(exc), cause=exc) from exc
        if not isinstance(data, list):
            raise VocabularyIoError("vocab.json 顶层必须是数组")
        return [item for item in data if isinstance(item, dict)]

    # —— 写入 ——
    def save(self, items: list[dict[str, Any]]) -> None:
        """原子写：先写 ``.tmp`` 再 ``os.replace``（四处原实现完全一致）。"""
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(items, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception as exc:
            raise VocabularyIoError(str(exc), cause=exc) from exc
