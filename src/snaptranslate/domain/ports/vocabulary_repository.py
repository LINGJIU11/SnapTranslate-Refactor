"""词表仓储端口。

**三种加载语义必须显式区分**——原版 4 个脚本各写了一份 ``load_vocab``，行为并不一致，
合并成一种就会改变行为（见 ARCHITECTURE.md §4.2）：

======================  ==========================  ==================  ===========================
方法                     失败时                       非 dict 元素          对应用户可见行为
======================  ==========================  ==================  ===========================
``load_raw()``           返回 ``[]``                  原样保留            `main.py` 划词窗口
``load_tolerant()``      返回 ``[]``                  过滤掉              `vocab_review*.py` 复习端
``load_strict()``        抛 ``VocabularyIoError``      过滤掉              `set.py` 后台管理（显示"读取失败"）
======================  ==========================  ==================  ===========================
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VocabularyRepository(Protocol):
    @property
    def path(self) -> str:
        """词表文件路径（界面需要展示）。"""
        ...

    def exists(self) -> bool:
        ...

    def load_raw(self) -> list[dict]:
        """原 ``main.py:_load_vocab``：仅判断顶层是 list，不过滤元素，任何错误返回空表。"""
        ...

    def load_tolerant(self) -> list[dict]:
        """原 ``vocab_review.py / vocab_review_web.py:load_vocab``：过滤非 dict，任何错误返回空表。"""
        ...

    def load_strict(self) -> list[dict]:
        """原 ``set.py:load_vocab``：读取失败或顶层非数组时抛 :class:`VocabularyIoError`。"""
        ...

    def save(self, items: list[dict]) -> None:
        """原子写（先写 ``.tmp`` 再 ``os.replace``），与原版四处实现一致。"""
        ...
