"""复习卡片的「渲染 + 评分 + 揭示」控制器（原 ``vocab_review.py:694-855``）。

原版这些方法直接读写窗口的 ``self.order`` / ``self.pos`` / ``self.show_*``；
分层后它们只与 ``ReviewSession`` 会话和 :class:`CardForm` 控件树打交道，
因此独立成一个小控制器：窗口负责装配与其它事件，这里负责"卡片该长什么样"。

会话对象在"浏览…换词表"时会被整体替换，所以这里持有一个可变引用
（:class:`SessionRef`），保证换表后控制器立刻作用在新会话上。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Protocol

from snaptranslate.domain.errors import VocabularyIoError
from snaptranslate.domain.models.review import Grade, GradeResult
from snaptranslate.domain.models.vocab_entry import Vocabulary, VocabEntry
from snaptranslate.domain.services.review_session import ReviewSession
from snaptranslate.presentation.texts import ReviewText
from snaptranslate.presentation.tk.card_form import CardForm
from snaptranslate.presentation.tk.speech import SpeakScheduler

#: 评分成功后写日志用的回调：``(结果, 档位, 词条文本, 是否已揭示)``
GradeLogged = Callable[[GradeResult, Grade, str, bool], None]
#: 保存失败时的回调（原版弹"保存失败"）
SaveFailed = Callable[[VocabularyIoError], None]


class SessionRef(Protocol):
    """“当前会话 + 它的词表”的可变引用（原版就是窗口上的两个普通属性）。"""

    session: ReviewSession
    vocabulary: Vocabulary


class CardController:
    """把会话状态渲染到控件，并把按钮事件翻译成用例调用。"""

    def __init__(
        self,
        ref: SessionRef,
        form: CardForm,
        speak: SpeakScheduler,
        *,
        progress_var: tk.StringVar,
        score_var: tk.StringVar,
        word_var: tk.StringVar,
        meaning_var: tk.StringVar,
        grade_use_case,
        on_grade_logged: GradeLogged,
        on_save_failed: SaveFailed,
        score_max: float,
    ) -> None:
        self._ref = ref
        self._form = form
        self._speak = speak
        self._progress_var = progress_var
        self._score_var = score_var
        self._word_var = word_var
        self._meaning_var = meaning_var
        self._grade_use_case = grade_use_case
        self._on_grade_logged = on_grade_logged
        self._on_save_failed = on_save_failed
        self._score_max = score_max

    # —— 卡片 ——
    def show(self, read_mode: str, volume: int) -> None:
        """原 ``_show_card``（``792-816``）。"""
        vocabulary = self._ref.vocabulary
        if len(vocabulary) == 0:
            self._progress_var.set("0 / 0")
            self._score_var.set(ReviewText.SCORE_PLACEHOLDER)
            self._word_var.set(ReviewText.EMPTY_VOCAB)
            self._meaning_var.set(ReviewText.MEANING_EMPTY)
            self._form.clear_example()
            return
        session = self._ref.session
        self._progress_var.set(ReviewText.progress(session.position, len(session.order)))
        entry = session.current()
        if entry is None:
            return
        self._score_var.set(ReviewText.score(entry.score, entry.reviews, self._score_max))
        self._word_var.set(entry.word)
        session.reset_reveal()
        self._meaning_var.set(ReviewText.MEANING_PLACEHOLDER)
        self._form.refresh_reveal_ui(session.reveal.show_example)
        self._form.clear_example()
        self._speak.speak_for_card(entry, read_mode, volume)

    # —— 揭示 ——
    def toggle_meaning(self) -> None:
        """原 ``_toggle_meaning``（``818-827``）。"""
        entry = self._ref.session.current()
        if entry is None:
            return
        if self._ref.session.reveal.toggle_meaning():
            self._meaning_var.set(ReviewText.meaning(entry.meaning))
        else:
            self._meaning_var.set(ReviewText.MEANING_HIDDEN)
        self._form.render_example(entry, self._ref.session.reveal)

    def toggle_example(self, read_mode: str, volume: int) -> None:
        """原 ``_toggle_example``（``829-848``）：展开且模式为 word_example 时朗读例句。"""
        entry = self._ref.session.current()
        if entry is None:
            return
        reveal = self._ref.session.reveal
        transition = reveal.toggle_example()
        self._form.refresh_reveal_ui(reveal.show_example)
        self._form.render_example(entry, reveal)
        if (not transition.was_showing) and transition.now_showing:
            if read_mode == "word_example" and str(entry.example or "").strip():
                self._speak.speak_example(entry, volume)

    def toggle_example_zh(self) -> None:
        """原 ``_toggle_example_zh``（``850-855``）：例句未显示时直接返回。"""
        entry = self._ref.session.current()
        if entry is None or not self._ref.session.reveal.show_example:
            return
        self._ref.session.reveal.toggle_example_zh()
        self._form.render_example(entry, self._ref.session.reveal)

    # —— 评分 ——
    def apply_grade(self, grade: Grade, read_mode: str, volume: int) -> None:
        """原 ``_apply_grade``（``694-716``）+ ``_advance_after_grade``（``718-732``）。

        原版 ``_advance_after_grade()`` 的**最后一行**就是 ``self._show_card()``：
        用例推进会话（重排顺序、前进一格、重置揭示状态）之后必须**重绘卡片**，
        否则界面会停在旧卡上（文字、熟练度、进度、释义/例句全都不变），
        而评分已经落在**看不见的下一个词**上。

        因此这里严格照原版语义分三种情况：
        - 没有当前卡片 / 档位非法（用例返回 ``None``）→ 不重绘；
        - 保存失败（``VocabularyIoError``）→ 弹窗、不重绘、不前进；
        - 成功 → 记日志，然后重绘（重绘顺带重置揭示、清空例句框、按模式自动朗读新卡）。
        """
        entry = self._ref.session.current()
        if entry is None:
            return
        # 原版先取 revealed / word，再落盘（落盘会推进会话并重置揭示状态）
        revealed = self._ref.session.reveal.any_revealed
        word = entry.word.strip()
        try:
            result = self._grade_use_case.grade(self._ref.session, grade)
        except VocabularyIoError as exc:
            self._on_save_failed(exc)
            return
        if result is None:
            return
        self._on_grade_logged(result, grade, word, revealed)
        self.show(read_mode, volume)

    def current_entry(self) -> VocabEntry | None:
        """窗口的"手动重读当前词条"需要拿到当前卡片。"""
        return self._ref.session.current()


__all__ = ["CardController", "GradeLogged", "SaveFailed", "SessionRef"]
