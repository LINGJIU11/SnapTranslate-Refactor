"""当前词表文件绑定。

复习端（桌面/网页）允许用户在界面里切换词表文件，而用例需要"当前生效的那个仓储"。
用一个可重绑定的绑定对象表达，避免把"界面选择"泄漏进领域层。
"""

from __future__ import annotations

from typing import Callable

from snaptranslate.domain.ports.vocabulary_repository import VocabularyRepository


class VocabularyTarget:
    """持有当前词表路径 + 按路径现建仓储的工厂。"""

    def __init__(self, path: str, repository_factory: Callable[[str], VocabularyRepository]) -> None:
        self._path = path
        self._factory = repository_factory

    @property
    def path(self) -> str:
        return self._path

    @property
    def repository(self) -> VocabularyRepository:
        return self._factory(self._path)

    def use(self, path: str) -> None:
        """切换到另一个词表文件（原版"浏览…"/"加载词表"）。"""
        self._path = path
