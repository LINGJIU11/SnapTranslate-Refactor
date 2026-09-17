"""API Key 文件存储（原 ``read_api_key_file`` / ``write_api_key_file``，三处实现一致）。"""

from __future__ import annotations

import os


class FileApiKeyStore:
    """实现 :class:`~snaptranslate.domain.ports.api_key_store.ApiKeyStore`。"""

    def __init__(self, path: str) -> None:
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    def read(self) -> str | None:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                for line in handle:
                    text = line.strip()
                    if text:
                        return text
        except FileNotFoundError:
            return None
        except Exception:
            return None
        return None

    def write(self, key: str) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(key.strip() + "\n")
        os.replace(tmp, self._path)
