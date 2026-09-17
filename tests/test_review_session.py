"""复习会话与揭示状态测试（原桌面端 / Web 端两份实现的汇合点）。"""

from __future__ import annotations

import random
import unittest

from snaptranslate.domain.models.review import Grade, SortMode
from snaptranslate.domain.models.vocab_entry import Vocabulary
from snaptranslate.domain.services.review_session import ReviewSession


def _vocab() -> Vocabulary:
    return Vocabulary(
        [
            {"word": "a", "meaning": "甲", "score": 30, "reviews": 0},
            {"word": "b", "meaning": "乙", "score": 80, "reviews": 2},
            {"word": "c", "meaning": "丙", "score": 30, "reviews": 1},
            {"word": "d", "meaning": "丁", "score": 55, "reviews": 0},
        ]
    )


class OrderTests(unittest.TestCase):
    def test_score_asc_with_index_tiebreak(self) -> None:
        session = ReviewSession(_vocab(), SortMode.SCORE_ASC)
        self.assertEqual(session.order, [0, 2, 3, 1])

    def test_score_desc_with_index_tiebreak(self) -> None:
        session = ReviewSession(_vocab(), SortMode.SCORE_DESC)
        self.assertEqual(session.order, [1, 3, 0, 2])

    def test_random_order_is_permutation(self) -> None:
        session = ReviewSession(_vocab(), SortMode.RANDOM, rng=random.Random(7))
        self.assertEqual(sorted(session.order), [0, 1, 2, 3])

    def test_empty_and_single(self) -> None:
        self.assertEqual(ReviewSession(Vocabulary([]), SortMode.SCORE_ASC).order, [])
        self.assertEqual(ReviewSession(Vocabulary([{"word": "a"}]), SortMode.SCORE_ASC).order, [0])

    def test_set_mode_resets_position(self) -> None:
        session = ReviewSession(_vocab(), SortMode.RANDOM, rng=random.Random(1))
        session.position = 3
        session.set_mode(SortMode.SCORE_ASC)
        self.assertEqual(session.position, 0)
        self.assertEqual(session.order, [0, 2, 3, 1])


class CurrentAndAdvanceTests(unittest.TestCase):
    def test_current_none_when_out_of_range(self) -> None:
        session = ReviewSession(Vocabulary([]), SortMode.SCORE_ASC)
        self.assertIsNone(session.current())

    def test_advance_wraps_and_follows_current_index(self) -> None:
        session = ReviewSession(_vocab(), SortMode.SCORE_ASC)
        self.assertEqual(session.current_index(), 0)
        session.advance_after_grade()
        # 评分模式下重排后再定位原卡片，并前进一格
        self.assertEqual(session.position, 1)
        self.assertEqual(session.current_index(), 2)

    def test_advance_on_empty_is_noop(self) -> None:
        session = ReviewSession(Vocabulary([]), SortMode.SCORE_ASC)
        session.advance_after_grade()
        self.assertEqual(session.position, 0)


class RevealStateTests(unittest.TestCase):
    def test_toggle_meaning(self) -> None:
        session = ReviewSession(_vocab())
        self.assertFalse(session.reveal.any_revealed)
        self.assertTrue(session.reveal.toggle_meaning())
        self.assertTrue(session.reveal.any_revealed)

    def test_toggle_example_closes_translation(self) -> None:
        session = ReviewSession(_vocab())
        session.reveal.toggle_example()
        session.reveal.toggle_example_zh()
        self.assertTrue(session.reveal.show_example_zh)
        transition = session.reveal.toggle_example()
        self.assertTrue(transition.was_showing)
        self.assertFalse(transition.now_showing)
        self.assertFalse(session.reveal.show_example_zh)

    def test_toggle_example_zh_requires_example(self) -> None:
        session = ReviewSession(_vocab())
        session.reveal.toggle_example_zh()
        self.assertFalse(session.reveal.show_example_zh)

    def test_advance_resets_reveal(self) -> None:
        session = ReviewSession(_vocab())
        session.reveal.toggle_meaning()
        session.advance_after_grade()
        self.assertFalse(session.reveal.any_revealed)


class GradeFlowTests(unittest.TestCase):
    def test_grade_enum_values_match_original_strings(self) -> None:
        self.assertEqual(Grade.KNOW.value, "know")
        self.assertEqual(SortMode.SCORE_DESC.value, "score_desc")


if __name__ == "__main__":
    unittest.main()
