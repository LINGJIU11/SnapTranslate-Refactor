"""翻译基础设施测试（缓存、响应解析、竞速策略、错误文案、DeepSeek 解析）。"""

from __future__ import annotations

import unittest

import requests

from snaptranslate.domain.errors import MissingApiKeyError
from snaptranslate.domain.models.translation import NO_TRANSLATION_RESULT, TranslationResult
from snaptranslate.infrastructure.llm.deepseek import (
    build_user_prompt,
    is_insufficient_balance_error,
    parse_bilingual_response,
)
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.errors import format_translate_failure
from snaptranslate.infrastructure.translation.factory import (
    SOURCE_MYMEMORY,
    build_racing_translator,
    build_translator,
)
from snaptranslate.infrastructure.translation.google import parse_clients5_payload
from snaptranslate.infrastructure.translation.mymemory import (
    MYMEMORY_ENDPOINT,
    TranslationQuotaError,
    langpairs_for,
    parse_mymemory_response,
)
from snaptranslate.infrastructure.translation.racing import RacingTranslator


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeTranslator:
    """返回固定结果或抛固定异常的假引擎。"""

    def __init__(self, name: str, *, text: str | None = None, error: BaseException | None = None):
        self.name = name
        self._text = text
        self._error = error
        self.calls = 0

    def translate(self, text: str) -> TranslationResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return TranslationResult(self._text or "", self.name)


class TranslationResultTests(unittest.TestCase):
    def test_display_with_and_without_label(self) -> None:
        self.assertEqual(TranslationResult("你好", "Google").display_text, "你好\n（Google 最快返回）")
        self.assertEqual(TranslationResult("你好").display_text, "你好")

    def test_is_empty(self) -> None:
        self.assertTrue(TranslationResult.no_result().is_empty)
        self.assertTrue(TranslationResult("").is_empty)
        self.assertFalse(TranslationResult("你好").is_empty)
        self.assertEqual(TranslationResult.no_result().text, NO_TRANSLATION_RESULT)


class CacheTests(unittest.TestCase):
    def test_skips_empty_results(self) -> None:
        cache = TranslationCache()
        cache.put("google", "a", NO_TRANSLATION_RESULT)
        cache.put("google", "b", "")
        self.assertIsNone(cache.get("google", "a"))
        self.assertIsNone(cache.get("google", "b"))
        self.assertEqual(len(cache), 0)

    def test_lru_eviction(self) -> None:
        cache = TranslationCache(max_size=2)
        cache.put("google", "a", "甲")
        cache.put("google", "b", "乙")
        cache.get("google", "a")  # 提升 a 的新鲜度
        cache.put("google", "c", "丙")
        self.assertIsNone(cache.get("google", "b"))
        self.assertEqual(cache.get("google", "a"), "甲")
        self.assertEqual(cache.get("google", "c"), "丙")


class PayloadParsingTests(unittest.TestCase):
    def test_clients5_variants(self) -> None:
        self.assertEqual(parse_clients5_payload([["你好", "en"], ["世界", "en"]]), "你好世界")
        self.assertEqual(parse_clients5_payload("  纯字符串 "), "纯字符串")
        self.assertEqual(parse_clients5_payload({"x": 1}), "")
        self.assertEqual(parse_clients5_payload([["", "en"], ["b"]]), "b")
        self.assertEqual(parse_clients5_payload([None, [], ["y", "en"]]), "y")

    def test_mymemory_langpairs(self) -> None:
        self.assertEqual(langpairs_for("hello"), ("en|zh-CN", "Autodetect|zh-CN"))
        self.assertEqual(langpairs_for("你好"), ("Autodetect|zh-CN", "en|zh-CN"))

    def test_mymemory_quota_detection(self) -> None:
        with self.assertRaises(RuntimeError):
            parse_mymemory_response(_StubResponse({"responseData": {"translatedText": "MYMEMORY WARNING: X"}}))
        with self.assertRaises(RuntimeError):
            parse_mymemory_response(_StubResponse({"responseData": {"translatedText": "QUOTA EXCEEDED"}}))
        self.assertEqual(parse_mymemory_response(_StubResponse({"responseData": {"translatedText": "你好"}})), "你好")
        self.assertEqual(parse_mymemory_response(_StubResponse({"responseData": {"translatedText": "  "}})), "")
        self.assertEqual(parse_mymemory_response(_StubResponse({})), "")

    def test_endpoint_constant_matches_original(self) -> None:
        self.assertEqual(MYMEMORY_ENDPOINT, "https://api.mymemory.translated.net/get")


class ErrorFormattingTests(unittest.TestCase):
    def test_dns_marker(self) -> None:
        message = format_translate_failure(requests.exceptions.ConnectionError("Failed to resolve 'x'"))
        self.assertIn("DNS 解析失败", message)

    def test_request_exception_truncated(self) -> None:
        long_error = requests.exceptions.HTTPError("x" * 500)
        message = format_translate_failure(long_error)
        self.assertTrue(message.startswith("翻译请求失败（HTTPError）："))
        self.assertTrue(message.endswith("…"))
        self.assertEqual(len(message), len("翻译请求失败（HTTPError）：") + 260 + 1)

    def test_request_exception_short(self) -> None:
        self.assertEqual(
            format_translate_failure(requests.exceptions.HTTPError("403")),
            "翻译请求失败：403",
        )

    def test_generic_exception(self) -> None:
        self.assertEqual(format_translate_failure(ValueError("短")), "短")
        self.assertEqual(len(format_translate_failure(ValueError("x" * 500))), 401)


class RacingTranslatorTests(unittest.TestCase):
    """F7 之后竞速只剩两条线路：clients5 与 MyMemory。"""

    def _racing(self, cache: TranslationCache, c5, mymemory) -> RacingTranslator:
        return RacingTranslator(cache, c5, mymemory)

    def test_returns_first_non_empty_with_label(self) -> None:
        cache = TranslationCache()
        racing = self._racing(
            cache,
            _FakeTranslator("c5", text="译文"),
            _FakeTranslator("mm", error=RuntimeError("慢")),
        )
        result = racing.translate("hello")
        self.assertEqual(result.text, "译文")
        self.assertTrue(result.display_text.endswith("（Google（clients5） 最快返回）"))
        # 卡片上不带引擎标签（F8）
        self.assertEqual(result.card_text, "译文")

    def test_cache_hit_has_no_label(self) -> None:
        cache = TranslationCache()
        cache.put("google_c5", "hello", "缓存译文")
        racing = self._racing(
            cache,
            _FakeTranslator("c5", text="不应被调用"),
            _FakeTranslator("mm", text="y"),
        )
        result = racing.translate("hello")
        self.assertEqual(result.text, "缓存译文")
        self.assertIsNone(result.engine_label)

    def test_prefers_quota_error_when_all_fail(self) -> None:
        racing = self._racing(
            TranslationCache(),
            _FakeTranslator("c5", error=requests.exceptions.Timeout("timeout")),
            _FakeTranslator("mm", error=TranslationQuotaError("MYMEMORY WARNING")),
        )
        with self.assertRaises(TranslationQuotaError):
            racing.translate("hello")

    def test_all_empty_returns_no_result(self) -> None:
        racing = self._racing(
            TranslationCache(),
            _FakeTranslator("c5", text=""),
            _FakeTranslator("mm", text=""),
        )
        self.assertEqual(racing.translate("hello").text, NO_TRANSLATION_RESULT)

    def test_only_two_lines_participate(self) -> None:
        """被裁掉的 gtx 与两条 Lingva 不能再出现在竞速里（F7）。"""
        racing = build_racing_translator(TranslationCache())
        self.assertEqual(racing.line_names, ("Google（clients5）", "MyMemory"))
        self.assertFalse(hasattr(racing, "_lingvas"))
        self.assertFalse(hasattr(racing, "_gtx"))


class FactoryTests(unittest.TestCase):
    def test_mymemory_source(self) -> None:
        translator = build_translator(SOURCE_MYMEMORY, TranslationCache())
        self.assertEqual(translator.name, "mymemory")

    def test_default_source_is_racing(self) -> None:
        translator = build_translator("google", TranslationCache())
        self.assertEqual(translator.name, "racing")

    def test_unknown_source_falls_back_to_racing(self) -> None:
        self.assertEqual(build_translator("whatever", TranslationCache()).name, "racing")


class DeepSeekParsingTests(unittest.TestCase):
    def test_parse_with_fence_and_prefix(self) -> None:
        self.assertEqual(parse_bilingual_response('{"example":"Hi","example_zh":"你好"}'), ("Hi", "你好"))
        self.assertEqual(
            parse_bilingual_response('```json\n{"example":"Hi","example_zh":"你好"}\n```'), ("Hi", "你好")
        )
        self.assertEqual(
            parse_bilingual_response('前缀 {"example":"Hi","example_zh":"你好"} 后缀'), ("Hi", "你好")
        )

    def test_missing_keys_yield_empty(self) -> None:
        self.assertEqual(parse_bilingual_response('{"example":"Hi"}'), ("Hi", ""))

    def test_insufficient_balance(self) -> None:
        class _HttpError(Exception):
            def __init__(self, status):
                super().__init__("insufficient balance" if status == 402 else "boom")
                self.status_code = status

        self.assertTrue(is_insufficient_balance_error(_HttpError(402)))
        self.assertFalse(is_insufficient_balance_error(_HttpError(500)))
        self.assertTrue(is_insufficient_balance_error(Exception("Insufficient Balance")))

    def test_prompt_contains_word_and_meaning(self) -> None:
        prompt = build_user_prompt("urban", "城市的")
        self.assertIn("urban", prompt)
        self.assertIn("城市的", prompt)
        self.assertIn('{"example":"英文例句","example_zh":"例句的完整中文翻译"}', prompt)

    def test_missing_key_raises(self) -> None:
        from snaptranslate.infrastructure.llm.deepseek import DeepSeekExampleGenerator

        class _EmptyStore:
            path = ""

            def read(self):
                return None

            def write(self, key):
                pass

        with self.assertRaises(MissingApiKeyError):
            DeepSeekExampleGenerator(_EmptyStore()).generate("urban", "城市的")

    def test_ensure_ready_flags_missing_key(self) -> None:
        """原版 ``_get_client`` 在批量开始前就读 Key；``ensure_ready`` 等价于此。"""
        from snaptranslate.infrastructure.llm.deepseek import DeepSeekExampleGenerator

        class _EmptyStore:
            path = ""

            def read(self):
                return None

            def write(self, key):
                pass

        with self.assertRaises(MissingApiKeyError):
            DeepSeekExampleGenerator(_EmptyStore()).ensure_ready()

    def test_ensure_ready_passes_with_key(self) -> None:
        from snaptranslate.infrastructure.llm.deepseek import DeepSeekExampleGenerator

        class _Store:
            path = "api_key.txt"

            def read(self):
                return "sk-test-not-a-real-key"

            def write(self, key):
                pass

        DeepSeekExampleGenerator(_Store()).ensure_ready()  # 不应抛异常（不联网）


if __name__ == "__main__":
    unittest.main()
