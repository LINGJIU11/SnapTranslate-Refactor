"""组合根：把配置 + 适配器 + 用例装配成表示层可直接使用的依赖包。

唯一 import 全部层的地方（见 ARCHITECTURE.md §2.6）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from snaptranslate.application.deps import (
    AdminAppDeps,
    ReviewAppDeps,
    TranslateAppDeps,
    WebReviewDeps,
)
from snaptranslate.application.backup import BackupVocabularyUseCase
from snaptranslate.application.generate_examples import GenerateExamplesUseCase
from snaptranslate.application.review import DESKTOP_MISSING_MESSAGE, WEB_MISSING_MESSAGE, ReviewUseCase
from snaptranslate.application.settings import ReviewSettingsUseCase, TranslateSettingsUseCase
from snaptranslate.application.translate_screenshot import TranslateScreenshotUseCase
from snaptranslate.application.translate_selection import TranslateSelectionUseCase
from snaptranslate.application.translate_text import TranslateTextUseCase
from snaptranslate.application.vocabulary_admin import VocabularyAdminUseCase
from snaptranslate.application.vocabulary_collection import (
    RecallLastTranslationUseCase,
    VocabularyCollectionUseCase,
)
from snaptranslate.application.vocabulary_target import VocabularyTarget
from snaptranslate.config import paths as config_paths
from snaptranslate.domain.ports.api_key_store import ApiKeyStore
from snaptranslate.domain.ports.backup_writer import BackupWriter
from snaptranslate.domain.ports.clock import Clock
from snaptranslate.domain.ports.example_generator import ExampleGenerator
from snaptranslate.domain.ports.hotkey_listener import HotkeyListener
from snaptranslate.domain.ports.ocr import OcrEngine
from snaptranslate.domain.ports.translator import Translator
from snaptranslate.domain.ports.tts import TextToSpeech
from snaptranslate.domain.ports.vocabulary_repository import VocabularyRepository
from snaptranslate.infrastructure.input.win32_clipboard import PyperclipClipboard
from snaptranslate.infrastructure.input.win32_hotkeys import Win32PollingHotkeyListener
from snaptranslate.infrastructure.input.win32_selection import Win32SelectionReader
from snaptranslate.infrastructure.input.win32_window import Win32WindowActivator
from snaptranslate.infrastructure.llm.deepseek import DeepSeekExampleGenerator
from snaptranslate.infrastructure.ocr.tesseract import TesseractOcrEngine
from snaptranslate.infrastructure.persistence.api_key_file import FileApiKeyStore
from snaptranslate.infrastructure.persistence.backup import FileBackupWriter
from snaptranslate.infrastructure.persistence.json_settings import JsonSettingsRepository
from snaptranslate.infrastructure.persistence.json_vocabulary import JsonVocabularyRepository
from snaptranslate.infrastructure.system_clock import SystemClock
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.errors import RequestsErrorFormatter
from snaptranslate.infrastructure.translation.factory import build_translator
from snaptranslate.infrastructure.tts.windows_sapi import WindowsSapiTts


@dataclass(frozen=True)
class DataPaths:
    """一套数据文件位置（默认取自 ``config.paths``，即工程根目录）。"""

    vocab: str
    api_key: str
    translate_settings: str
    review_settings: str
    backups: str

    @classmethod
    def default(cls) -> "DataPaths":
        return cls(
            vocab=config_paths.vocab_path(),
            api_key=config_paths.api_key_path(),
            translate_settings=config_paths.translate_settings_path(),
            review_settings=config_paths.review_settings_path(),
            backups=config_paths.backup_dir(),
        )

    @classmethod
    def under(cls, directory: str) -> "DataPaths":
        base = Path(directory)
        return cls(
            vocab=str(base / config_paths.VOCAB_FILENAME),
            api_key=str(base / config_paths.API_KEY_FILENAME),
            translate_settings=str(base / config_paths.TRANSLATE_SETTINGS_FILENAME),
            review_settings=str(base / config_paths.REVIEW_SETTINGS_FILENAME),
            backups=str(base / config_paths.BACKUP_DIRNAME),
        )


class Container:
    """依赖容器。"""

    def __init__(self, paths: DataPaths | None = None, clock: Clock | None = None) -> None:
        self.paths = paths or DataPaths.default()
        self.clock: Clock = clock or SystemClock()
        self._cache = TranslationCache()
        self._tts: TextToSpeech = WindowsSapiTts()
        self._ocr: OcrEngine = TesseractOcrEngine()
        self._clipboard = PyperclipClipboard()
        self._selection = Win32SelectionReader(self._clipboard, clock=self.clock)
        self._window_activator = Win32WindowActivator()
        self._error_formatter = RequestsErrorFormatter()

    # —————————————— 基础设施 ——————————————
    def translator(self, source: str) -> Translator:
        """按翻译源构造翻译器（共享同一个进程内缓存，等价于原版模块级缓存）。"""
        return build_translator(source, self._cache)

    def tts(self) -> TextToSpeech:
        return self._tts

    def ocr_engine(self) -> OcrEngine:
        return self._ocr

    def vocabulary_repository(self, path: str | None = None) -> VocabularyRepository:
        return JsonVocabularyRepository(path or self.paths.vocab)

    def backup_writer(self, directory: str | None = None) -> BackupWriter:
        return FileBackupWriter(directory or self.paths.backups, self.clock)

    def api_key_store(self, path: str | None = None) -> ApiKeyStore:
        return FileApiKeyStore(path or self.paths.api_key)

    def translate_settings(self) -> TranslateSettingsUseCase:
        return TranslateSettingsUseCase(JsonSettingsRepository(self.paths.translate_settings))

    def review_settings(self) -> ReviewSettingsUseCase:
        return ReviewSettingsUseCase(JsonSettingsRepository(self.paths.review_settings))

    def example_generator(self, key_path: str | None = None) -> ExampleGenerator:
        return DeepSeekExampleGenerator(self.api_key_store(key_path))

    def hotkey_listener(self) -> HotkeyListener:
        """原版实际生效的轮询式监听器（``RegisterHotKey`` 那套从未启动，见 KNOWN_ISSUES.md #1）。"""
        return Win32PollingHotkeyListener()

    def vocabulary_target(self, path: str | None = None) -> VocabularyTarget:
        return VocabularyTarget(path or self.paths.vocab, self.vocabulary_repository)

    # —————————————— 用例 ——————————————
    def translate_text_use_case(self, source_provider, tts_volume_provider) -> TranslateTextUseCase:
        return TranslateTextUseCase(
            self.translator,
            source_provider,
            self._tts,
            self._error_formatter,
            tts_volume_provider,
        )

    def translate_selection_use_case(self, source_provider, tts_volume_provider) -> TranslateSelectionUseCase:
        return TranslateSelectionUseCase(
            self._selection,
            self.translate_text_use_case(source_provider, tts_volume_provider),
        )

    def translate_screenshot_use_case(self, source_provider, tts_volume_provider) -> TranslateScreenshotUseCase:
        return TranslateScreenshotUseCase(
            self._ocr,
            self.translate_text_use_case(source_provider, tts_volume_provider),
        )

    def vocabulary_collection_use_case(self, path: str | None = None) -> VocabularyCollectionUseCase:
        return VocabularyCollectionUseCase(self.vocabulary_repository(path))

    def review_use_case(self, path: str | None = None, *, web: bool = False) -> ReviewUseCase:
        return ReviewUseCase(
            self.vocabulary_target(path),
            self._tts,
            self.backup_writer(),
            missing_message=WEB_MISSING_MESSAGE if web else DESKTOP_MISSING_MESSAGE,
        )

    def generate_examples_use_case(self, target: VocabularyTarget | None = None) -> GenerateExamplesUseCase:
        return GenerateExamplesUseCase(target or self.vocabulary_target(), self.clock)

    def vocabulary_admin_use_case(self) -> VocabularyAdminUseCase:
        return VocabularyAdminUseCase(self.vocabulary_repository, lambda directory: self.backup_writer(directory))

    # —————————————— 依赖包（交给表示层） ——————————————
    def translate_app_deps(self) -> TranslateAppDeps:
        collection = self.vocabulary_collection_use_case()
        return TranslateAppDeps(
            settings=self.translate_settings(),
            collection=collection,
            recall_last_factory=lambda provider: RecallLastTranslationUseCase(collection, provider),
            translate_text_factory=self.translate_text_use_case,
            selection_usecase_factory=self.translate_selection_use_case,
            screenshot_usecase_factory=self.translate_screenshot_use_case,
            hotkey_listener=self.hotkey_listener(),
            window_activator=self._window_activator,
            startup_backup=BackupVocabularyUseCase(
                self.vocabulary_repository(), self.backup_writer()
            ).execute,
            vocab_path=self.paths.vocab,
        )

    def review_app_deps(self) -> ReviewAppDeps:
        target = self.vocabulary_target()
        return ReviewAppDeps(
            review=ReviewUseCase(target, self._tts, self.backup_writer(), missing_message=DESKTOP_MISSING_MESSAGE),
            examples=GenerateExamplesUseCase(target, self.clock),
            settings=self.review_settings(),
            api_key_store=self.api_key_store(),
            generator_factory=self.example_generator,
            vocab_path=target.path,
        )

    def web_review_deps(self) -> WebReviewDeps:
        target = self.vocabulary_target()
        return WebReviewDeps(
            review=ReviewUseCase(target, self._tts, self.backup_writer(), missing_message=WEB_MISSING_MESSAGE),
            examples=GenerateExamplesUseCase(target, self.clock),
            api_key_store=self.api_key_store(),
            api_key_store_factory=self.api_key_store,
            generator_factory=self.example_generator,
            vocab_path=target.path,
            api_key_path=self.paths.api_key,
            backup_dir=self.paths.backups,
        )

    def admin_app_deps(self) -> AdminAppDeps:
        return AdminAppDeps(
            admin=self.vocabulary_admin_use_case(),
            vocab_path=self.paths.vocab,
            backup_dir=self.paths.backups,
        )
