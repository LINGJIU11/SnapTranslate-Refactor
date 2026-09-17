"""评分规则测试（对照原版三处重复实现）。"""

from __future__ import annotations

import unittest

from snaptranslate.domain.services.scoring import (
    DEFAULT_SCORE,
    GRADE_DELTA,
    SCORE_MAX,
    SCORE_MIN,
    apply_grade,
    item_score,
    normalize_scores,
)


class ItemScoreTests(unittest.TestCase):
    def test_default_when_missing_or_invalid(self) -> None:
        self.assertEqual(item_score({}), DEFAULT_SCORE)
        self.assertEqual(item_score({"score": None}), DEFAULT_SCORE)
        self.assertEqual(item_score({"score": "abc"}), DEFAULT_SCORE)

    def test_clamped_to_range(self) -> None:
        self.assertEqual(item_score({"score": -10}), SCORE_MIN)
        self.assertEqual(item_score({"score": 1000}), SCORE_MAX)

    def test_numeric_string_is_parsed(self) -> None:
        self.assertAlmostEqual(item_score({"score": "42.5"}), 42.5)

    def test_normalize_scores_writes_back(self) -> None:
        items = [{"score": "abc"}, {"score": 999}]
        normalize_scores(items)
        self.assertEqual(items[0]["score"], DEFAULT_SCORE)
        self.assertEqual(items[1]["score"], SCORE_MAX)


class ApplyGradeTests(unittest.TestCase):
    def test_unrevealed_deltas(self) -> None:
        self.assertEqual(apply_grade({"score": 50.0, "reviews": 0}, "know", False), (50.0, 60.0, 10.0, 1))
        self.assertEqual(apply_grade({"score": 50.0, "reviews": 0}, "vague", False), (50.0, 46.0, -4.0, 1))
        self.assertEqual(apply_grade({"score": 50.0, "reviews": 0}, "unknown", False), (50.0, 42.0, -8.0, 1))

    def test_revealed_deltas(self) -> None:
        self.assertEqual(apply_grade({"score": 50.0, "reviews": 0}, "know", True), (50.0, 55.0, 5.0, 1))
        self.assertEqual(apply_grade({"score": 50.0, "reviews": 0}, "vague", True), (50.0, 43.0, -7.0, 1))
        self.assertEqual(apply_grade({"score": 50.0, "reviews": 0}, "unknown", True), (50.0, 38.0, -12.0, 1))

    def test_clamped_and_rounded(self) -> None:
        item = {"score": 96.6, "reviews": 0}
        old, new, delta, reviews = apply_grade(item, "know", True)
        self.assertEqual(old, 96.6)
        self.assertEqual(new, 100.0)
        self.assertEqual(item["score"], 100.0)
        self.assertEqual(item["reviews"], 1)
        self.assertEqual(delta, 5.0)
        self.assertEqual(reviews, 1)

    def test_invalid_grade_returns_none(self) -> None:
        self.assertIsNone(apply_grade({"score": 50.0}, "nonsense", False))

    def test_broken_reviews_value_raises_like_original(self) -> None:
        """原版 ``int(it.get("reviews") or 0) + 1`` 对非数字会抛 ValueError——保持等价。"""
        item = {"score": 50.0, "reviews": "x"}
        with self.assertRaises(ValueError):
            apply_grade(item, "know", False)

    def test_delta_table_matches_original(self) -> None:
        self.assertEqual(
            GRADE_DELTA,
            {
                ("know", False): 10.0,
                ("vague", False): -4.0,
                ("unknown", False): -8.0,
                ("know", True): 5.0,
                ("vague", True): -7.0,
                ("unknown", True): -12.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
