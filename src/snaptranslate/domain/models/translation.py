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
class Direction:
    """翻译方向（**新增功能**：中译英输入框需要显式方向，原版只有"自动 → 中文"）。

    字段刻意保持"数据化"，让基础设施层自己决定怎么落到具体接口参数上：

    :param source: 源语言（``"auto"`` / ``"zh-CN"``）
    :param target: 目标语言（``"zh-CN"`` / ``"en"``）
    :param variant: 参与**缓存键**的短标签；默认方向为空串，这样原版那一路的缓存键不变
    :param langpair: MyMemory 的显式 ``langpair``；``None`` 表示沿用原版"按内容猜"的行为
    """

    source: str
    target: str
    variant: str = ""
    langpair: str | None = None


#: 原版唯一的方向：自动检测源语言 → 简体中文（默认参数，保证既有路径行为不变）
AUTO_TO_CHINESE = Direction("auto", "zh-CN")

#: 新增功能：中译英输入框
CHINESE_TO_ENGLISH = Direction("zh-CN", "en", variant="zh>en", langpair="zh-CN|en")


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
        """**日志与控制台**用的文本：带引擎标签（原 ``main.py:989`` 的拼接规则）。"""
        if self.engine_label:
            return f"{self.text}\n（{self.engine_label} 最快返回）"
        return self.text

    @property
    def card_text(self) -> str:
        """**悬浮卡片**用的文本：只有干净译文，不带"（X 最快返回）"标签（见 KNOWN_ISSUES.md §五 F8）。

        用户要求：标签只出现在日志里，不干扰卡片上的阅读。
        """
        return self.text
