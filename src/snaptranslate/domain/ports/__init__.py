"""端口（Protocol）：上层声明"我需要什么能力"，下层提供适配器实现。

依赖倒置的关键：``application`` 只 import 这里的 Protocol，
``infrastructure`` 提供实现，``bootstrap`` 负责装配（见 ARCHITECTURE.md §1）。
"""

from __future__ import annotations

from snaptranslate.domain.ports.api_key_store import ApiKeyStore
from snaptranslate.domain.ports.backup_writer import BackupResult, BackupWriter
from snaptranslate.domain.ports.clipboard import Clipboard
from snaptranslate.domain.ports.clock import Clock
from snaptranslate.domain.ports.example_generator import ExampleGenerator
from snaptranslate.domain.ports.hotkey_listener import HotkeyBindings, HotkeyCallbacks, HotkeyListener
from snaptranslate.domain.ports.ocr import OcrEngine, OcrStage, StageCallback
from snaptranslate.domain.ports.selection_reader import SelectionReader
from snaptranslate.domain.ports.settings_repository import SettingsRepository
from snaptranslate.domain.ports.translator import Translator
from snaptranslate.domain.ports.tts import TextToSpeech
from snaptranslate.domain.ports.vocabulary_repository import VocabularyRepository
from snaptranslate.domain.ports.window import WindowActivator

__all__ = [
    "ApiKeyStore",
    "BackupResult",
    "BackupWriter",
    "Clipboard",
    "Clock",
    "ExampleGenerator",
    "HotkeyBindings",
    "HotkeyCallbacks",
    "HotkeyListener",
    "OcrEngine",
    "OcrStage",
    "SelectionReader",
    "SettingsRepository",
    "StageCallback",
    "TextToSpeech",
    "Translator",
    "VocabularyRepository",
    "WindowActivator",
]
