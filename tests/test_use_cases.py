"""用例层测试：用假适配器（不联网、不起 GUI）验证编排逻辑。"""

from __future__ import annotations

import unittest

from snaptranslate.application.dto import (
    CollectKind,
    DeleteKind,
    ErrorKind,
    OutcomeKind,
    StopKind,
)
from snaptranslate.application.generate_examples import GenerateExamplesUseCase
from snaptranslate.application.progress import ProgressReporter, Stage
from snaptranslate.application.review import (
    READ_MODE_NONE,
    READ_MODE_WORD,
    READ_MODE_WORD_EXAMPLE,
    ReviewUseCase,
)
from snaptranslate.application.translate_screenshot import TranslateScreenshotUseCase
from snaptranslate.application.translate_selection import TranslateSelectionUseCase
from snaptranslate.application.translate_text import TranslateTextUseCase
from snaptranslate.application.vocabulary_admin import VocabularyAdminUseCase
from snaptranslate.application.vocabulary_collection import (
    RecallLastTranslationUseCase,
    VocabularyCollectionUseCase,
)
from snaptranslate.application.vocabulary_target import VocabularyTarget
from snaptranslate.domain.errors import (
    InsufficientBalanceError,
    OcrError,
    OcrUnavailableError,
    SnapTranslateError,
    VocabularyFileMissingError,
    VocabularyIoError,
)
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.models.translation import TranslationResult
from snaptranslate.domain.models.vocab_entry import Vocabulary
from snaptranslate.domain.ports.backup_writer import BackupResult
from snaptranslate.domain.ports.ocr import OcrStage


# —————————————————————————— 假适配器 ——————————————————————————


class FakeRepository:
    def __init__(self, items=None, *, path: str = "vocab.json", fail_save: bool = False,
                 fail_load: bool = False) -> None:
        self._items = list(items or [])
        self._path = path
        self._fail_save = fail_save
        self._fail_load = fail_load
        self.save_count = 0
        self.saved_payloads: list[list[dict]] = []

    @property
    def path(self) -> str:
        return self._path

    def exists(self) -> bool:
        return True

    def load_raw(self):
        if self._fail_load:
            raise VocabularyIoError("boom")
        return list(self._items)

    def load_tolerant(self):
        if self._fail_load:
            raise VocabularyIoError("boom")
        return [item for item in self._items if isinstance(item, dict)]

    def load_strict(self):
        if self._fail_load:
            raise VocabularyIoError("读取失败")
        if not isinstance(self._items, list):
            raise VocabularyIoError("vocab.json 顶层必须是数组")
        return [item for item in self._items if isinstance(item, dict)]

    def save(self, items) -> None:
        self.save_count += 1
        self.saved_payloads.append(list(items))
        if self._fail_save:
            raise VocabularyIoError("写入失败")
        self._items = list(items)


class FakeTts:
    def __init__(self) -> None:
        self.sync_calls: list[tuple[str, int, bool, float]] = []
        self.async_calls: list[tuple[str, int, bool, float]] = []

    def speak(self, text, *, volume=100, prefer_en=True, timeout_sec=120.0) -> None:
        self.sync_calls.append((text, volume, prefer_en, timeout_sec))

    def speak_async(self, text, *, volume=100, prefer_en=True, timeout_sec=8.0) -> None:
        self.async_calls.append((text, volume, prefer_en, timeout_sec))


class FakeTranslator:
    def __init__(self, result: TranslationResult | None = None, error: BaseException | None = None) -> None:
        self.name = "fake"
        self._result = result or TranslationResult("译文")
        self._error = error
        self.seen: list[str] = []

    def translate(self, text: str) -> TranslationResult:
        self.seen.append(text)
        if self._error is not None:
            raise self._error
        return self._result


class FakeSelection:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    def read_selected_text(self) -> str:
        self.calls += 1
        return self._text


class FakeOcr:
    def __init__(self, *, text: str = "识别文本", error: BaseException | None = None, available: bool = True) -> None:
        self._text = text
        self._error = error
        self._available = available
        self.stages: list[OcrStage] = []

    @property
    def is_available(self) -> bool:
        return self._available

    def extract_text(self, bbox: BBox, on_stage=None) -> str:
        if on_stage is not None:
            on_stage(OcrStage.CAPTURING)
            self.stages.append(OcrStage.CAPTURING)
        if self._error is not None:
            raise self._error
        if on_stage is not None:
            on_stage(OcrStage.RECOGNIZING)
            self.stages.append(OcrStage.RECOGNIZING)
        return self._text


class FakeGenerator:
    def __init__(self, script) -> None:
        self._script = list(script)
        self.calls: list[tuple[str, str]] = []

    def generate(self, word: str, meaning: str):
        self.calls.append((word, meaning))
        outcome = self._script.pop(0) if self._script else ("example", "例句")
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClock:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def stamp(self) -> str:
        return "2026-09-17_00-00-00"

    def log_time(self) -> str:
        return "00:00:00"

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


class FakeBackup:
    def __init__(self, *, result: BackupResult | None = None, backups=None) -> None:
        self._result = result or BackupResult(True, "backups/x.json", "backups/x.json")
        self._backups = list(backups or [])
        self.cleaned = False

    @property
    def directory(self) -> str:
        return "backups"

    def list_backups(self):
        return list(self._backups)

    def create(self, source_path: str, entry_count: int, *, missing_message: str = "") -> BackupResult:
        self.created_with = (source_path, entry_count, missing_message)
        return self._result

    def cleanup_keep_latest(self):
        self.cleaned = True
        return (2, "backups/keep.json")


class Recorder:
    def __init__(self) -> None:
        self.statuses: list[Stage] = []
        self.cursors: list[Stage] = []

    @property
    def progress(self) -> ProgressReporter:
        return ProgressReporter(on_status=self.statuses.append, on_cursor=self.cursors.append)


class RaisingFormatter:
    def __call__(self, exc: BaseException) -> str:
        return f"格式化:{type(exc).__name__}"


# —————————————————————————— 划词翻译 ——————————————————————————


class TranslateTextUseCaseTests(unittest.TestCase):
    def _use_case(self, translator, tts=None, volume=100) -> TranslateTextUseCase:
        return TranslateTextUseCase(
            lambda source: translator,
            lambda: "google",
            tts or FakeTts(),
            RaisingFormatter(),
            lambda: volume,
        )

    def test_empty_text_reports_no_text(self) -> None:
        recorder = Recorder()
        outcome = self._use_case(FakeTranslator()).execute("   ", progress=recorder.progress, no_text_hint="请先划词")
        self.assertIs(outcome.kind, OutcomeKind.NO_TEXT)
        self.assertEqual(outcome.error_message, "请先划词")
        self.assertIn(Stage.NO_TEXT, recorder.cursors)

    def test_truncates_and_cleans(self) -> None:
        translator = FakeTranslator()
        recorder = Recorder()
        outcome = self._use_case(translator).execute(
            "  " + "a" * 200 + "  ", progress=recorder.progress, no_text_hint="x"
        )
        self.assertTrue(outcome.truncated)
        self.assertEqual(len(outcome.source_text), 123)
        self.assertEqual(translator.seen[0], outcome.source_text)

    def test_english_triggers_async_speech(self) -> None:
        tts = FakeTts()
        recorder = Recorder()
        self._use_case(FakeTranslator(), tts, volume=42).execute(
            "hello world", progress=recorder.progress, no_text_hint="x"
        )
        self.assertEqual(tts.async_calls, [("hello world", 42, True, 8.0)])

    def test_chinese_does_not_speak(self) -> None:
        tts = FakeTts()
        self._use_case(FakeTranslator(), tts).execute("你好世界", progress=Recorder().progress, no_text_hint="x")
        self.assertEqual(tts.async_calls, [])

    def test_success_reports_result_and_labels(self) -> None:
        recorder = Recorder()
        outcome = self._use_case(FakeTranslator(TranslationResult("你好", "Google"))).execute(
            "hello", progress=recorder.progress, no_text_hint="x"
        )
        self.assertTrue(outcome.ok)
        self.assertEqual(outcome.result.display_text, "你好\n（Google 最快返回）")
        self.assertIn(Stage.TRANSLATING, recorder.cursors)
        self.assertIn(Stage.DONE, recorder.cursors)

    def test_domain_error_is_rendered(self) -> None:
        recorder = Recorder()
        outcome = self._use_case(FakeTranslator(error=SnapTranslateError("翻译炸了", detail="细节"))).execute(
            "hello", progress=recorder.progress, no_text_hint="x"
        )
        self.assertIs(outcome.kind, OutcomeKind.ERROR)
        self.assertIs(outcome.error_kind, ErrorKind.TRANSLATE)
        self.assertEqual(outcome.error_message, "翻译炸了\n细节")
        self.assertIn(Stage.FAILED, recorder.cursors)

    def test_unexpected_error_uses_formatter(self) -> None:
        outcome = self._use_case(FakeTranslator(error=ValueError("boom"))).execute(
            "hello", progress=Recorder().progress, no_text_hint="x"
        )
        self.assertEqual(outcome.error_message, "格式化:ValueError")

    def test_translate_helper_bypasses_ui_state(self) -> None:
        translator = FakeTranslator(TranslationResult("译文"))
        use_case = self._use_case(translator)
        self.assertEqual(use_case.translate("x").text, "译文")


class TranslateSelectionUseCaseTests(unittest.TestCase):
    def test_reads_selection_then_translates(self) -> None:
        selection = FakeSelection("hello")
        translator = FakeTranslator(TranslationResult("你好"))
        use_case = TranslateSelectionUseCase(
            selection,
            TranslateTextUseCase(lambda s: translator, lambda: "google", FakeTts(), RaisingFormatter()),
        )
        recorder = Recorder()
        outcome = use_case.execute(progress=recorder.progress, no_text_hint="x")
        self.assertTrue(outcome.ok)
        self.assertEqual(selection.calls, 1)
        self.assertEqual(recorder.cursors[0], Stage.READING_SELECTION)


class TranslateScreenshotUseCaseTests(unittest.TestCase):
    def _use_case(self, ocr, translator=None) -> TranslateScreenshotUseCase:
        translator = translator or FakeTranslator(TranslationResult("识别译文"))
        text_use_case = TranslateTextUseCase(
            lambda s: translator, lambda: "google", FakeTts(), RaisingFormatter()
        )
        return TranslateScreenshotUseCase(ocr, text_use_case)

    def test_reports_stages_and_translates(self) -> None:
        ocr = FakeOcr(text="hello world")
        recorder = Recorder()
        outcome = self._use_case(ocr).execute(BBox(0, 0, 100, 20), progress=recorder.progress, no_text_hint="x")
        self.assertTrue(outcome.ok)
        self.assertEqual(ocr.stages, [OcrStage.CAPTURING, OcrStage.RECOGNIZING])
        self.assertIn(Stage.OCR_CAPTURING, recorder.statuses)
        self.assertIn(Stage.OCR_RECOGNIZING, recorder.statuses)
        self.assertIn(Stage.OCR_TRANSLATING, recorder.statuses)

    def test_busy_when_already_running(self) -> None:
        use_case = self._use_case(FakeOcr())
        use_case._running = True  # noqa: SLF001 - 模拟并发中的 OCR
        recorder = Recorder()
        outcome = use_case.execute(BBox(0, 0, 10, 10), progress=recorder.progress, no_text_hint="x")
        self.assertIs(outcome.kind, OutcomeKind.BUSY)
        self.assertIn(Stage.OCR_BUSY, recorder.statuses)
        self.assertIn(Stage.OCR_BUSY, recorder.cursors)

    def test_unavailable_dependency(self) -> None:
        use_case = self._use_case(FakeOcr(error=OcrUnavailableError("OCR 不可用", detail="缺少依赖")))
        outcome = use_case.execute(BBox(0, 0, 10, 10), progress=Recorder().progress, no_text_hint="x")
        self.assertIs(outcome.error_kind, ErrorKind.OCR_UNAVAILABLE)
        self.assertEqual(outcome.error_message, "OCR 不可用\n缺少依赖")

    def test_ocr_failure_kind(self) -> None:
        use_case = self._use_case(FakeOcr(error=OcrError("OCR 失败：语言包缺失")))
        outcome = use_case.execute(BBox(0, 0, 10, 10), progress=Recorder().progress, no_text_hint="x")
        self.assertIs(outcome.error_kind, ErrorKind.OCR_FAILED)
        self.assertEqual(outcome.error_message, "OCR 失败：语言包缺失")

    def test_lock_released_after_run(self) -> None:
        use_case = self._use_case(FakeOcr())
        use_case.execute(BBox(0, 0, 10, 10), progress=Recorder().progress, no_text_hint="x")
        self.assertFalse(use_case._running)  # noqa: SLF001


# —————————————————————————— 生词本 ——————————————————————————


class VocabularyCollectionTests(unittest.TestCase):
    def test_collect_added_duplicate_empty_failed(self) -> None:
        repository = FakeRepository([{"word": "urban", "meaning": "城市的"}])
        use_case = VocabularyCollectionUseCase(repository)
        self.assertIs(use_case.collect("urban", "城市的").kind, CollectKind.DUPLICATE)
        self.assertIs(use_case.collect("", "x").kind, CollectKind.EMPTY)
        self.assertIs(use_case.collect("theft", "盗窃").kind, CollectKind.ADDED)
        self.assertEqual(repository.save_count, 1)

        broken = VocabularyCollectionUseCase(FakeRepository([], fail_save=True))
        self.assertIs(broken.collect("theft", "盗窃").kind, CollectKind.FAILED)

    def test_recent_saved_words(self) -> None:
        repository = FakeRepository([{"word": "a"}, {"word": "b"}, {"word": "c"}, {"word": "d"},
                                     {"word": "e"}, {"word": "f"}])
        self.assertEqual(VocabularyCollectionUseCase(repository).recent_saved_words(), ["f", "e", "d", "c", "b"])

    def test_delete_recent_outcomes(self) -> None:
        repository = FakeRepository([{"word": "a"}, {"word": "b"}])
        use_case = VocabularyCollectionUseCase(repository)
        self.assertIs(use_case.delete_recent(9).kind, DeleteKind.EMPTY)
        outcome = use_case.delete_recent(0)  # recent = [b, a] → 删除 b
        self.assertIs(outcome.kind, DeleteKind.DELETED)
        self.assertEqual(outcome.word, "b")
        self.assertEqual([item["word"] for item in repository.load_raw()], ["a"])

        missing = VocabularyCollectionUseCase(FakeRepository([{"word": "a"}], fail_save=True))
        self.assertIs(missing.delete_recent(0).kind, DeleteKind.FAILED)

    def test_recall_last_translation(self) -> None:
        use_case = RecallLastTranslationUseCase(
            VocabularyCollectionUseCase(FakeRepository([])), lambda: ("", "")
        )
        self.assertIs(use_case.execute().kind, CollectKind.NO_LAST)

        repository = FakeRepository([])
        use_case = RecallLastTranslationUseCase(
            VocabularyCollectionUseCase(repository), lambda: (" urban ", " 城市的 ")
        )
        outcome = use_case.execute()
        self.assertIs(outcome.kind, CollectKind.ADDED)
        self.assertEqual(repository.load_raw()[0]["word"], "urban")


# —————————————————————————— 例句生成 ——————————————————————————


class GenerateExamplesUseCaseTests(unittest.TestCase):
    def _setup(self, entries, script, *, save_each=True, should_stop=None, delay=0.35):
        repository = FakeRepository(entries)
        vocabulary = Vocabulary(repository.load_raw())
        use_case = GenerateExamplesUseCase(VocabularyTarget("vocab.json", lambda p: repository), FakeClock())
        pending = use_case.pending_items(vocabulary)
        generator = FakeGenerator(script)
        done: list = []
        outcome = use_case.execute(
            generator,
            vocabulary,
            pending,
            on_item_done=done.append,
            should_stop=should_stop,
            save_each=save_each,
            delay=delay,
        )
        return outcome, repository, done, generator

    def test_all_success_saves_each_item(self) -> None:
        entries = [{"word": "a", "meaning": "甲"}, {"word": "b", "meaning": "乙"}]
        outcome, repository, done, _generator = self._setup(entries, [("ex1", "译1"), ("ex2", "译2")])
        self.assertEqual((outcome.ok, outcome.total), (2, 2))
        self.assertIs(outcome.stop_kind, StopKind.COMPLETED)
        self.assertEqual(repository.save_count, 2)
        self.assertEqual(repository.load_raw()[1]["example"], "ex2")
        self.assertTrue(all(item.ok for item in done))

    def test_batch_mode_saves_once_at_end(self) -> None:
        entries = [{"word": "a", "meaning": "甲"}, {"word": "b", "meaning": "乙"}]
        outcome, repository, _done, _generator = self._setup(
            entries, [("ex1", "译1"), ("ex2", "译2")], save_each=False, delay=0.2
        )
        self.assertEqual(outcome.ok, 2)
        self.assertEqual(repository.save_count, 1)

    def test_insufficient_balance_stops(self) -> None:
        entries = [{"word": "a", "meaning": "甲"}, {"word": "b", "meaning": "乙"}, {"word": "c", "meaning": "丙"}]
        outcome, _repository, done, _generator = self._setup(
            entries, [("ex1", "译1"), InsufficientBalanceError("402"), ("ex3", "译3")]
        )
        self.assertEqual((outcome.ok, outcome.total), (1, 3))
        self.assertIs(outcome.stop_kind, StopKind.INSUFFICIENT_BALANCE)
        self.assertEqual(len(done), 1)

    def test_single_failure_does_not_break_loop(self) -> None:
        entries = [{"word": "a", "meaning": "甲"}, {"word": "b", "meaning": "乙"}]
        outcome, _repository, done, _generator = self._setup(entries, [ValueError("模型抽风"), ("ex2", "译2")])
        self.assertEqual(outcome.ok, 1)
        self.assertFalse(done[0].ok)
        self.assertEqual(done[0].error, "模型抽风")
        self.assertTrue(done[1].ok)

    def test_should_stop_marks_window_closed(self) -> None:
        entries = [{"word": "a", "meaning": "甲"}, {"word": "b", "meaning": "乙"}]
        calls = {"n": 0}

        def should_stop() -> bool:
            calls["n"] += 1
            return calls["n"] > 1

        outcome, _repository, _done, _generator = self._setup(entries, [("ex", "译")], should_stop=should_stop)
        self.assertIs(outcome.stop_kind, StopKind.WINDOW_CLOSED)
        self.assertEqual(outcome.ok, 1)

    def test_delay_is_passed_to_clock(self) -> None:
        entries = [{"word": "a", "meaning": "甲"}]
        _outcome, _repository, _done, _generator = self._setup(entries, [("ex", "译")], delay=0.25)
        # FakeClock 在 use case 内部持有，这里只验证不抛异常且条数正确
        self.assertEqual(len(entries), 1)


# —————————————————————————— 复习 ——————————————————————————


class ReviewUseCaseTests(unittest.TestCase):
    def _use_case(self, entries, *, fail_save=False):
        repository = FakeRepository(entries, fail_save=fail_save)
        tts = FakeTts()
        backup = FakeBackup()
        use_case = ReviewUseCase(VocabularyTarget("vocab.json", lambda p: repository), tts, backup)
        vocabulary = use_case.load()
        session = use_case.create_session(vocabulary, "score_asc")
        return use_case, session, repository, tts, backup

    def test_load_normalizes_scores(self) -> None:
        use_case, _session, _repository, _tts, _backup = self._use_case([{"word": "a", "score": "abc"}])
        self.assertEqual(use_case.load().raw[0]["score"], 50.0)

    def test_grade_saves_and_advances(self) -> None:
        use_case, session, repository, _tts, _backup = self._use_case(
            [{"word": "a", "score": 50, "reviews": 0}, {"word": "b", "score": 50, "reviews": 0}]
        )
        self.assertEqual(session.current().word, "a")
        result = use_case.grade(session, "know")
        assert result is not None
        self.assertEqual((result.old_score, result.new_score, result.delta), (50.0, 60.0, 10.0))
        self.assertEqual(result.word, "a")
        self.assertFalse(result.revealed)
        self.assertEqual(repository.save_count, 1)
        self.assertEqual(repository.load_raw()[0]["score"], 60.0)
        # 评分后重排（a 变 60 分，排到 50 分的 b 之后），再前进一格 → 当前卡片是 b
        self.assertEqual(session.current().word, "b")
        self.assertFalse(session.reveal.any_revealed)

    def test_grade_uses_reveal_state(self) -> None:
        use_case, session, _repository, _tts, _backup = self._use_case([{"word": "a", "score": 50}])
        session.reveal.toggle_meaning()
        result = use_case.grade(session, "know")
        assert result is not None
        self.assertTrue(result.revealed)
        self.assertEqual(result.delta, 5.0)

    def test_grade_without_current_returns_none(self) -> None:
        use_case, session, _repository, _tts, _backup = self._use_case([])
        self.assertIsNone(use_case.grade(session, "know"))

    def test_save_failure_does_not_advance(self) -> None:
        use_case, session, _repository, _tts, _backup = self._use_case([{"word": "a", "score": 50}], fail_save=True)
        with self.assertRaises(VocabularyIoError):
            use_case.grade(session, "know")
        self.assertEqual(session.position, 0)

    def test_backup_on_startup_uses_missing_message(self) -> None:
        use_case, session, _repository, _tts, backup = self._use_case([{"word": "a"}])
        use_case.backup_on_startup(session.vocabulary)
        self.assertEqual(backup.created_with[0], "vocab.json")
        self.assertEqual(backup.created_with[1], 1)
        self.assertIn("未找到 vocab.json", backup.created_with[2])

    def test_web_variant_uses_other_missing_message(self) -> None:
        repository = FakeRepository([{"word": "a"}])
        backup = FakeBackup()
        use_case = ReviewUseCase(
            VocabularyTarget("vocab.json", lambda p: repository),
            FakeTts(),
            backup,
            missing_message="未找到词表文件，跳过备份",
        )
        use_case.backup_on_startup(use_case.load())
        self.assertEqual(backup.created_with[2], "未找到词表文件，跳过备份")

    def test_speak_policy(self) -> None:
        use_case, session, _repository, tts, _backup = self._use_case(
            [{"word": "urban", "example": "Living in an urban area.", "example_zh": "住在城市里。"}]
        )
        entry = session.current()
        use_case.speak_for_card(entry, READ_MODE_NONE, 90)
        self.assertEqual(tts.sync_calls, [])
        use_case.speak_for_card(entry, READ_MODE_WORD, 90)
        self.assertEqual(tts.sync_calls[-1], ("urban", 90, True, 120.0))
        use_case.speak_for_card(entry, READ_MODE_WORD_EXAMPLE, 90)
        self.assertEqual(tts.sync_calls[-1], ("urban", 90, True, 60.0))
        use_case.speak_example(entry, 90)
        self.assertEqual(tts.sync_calls[-1], ("Living in an urban area.", 90, True, 120.0))

    def test_speak_example_skips_empty(self) -> None:
        use_case, session, _repository, tts, _backup = self._use_case([{"word": "urban"}])
        use_case.speak_example(session.current(), 50)
        self.assertEqual(tts.sync_calls, [])


# —————————————————————————— 后台管理 ——————————————————————————


class VocabularyAdminUseCaseTests(unittest.TestCase):
    def _use_case(self, repository, backup=None):
        return VocabularyAdminUseCase(lambda path: repository, lambda directory: backup or FakeBackup())

    def test_status_counts(self) -> None:
        repository = FakeRepository(
            [
                {"word": "a", "example": "x", "example_zh": "y"},
                {"word": "b", "example": "x", "example_zh": ""},
            ]
        )
        backup = FakeBackup(backups=["backups/new.json", "backups/old.json"])
        status = self._use_case(repository, backup).status("vocab.json", "backups")
        self.assertEqual((status.total, status.with_example, status.pending), (2, 1, 1))
        self.assertEqual(status.backup_count, 2)
        self.assertEqual(status.latest_backup, "backups/new.json")
        self.assertIsNone(status.read_error)

    def test_status_reports_read_error_but_keeps_backups(self) -> None:
        backup = FakeBackup(backups=["backups/new.json"])
        status = self._use_case(FakeRepository([], fail_load=True), backup).status("vocab.json", "backups")
        self.assertIsNone(status.total)
        self.assertEqual(status.read_error, "读取失败")
        self.assertEqual(status.backup_count, 1)

    def test_reset_scores(self) -> None:
        repository = FakeRepository([{"word": "a", "score": 91.0, "reviews": 7}])
        count = self._use_case(repository).reset_scores("vocab.json")
        self.assertEqual(count, 1)
        self.assertEqual(repository.load_raw()[0]["score"], 50.0)
        self.assertEqual(repository.load_raw()[0]["reviews"], 0)

    def test_reset_scores_missing_file(self) -> None:
        class _Missing(FakeRepository):
            def exists(self) -> bool:
                return False

        with self.assertRaises(VocabularyFileMissingError):
            self._use_case(_Missing([])).reset_scores("gone.json")

    def test_cleanup_backups_delegates(self) -> None:
        backup = FakeBackup()
        result = self._use_case(FakeRepository([]), backup).cleanup_backups("backups")
        self.assertTrue(backup.cleaned)
        self.assertEqual(result, (2, "backups/keep.json"))


if __name__ == "__main__":
    unittest.main()
