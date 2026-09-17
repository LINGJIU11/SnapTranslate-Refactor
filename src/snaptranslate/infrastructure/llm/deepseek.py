"""DeepSeek 例句生成适配器。

收敛原版桌面端（``vocab_review.py:895-935``）与 Web 端（``vocab_review_web.py:123-147``）
两份几乎相同的实现：提示词、JSON 解析、402 余额不足识别。
"""

from __future__ import annotations

import json
import re

from snaptranslate.domain.errors import (
    ExampleGenerationError,
    InsufficientBalanceError,
    MissingApiKeyError,
    MissingDependencyError,
)
from snaptranslate.domain.ports.api_key_store import ApiKeyStore

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

SYSTEM_PROMPT = 'Reply with a single JSON object only, keys: "example" (English), "example_zh" (Chinese).'


def build_user_prompt(word: str, meaning: str) -> str:
    """原版提示词逐字保留。"""
    return (
        "为英语学习者写一句自然地道的英文例句，并给出这句英文的完整简体中文翻译（整句译文，不是只翻译词条）。\n"
        f"词条（可能是词或短语）：{word}\n"
        f"词条中文释义：{meaning}\n\n"
        "只输出一个 JSON 对象，不要 markdown 代码块，不要前缀或解释。\n"
        '格式严格为：{"example":"英文例句","example_zh":"例句的完整中文翻译"}\n'
        "自然、难度适合中高级学习者；若词条是短语，请在例句中自然使用该短语。\n"
    )


def parse_bilingual_response(raw: str) -> tuple[str, str]:
    """从模型输出里解析 ``{"example": ..., "example_zh": ...}``（含 ``` 围栏剥离）。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("模型返回不是 JSON 对象")
    return str(data.get("example", "")).strip(), str(data.get("example_zh", "")).strip()


def is_insufficient_balance_error(exc: BaseException) -> bool:
    """DeepSeek / OpenAI SDK：余额不足通常返回 HTTP 402。"""
    if getattr(exc, "status_code", None) == 402:
        return True
    message = str(exc).lower()
    return "insufficient balance" in message or ("402" in message and "balance" in message)


class DeepSeekExampleGenerator:
    """实现 :class:`~snaptranslate.domain.ports.example_generator.ExampleGenerator`。"""

    def __init__(
        self,
        api_key_store: ApiKeyStore,
        *,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
    ) -> None:
        self._store = api_key_store
        self._base_url = base_url
        self._model = model

    def ensure_ready(self) -> None:
        """就绪校验：``openai`` 可导入且本地存在 API Key（原 ``_get_client``）。"""
        self._build_client()

    def generate(self, word: str, meaning: str) -> tuple[str, str]:
        client = self._build_client()
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(word, meaning)},
                ],
                stream=False,
            )
        except Exception as exc:  # noqa: BLE001 - 需要按原版规则识别 402
            if is_insufficient_balance_error(exc):
                raise InsufficientBalanceError(str(exc), cause=exc) from exc
            raise
        raw = (response.choices[0].message.content or "").strip()
        example, example_zh = parse_bilingual_response(raw)
        if not example or not example_zh:
            raise ExampleGenerationError("模型未返回完整 example / example_zh")
        return example, example_zh

    def _build_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 取决于运行环境
            raise MissingDependencyError("openai", cause=exc) from exc
        key = self._store.read() or ""
        if not key:
            raise MissingApiKeyError()
        return OpenAI(api_key=key, base_url=self._base_url)
