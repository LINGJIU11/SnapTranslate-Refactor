"""JSON 设置仓储（两种写入语义，见 ARCHITECTURE.md §4.3）。"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping


class JsonSettingsRepository:
    """实现 :class:`~snaptranslate.domain.ports.settings_repository.SettingsRepository`。"""

    def __init__(self, path: str) -> None:
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def read(self) -> dict[str, Any]:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def merge(self, patch: Mapping[str, Any]) -> None:
        """原 ``main.py:_save_settings``：先读现有内容再 update，失败向上抛（调用方自行吞掉）。"""
        data = self.read()
        if not isinstance(data, dict):
            data = {}
        data.update(patch)
        self._atomic_dump(data)

    def replace(self, payload: Mapping[str, Any]) -> None:
        """原 ``vocab_review.py:_save_tts_volume``：整体覆盖，失败时静默并清理临时文件。"""
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    def _atomic_dump(self, data: Mapping[str, Any]) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(dict(data), handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)
