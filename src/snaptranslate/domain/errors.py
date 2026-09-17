"""领域错误。

原版用 ``except Exception`` + 直接 ``str(exc)`` 展示错误（见 ``main.py:307-325``）。
重构后仍然保留"把底层异常翻译成用户可读文案"的做法，但把文案生成收口到
infrastructure 的适配器里，应用层与表示层只消费 ``SnapTranslateError.message``。
"""

from __future__ import annotations


class SnapTranslateError(Exception):
    """本项目所有可预期错误的基类。"""

    def __init__(self, message: str, *, detail: str = "", cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.cause = cause

    def render(self) -> str:
        """表示层展示用文本：有 detail 时按原版习惯换行拼接。"""
        if self.detail:
            return f"{self.message}\n{self.detail}"
        return self.message


class TranslationError(SnapTranslateError):
    """翻译失败。``message`` 已是格式化后的用户可读文案。"""


class OcrError(SnapTranslateError):
    """OCR 不可用或识别失败。"""


class OcrUnavailableError(OcrError):
    """OCR 依赖不齐（缺少 pillow / pytesseract / Tesseract 本体）。

    原版在 ``main.py:1080-1090`` 用标题"OCR 不可用"区分于普通识别失败。
    """


class VocabularyIoError(SnapTranslateError):
    """词表读写失败。"""


class VocabularyFileMissingError(VocabularyIoError):
    """词表文件不存在（原 ``set.py:162-164`` 的"找不到词表文件"分支）。"""

    def __init__(self, path: str) -> None:
        super().__init__(f"找不到词表文件：{path}")
        self.path = path


class ExampleGenerationError(SnapTranslateError):
    """例句生成失败。"""


class InsufficientBalanceError(ExampleGenerationError):
    """DeepSeek 返回 402：账户余额不足（原版在两个界面各判断了一次）。"""


class MissingApiKeyError(ExampleGenerationError):
    """本地没有 API Key，需要表示层向用户索取（原版：桌面弹窗、Web 侧边栏警告）。"""

    def __init__(self) -> None:
        super().__init__("未配置 DeepSeek API Key")


class MissingDependencyError(ExampleGenerationError):
    """缺少可选依赖（原版检查 ``import openai`` 失败时提示安装）。"""

    def __init__(self, package: str, *, cause: BaseException | None = None) -> None:
        super().__init__(f"缺少依赖：{package}", cause=cause)
        self.package = package
