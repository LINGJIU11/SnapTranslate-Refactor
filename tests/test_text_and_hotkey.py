"""文本清洗与热键解析测试。"""

from __future__ import annotations

import unittest

from snaptranslate.domain.models.hotkey import (
    DEFAULT_HOTKEYS,
    Hotkey,
    is_valid_key_token,
    label_or_placeholder,
    normalize,
)
from snaptranslate.domain.services.text_cleaning import clean_text, is_likely_english, truncate


class CleanTextTests(unittest.TestCase):
    def test_folds_newlines_and_spaces(self) -> None:
        self.assertEqual(clean_text("  a\r\n b  c "), "a b c")
        self.assertEqual(clean_text("行1\n行2"), "行1 行2")
        self.assertEqual(clean_text("\n\n"), "")
        self.assertEqual(clean_text("a  b   c"), "a b c")


class LikelyEnglishTests(unittest.TestCase):
    def test_needs_two_letters(self) -> None:
        self.assertFalse(is_likely_english(""))
        self.assertFalse(is_likely_english("a"))
        self.assertTrue(is_likely_english("ab"))
        self.assertFalse(is_likely_english("你好"))
        self.assertTrue(is_likely_english("你好 ab"))


class TruncateTests(unittest.TestCase):
    def test_short_text_untouched(self) -> None:
        self.assertEqual(truncate("abc"), "abc")

    def test_long_text_gets_suffix(self) -> None:
        result = truncate("x" * 200)
        self.assertEqual(len(result), 123)
        self.assertTrue(result.endswith("..."))


class HotkeyTests(unittest.TestCase):
    def test_normalize(self) -> None:
        self.assertEqual(normalize("  CTRL + L "), "ctrl+l")

    def test_parse_valid(self) -> None:
        parsed = Hotkey.parse("CTRL + L")
        assert parsed is not None
        self.assertEqual((parsed.modifier, parsed.key), ("ctrl", "l"))
        self.assertEqual(parsed.label, "CTRL+L")
        self.assertTrue(parsed.is_win32_registrable)
        self.assertFalse(Hotkey.parse("tab+q").is_win32_registrable)

    def test_parse_invalid(self) -> None:
        for combo in ["", "l", "ctrl+", "+l", "meta+k", "tab+f13", "ctrl+ä", "ctrl+l+m"]:
            self.assertIsNone(Hotkey.parse(combo), msg=combo)

    def test_tab_is_accepted_as_named_key(self) -> None:
        """原版 ``_vk_from_key_token("tab")`` 返回 VK_TAB，因此 ``ctrl+tab`` 是合法的（保持等价）。"""
        parsed = Hotkey.parse("ctrl+tab")
        assert parsed is not None
        self.assertEqual((parsed.modifier, parsed.key), ("ctrl", "tab"))

    def test_named_keys_and_function_keys(self) -> None:
        self.assertTrue(is_valid_key_token("tab"))
        self.assertTrue(is_valid_key_token("space"))
        self.assertTrue(is_valid_key_token("f12"))
        self.assertFalse(is_valid_key_token("f13"))
        self.assertFalse(is_valid_key_token(""))

    def test_label_placeholder(self) -> None:
        self.assertEqual(label_or_placeholder("bad"), "（未设置）")
        self.assertEqual(label_or_placeholder("tab+q"), "TAB+Q")

    def test_defaults(self) -> None:
        self.assertEqual(DEFAULT_HOTKEYS, {"translate": "ctrl+l", "snip": "tab+q", "save_last": "tab+e"})


if __name__ == "__main__":
    unittest.main()
