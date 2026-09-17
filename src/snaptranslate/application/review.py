"""用例：生词复习（原 ``vocab_review.py`` 与 ``vocab_review_web.py`` 的公共部分）。

两个界面原来各写了一份"顺序 / 评分 / 推进 / 朗读"逻辑，这里收敛成一份用例，
两端只保留渲染与事件绑定。
"""

from __future__ import annotations

from snaptranslate.application.vocabulary_target import VocabularyTarget
from snaptranslate.domain.models.review import Grade, GradeResult, SortMode
from snaptranslate.domain.models.vocab_entry import Vocabulary, VocabEntry
from snaptranslate.domain.ports.backup_writer import BackupResult, BackupWriter
from snaptranslate.domain.ports.tts import TextToSpeech
from snaptranslate.domain.services.review_session import ReviewSession
from snaptranslate.domain.services.scoring import DEFAULT_SCORE, SCORE_MAX, apply_grade

#: 朗读模式（原版界面单选项）
READ_MODE_NONE = "none"
READ_MODE_WORD = "word"
READ_MODE_WORD_EXAMPLE = "word_example"

#: 原版两处不同的朗读超时
SPEAK_WORD_TIMEOUT_SEC = 120.0
SPEAK_WORD_IN_CARD_TIMEOUT_SEC = 60.0
SPEAK_EXAMPLE_TIMEOUT_SEC = 120.0

#: 桌面端与 Web 端对"词表文件缺失"的备份提示文案不同（原版如此）
DESKTOP_MISSING_MESSAGE = "未找到 vocab.json，跳过备份"
WEB_MISSING_MESSAGE = "未找到词表文件，跳过备份"


class ReviewUseCase:
    def __init__(
        self,
        target: VocabularyTarget,
        tts: TextToSpeech,
        backup: BackupWriter,
        *,
        missing_message: str = DESKTOP_MISSING_MESSAGE,
    ) -> None:
        self._target = target
        self._tts = tts
        self._backup = backup
        self._missing_message = missing_message

    # —— 词表 ——
    @property
    def vocab_path(self) -> str:
        return self._target.path

    def use_path(self, path: str) -> None:
        self._target.use(path)

    def load(self) -> Vocabulary:
        """按复习端语义加载词表（容错 + 评分归一化），原 ``vocab_review.py:164-165``。"""
        vocabulary = Vocabulary(self._target.repository.load_tolerant())
        vocabulary.normalize_scores()
        return vocabulary

    def create_session(self, vocabulary: Vocabulary, mode: SortMode | str = SortMode.RANDOM) -> ReviewSession:
        return ReviewSession(vocabulary, mode)

    def pending_examples(self, vocabulary: Vocabulary) -> int:
        return vocabulary.pending_example_count()

    def backup_on_startup(self, vocabulary: Vocabulary) -> BackupResult:
        """原 ``_backup_vocab_on_startup``：词表存在才备份。"""
        return self._backup.create(
            self._target.path,
            len(vocabulary),
            missing_message=self._missing_message,
        )

    # —— 评分 ——
    def grade(self, session: ReviewSession, grade: Grade | str) -> GradeResult | None:
        """自评并落盘；无当前卡片或档位非法时返回 ``None``。

        保存失败会抛出 ``VocabularyIoError``（原版弹"保存失败"并**不**推进卡片）。
        """
        entry = session.current()
        if entry is None:
            return None
        revealed = session.reveal.any_revealed
        applied = apply_grade(entry.raw, grade, revealed)
        if applied is None:
            return None
        old_score, new_score, delta, reviews = applied
        self._target.repository.save(session.vocabulary.raw)
        result = GradeResult(
            word=entry.word.strip(),
            grade=Grade(getattr(grade, "value", grade)),
            revealed=revealed,
            old_score=old_score,
            new_score=new_score,
            delta=delta,
            reviews=reviews,
        )
        session.advance_after_grade()
        return result

    # —— 朗读 ——
    def speak_for_card(self, entry: VocabEntry | None, mode: str, volume: int) -> None:
        """卡面自动朗读：``word`` 模式读单词；``word_example`` 模式**只读单词**
        （例句在展开"显示例句"时才读，见 :meth:`speak_example`）。"""
        if entry is None or mode == READ_MODE_NONE:
            return
        word = entry.word.strip()
        if not word:
            return
        timeout = SPEAK_WORD_IN_CARD_TIMEOUT_SEC if mode == READ_MODE_WORD_EXAMPLE else SPEAK_WORD_TIMEOUT_SEC
        self._tts.speak(word, volume=volume, prefer_en=True, timeout_sec=timeout)

    def speak_example(self, entry: VocabEntry | None, volume: int) -> None:
        if entry is None:
            return
        example = entry.example.strip()
        if not example:
            return
        self._tts.speak(example, volume=volume, prefer_en=True, timeout_sec=SPEAK_EXAMPLE_TIMEOUT_SEC)

    # —— 供表示层渲染 ——
    @staticmethod
    def score_max() -> float:
        return SCORE_MAX

    @staticmethod
    def default_score() -> float:
        return DEFAULT_SCORE
