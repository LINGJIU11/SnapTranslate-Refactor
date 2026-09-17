"""例句生成端口（DeepSeek / 任意 OpenAI 兼容端点）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ExampleGenerator(Protocol):
    def ensure_ready(self) -> None:
        """校验凭据与依赖是否就绪（不发起生成请求）。

        原版在**批量任务开始前**就调用 ``_get_client()``：没有 Key 就弹窗索取、
        缺 ``openai`` 就提示安装。若把校验推迟到逐条生成时，用户会看到每条都失败而不是弹窗，
        因此这里把"就绪校验"显式作为一个能力。
        缺失时抛 :class:`MissingApiKeyError` / :class:`MissingDependencyError`。
        """
        ...

    def generate(self, word: str, meaning: str) -> tuple[str, str]:
        """返回 ``(英文例句, 例句中文翻译)``。

        失败抛 :class:`~snaptranslate.domain.errors.ExampleGenerationError`；
        余额不足（HTTP 402）抛 :class:`~snaptranslate.domain.errors.InsufficientBalanceError`，
        以便应用层按原版行为立即中止批量任务。
        """
        ...
