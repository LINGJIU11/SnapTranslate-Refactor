"""词表仓储三种加载语义、写盘格式与词表集合行为测试。"""

from __future__ import annotations

import json
import unittest
from contextlib import contextmanager

from snaptranslate.domain.errors import VocabularyIoError
from snaptranslate.domain.models.vocab_entry import Vocabulary
from snaptranslate.infrastructure.persistence.json_vocabulary import JsonVocabularyRepository
from tests._tmp import nonexistent_path, temp_dir


@contextmanager
def vocab_file(payload, name: str = "vocab.json"):
    """写一个词表文件；``payload`` 为 ``None`` 时只创建目录不建文件。"""
    with temp_dir() as directory:
        path = directory / name
        if payload is not None:
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
            path.write_text(text, encoding="utf-8")
        yield path


class LoadSemanticsTests(unittest.TestCase):
    def test_load_raw_keeps_non_dicts(self) -> None:
        with vocab_file([{"word": "a"}, "字符串", 3]) as path:
            self.assertEqual(JsonVocabularyRepository(str(path)).load_raw(), [{"word": "a"}, "字符串", 3])

    def test_load_tolerant_filters_non_dicts(self) -> None:
        with vocab_file([{"word": "a"}, "字符串", 3, None]) as path:
            self.assertEqual(JsonVocabularyRepository(str(path)).load_tolerant(), [{"word": "a"}])

    def test_load_raw_on_non_list_returns_empty(self) -> None:
        with vocab_file({"word": "a"}) as path:
            self.assertEqual(JsonVocabularyRepository(str(path)).load_raw(), [])

    def test_load_strict_raises_on_non_list(self) -> None:
        with vocab_file({"word": "a"}) as path:
            with self.assertRaises(VocabularyIoError) as ctx:
                JsonVocabularyRepository(str(path)).load_strict()
            self.assertEqual(str(ctx.exception), "vocab.json 顶层必须是数组")

    def test_load_strict_raises_on_broken_json(self) -> None:
        with vocab_file("{ not json") as path:
            with self.assertRaises(VocabularyIoError):
                JsonVocabularyRepository(str(path)).load_strict()

    def test_missing_file_behaviour(self) -> None:
        repository = JsonVocabularyRepository(str(nonexistent_path("vocab.json")))
        self.assertFalse(repository.exists())
        self.assertEqual(repository.load_raw(), [])
        self.assertEqual(repository.load_tolerant(), [])
        with self.assertRaises(VocabularyIoError):
            repository.load_strict()

    def test_broken_json_tolerant_returns_empty(self) -> None:
        with vocab_file("{ not json") as path:
            repository = JsonVocabularyRepository(str(path))
            self.assertEqual(repository.load_raw(), [])
            self.assertEqual(repository.load_tolerant(), [])


class SaveFormatTests(unittest.TestCase):
    def test_preserves_key_order_and_unknown_fields(self) -> None:
        sample = [
            {"word": "urban", "meaning": "城市的", "example": "", "example_zh": "", "score": 50.0, "reviews": 0,
             "extra": "保留", "自定义键": 1}
        ]
        with vocab_file(None) as path:
            repository = JsonVocabularyRepository(str(path))
            repository.save(sample)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(json.loads(text), sample)
            self.assertIn("自定义键", text)  # ensure_ascii=False
            self.assertNotIn("\\u", text)
            self.assertIn('\n  {\n    "word"', text)  # indent=2
            self.assertEqual(list(json.loads(text)[0].keys()), list(sample[0].keys()))

    def test_save_is_atomic_and_leaves_no_tmp(self) -> None:
        with vocab_file(None) as path:
            repository = JsonVocabularyRepository(str(path))
            repository.save([{"word": "a"}])
            self.assertTrue(path.is_file())
            self.assertFalse((path.parent / (path.name + ".tmp")).exists())


class VocabularyCollectionTests(unittest.TestCase):
    def test_add_creates_original_field_order(self) -> None:
        vocabulary = Vocabulary([])
        entry = vocabulary.add("urban", "城市的")
        self.assertEqual(
            list(entry.raw.keys()),
            ["word", "meaning", "example", "example_zh", "score", "reviews"],
        )
        self.assertEqual(entry.score, 50.0)
        self.assertEqual(entry.reviews, 0)

    def test_find_exact_match_only(self) -> None:
        vocabulary = Vocabulary([{"word": "urban"}, {"word": "Urban"}])
        self.assertIsNotNone(vocabulary.find("urban"))
        self.assertIsNone(vocabulary.find("urb"))

    def test_remove_word_keeps_non_dict_items(self) -> None:
        vocabulary = Vocabulary([{"word": "a"}, "字符串", {"word": "b"}, {"word": "a"}])
        removed = vocabulary.remove_word("a")
        self.assertEqual(removed, 2)
        self.assertEqual(vocabulary.raw, ["字符串", {"word": "b"}])

    def test_recent_words_dedupes_and_reverses(self) -> None:
        vocabulary = Vocabulary([{"word": "a"}, {"word": "b"}, {"word": "a"}, {"word": ""}, {"word": " c "}])
        self.assertEqual(vocabulary.recent_words(5), ["c", "b", "a"])
        self.assertEqual(vocabulary.recent_words(2), ["c", "b"])

    def test_entry_view_writes_through(self) -> None:
        raw = {"word": "a", "score": 10}
        vocabulary = Vocabulary([raw])
        entry = vocabulary.get(0)
        assert entry is not None
        entry.score = 88.0
        entry.example = "hi"
        self.assertEqual(raw["score"], 88.0)
        self.assertEqual(raw["example"], "hi")

    def test_counts(self) -> None:
        vocabulary = Vocabulary(
            [
                {"word": "a", "example": "x", "example_zh": "y"},
                {"word": "b", "example": "x", "example_zh": ""},
                {"word": "c"},
            ]
        )
        self.assertEqual(vocabulary.pending_example_count(), 2)
        self.assertEqual(vocabulary.with_example_count(), 1)


if __name__ == "__main__":
    unittest.main()
