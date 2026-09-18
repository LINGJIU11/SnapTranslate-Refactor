"""应用层向表示层暴露的依赖包（bundle）。

表示层只 import ``application``，因此"要用哪些用例"这一契约放在这里；
``bootstrap`` 负责把真实实现填进来（见 ARCHITECTURE.md §2.6）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from snaptranslate.application.generate_examples import GenerateExamplesUseCase
from snaptranslate.domain.models.launcher import LauncherAppItem
from snaptranslate.application.review import ReviewUseCase
from snaptranslate.application.settings import ReviewSettingsUseCase, TranslateSettingsUseCase
from snaptranslate.application.translate_input import TranslateInputUseCase
from snaptranslate.application.translate_screenshot import TranslateScreenshotUseCase
from snaptranslate.application.translate_selection import TranslateSelectionUseCase
from snaptranslate.application.translate_text import TranslateTextUseCase
from snaptranslate.application.vocabulary_admin import VocabularyAdminUseCase
from snaptranslate.application.vocabulary_collection import (
    RecallLastTranslationUseCase,
    VocabularyCollectionUseCase,
)
from snaptranslate.domain.ports.api_key_store import ApiKeyStore
from snaptranslate.domain.ports.app_launcher import AppLauncher
from snaptranslate.domain.ports.backup_writer import BackupResult
from snaptranslate.domain.ports.example_generator import ExampleGenerator
from snaptranslate.domain.ports.hotkey_listener import HotkeyListener
from snaptranslate.domain.ports.input_watcher import InputWatcher
from snaptranslate.domain.ports.log_sink import LogSink
from snaptranslate.domain.ports.pointer import Pointer
from snaptranslate.domain.ports.proxy import ProxySettings
from snaptranslate.domain.ports.tray import TrayIcon
from snaptranslate.domain.ports.window import WindowActivator

#: 翻译源取值提供者（读界面单选框）
SourceProvider = Callable[[], str]
#: 朗读音量提供者（读界面滑块）
VolumeProvider = Callable[[], int]
#: "最近一条翻译"提供者（读界面状态，返回 (原文, 译文)）
LastTranslationProvider = Callable[[], tuple[str, str]]

#: 构造"文本翻译用例"的工厂：需要界面提供的两个取值回调
TranslateTextFactory = Callable[[SourceProvider, VolumeProvider], TranslateTextUseCase]
SelectionUseCaseFactory = Callable[[SourceProvider, VolumeProvider], TranslateSelectionUseCase]
ScreenshotUseCaseFactory = Callable[[SourceProvider, VolumeProvider], TranslateScreenshotUseCase]
#: 新增功能：中译英输入框（只需要"当前翻译源"，与朗读音量无关）
InputUseCaseFactory = Callable[[SourceProvider], TranslateInputUseCase]
RecallLastFactory = Callable[[LastTranslationProvider], RecallLastTranslationUseCase]
#: 构造例句生成器（可指定 API Key 文件路径；无 key 时抛 MissingApiKeyError，由表示层弹窗/警告）
ExampleGeneratorFactory = Callable[[str | None], ExampleGenerator]


@dataclass(frozen=True)
class TranslateAppDeps:
    """划词翻译窗口（``main.py``）所需的全部依赖。"""

    settings: TranslateSettingsUseCase
    collection: VocabularyCollectionUseCase
    recall_last_factory: RecallLastFactory
    translate_text_factory: TranslateTextFactory
    selection_usecase_factory: SelectionUseCaseFactory
    screenshot_usecase_factory: ScreenshotUseCaseFactory
    #: 新增功能：中译英输入框用例
    input_usecase_factory: InputUseCaseFactory
    hotkey_listener: HotkeyListener
    window_activator: WindowActivator
    #: 取鼠标位置（悬浮卡片以"热键按下瞬间"的位置为锚点，见 KNOWN_ISSUES.md #23）
    pointer: Pointer
    #: 监听"任意键 / 鼠标左右键"（悬浮卡片不再定时消失，见 KNOWN_ISSUES.md #24）
    input_watcher: InputWatcher
    #: 代理设置（界面可改、请求层即时生效，见 KNOWN_ISSUES.md #25）
    proxy_policy: ProxySettings
    #: 代理自检：``probe(url) -> (是否可用, 说明)``（界面"测试"按钮用）
    proxy_probe: Callable[[str], tuple[bool, str]]
    #: 日志出口（写控制台 + 数据目录里的日志文件；打包后没有控制台）
    log_sink: LogSink
    startup_backup: Callable[[], BackupResult]
    vocab_path: str


@dataclass(frozen=True)
class LauncherAppDeps:
    """启动器控制台（**新增功能**：一个入口管三个窗口 + 托盘常驻）。"""

    #: 可启动/唤起的子应用清单（由 bootstrap 用界面标题与命令行参数填好）
    apps: tuple[LauncherAppItem, ...]
    #: 启动/唤起/结束子应用
    launcher: AppLauncher
    #: 托盘图标（注册失败时为"未注册"状态，面板仍然可用）
    tray: TrayIcon
    #: 数据目录（面板显示 + "打开数据目录"按钮）
    data_dir: str
    #: 托盘/exe 图标文件；不存在时适配器会退回系统默认图标
    icon_path: str
    #: 当前划词热键标签（面板上显示一行，方便用户知道自己按什么）
    hotkey_label: str


@dataclass(frozen=True)
class ReviewAppDeps:
    """生词复习（桌面端 ``vocab_review.py``）。"""

    review: ReviewUseCase
    examples: GenerateExamplesUseCase
    settings: ReviewSettingsUseCase
    api_key_store: ApiKeyStore
    generator_factory: ExampleGeneratorFactory
    vocab_path: str


@dataclass(frozen=True)
class WebReviewDeps:
    """生词复习（Web 端 ``vocab_review_web.py``）。"""

    review: ReviewUseCase
    examples: GenerateExamplesUseCase
    api_key_store: ApiKeyStore
    api_key_store_factory: Callable[[str], ApiKeyStore]
    generator_factory: ExampleGeneratorFactory
    vocab_path: str
    api_key_path: str
    backup_dir: str


@dataclass(frozen=True)
class AdminAppDeps:
    """词表后台管理（``set.py``）。"""

    admin: VocabularyAdminUseCase
    vocab_path: str
    backup_dir: str
