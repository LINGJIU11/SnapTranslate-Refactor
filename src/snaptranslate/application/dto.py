"""用例的输入/输出数据结构。

原版用例直接把结果写进 Tk 变量或 ``st.success``；这里改为返回值对象，
由表示层决定文案与呈现方式（UI 文案统一放在 ``presentation/texts.py``）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from snaptranslate.domain.models.review import Grade, GradeResult
from snaptranslate.domain.models.translation import TranslationResult


class OutcomeKind(str, Enum):
    """翻译类用例的结果类型。"""

    OK = "ok"
    NO_TEXT = "no_text"
    BUSY = "busy"
    ERROR = "error"


class ErrorKind(str, Enum):
    """错误归属（表示层据此选标题，例如"OCR 失败"/"OCR 不可用"）。"""

    TRANSLATE = "translate"
    OCR_FAILED = "ocr_failed"
    OCR_UNAVAILABLE = "ocr_unavailable"


@dataclass(frozen=True)
class TranslationOutcome:
    """一次"文本→中文"翻译的结果。"""

    kind: OutcomeKind
    source_text: str = ""
    result: TranslationResult | None = None
    truncated: bool = False
    error_kind: ErrorKind | None = None
    error_message: str | None = None
    #: 取词阶段失败（Ctrl+C 未生效）——用于让表示层给出针对性的提示与调试输出
    capture_failed: bool = False

    @property
    def ok(self) -> bool:
        return self.kind is OutcomeKind.OK


class CollectKind(str, Enum):
    """收录生词本的结果类型（对应原版四种提示）。"""

    ADDED = "added"
    DUPLICATE = "duplicate"
    EMPTY = "empty"
    FAILED = "failed"
    NO_LAST = "no_last"


@dataclass(frozen=True)
class CollectOutcome:
    kind: CollectKind
    word: str = ""


class DeleteKind(str, Enum):
    DELETED = "deleted"
    NOT_FOUND = "not_found"
    EMPTY = "empty"
    FAILED = "failed"


@dataclass(frozen=True)
class DeleteOutcome:
    kind: DeleteKind
    word: str = ""


@dataclass(frozen=True)
class AdminStatus:
    """词表后台管理的状态面板（原 ``set.py:refresh_status``）。"""

    total: int | None = None
    with_example: int | None = None
    pending: int | None = None
    backup_count: int = 0
    latest_backup: str | None = None
    read_error: str | None = None


class StopKind(str, Enum):
    """批量生成例句的终止原因。"""

    COMPLETED = "completed"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    WINDOW_CLOSED = "window_closed"


@dataclass(frozen=True)
class ExampleItemResult:
    """单条例句生成的结果（用于逐条日志）。"""

    order: int
    total: int
    word: str
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class GenerateOutcome:
    ok: int
    total: int
    stop_kind: StopKind = StopKind.COMPLETED


@dataclass(frozen=True)
class GradeOutcome:
    """评分用例的返回（包装领域层 :class:`GradeResult`，并附带是否落盘成功）。"""

    result: GradeResult
    grade: Grade
