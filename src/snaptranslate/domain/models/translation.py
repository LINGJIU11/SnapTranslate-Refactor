"""翻译结果值对象。

原版把"译文"与"引擎标签"混在一个字符串里传递：

- ``main.py:988-989``：``display = f"{translated}\\n{fb_note}" if fb_note else translated``
- ``main.py:294-296``：竞速命中时 ``fb_note = f"（{label} 最快返回）"``
- 命中缓存时（``main.py:267-270``）**不带**标签

重构后把两者分开保存，再用 :attr:`TranslationResult.display_text` 还原原版的拼接规则，
从而保证界面文案逐字一致（含"命中缓存不显示引擎标签"这一细节）。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 原版多处使用的"空结果"占位符（``main.py:118`` 等）
NO_TRANSLATION_RESULT = "(无翻译结果)"


@dataclass(frozen=True)
class TranslationResult:
    """一次翻译的产出：干净译文 + 可选引擎标签。"""

    text: str
    engine_label: str | None = None

    @classmethod
    def no_result(cls) -> "TranslationResult":
        return cls(NO_TRANSLATION_RESULT, None)

    @property
    def is_empty(self) -> bool:
        """空译文或占位符都算"没翻出来"（原版用 ``out != "(无翻译结果)"`` 判断）。"""
        return (not self.text) or self.text == NO_TRANSLATION_RESULT

    @property
    def display_text(self) -> str:
        """界面展示文本：与 ``main.py:989`` 的拼接规则完全一致。"""
        if self.engine_label:
            return f"{self.text}\n（{self.engine_label} 最快返回）"
        return self.text
