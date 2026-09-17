"""诊断脚本：演示"划词返回网址"这个 bug 的机理与修复效果（只读，不改任何代码）。

背景：原版取词只看"剪贴板内容有没有变"，内容没变时不报错，直接把剪贴板里的旧内容
（例如上次复制的网址）当原文翻译 → 用户看到 `网址 => 网址`。

现在改为看**剪贴板版本号**：只要真的发生了一次复制，版本号必然变化。

    python scripts/diagnose_url_capture.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from snaptranslate.application.progress import ProgressReporter  # noqa: E402
from snaptranslate.application.translate_selection import TranslateSelectionUseCase  # noqa: E402
from snaptranslate.application.translate_text import TranslateTextUseCase  # noqa: E402
from snaptranslate.infrastructure.input.win32_selection import Win32SelectionReader  # noqa: E402
from snaptranslate.infrastructure.system_clock import SystemClock  # noqa: E402
from snaptranslate.infrastructure.translation.cache import TranslationCache  # noqa: E402
from snaptranslate.infrastructure.translation.errors import RequestsErrorFormatter  # noqa: E402
from snaptranslate.infrastructure.translation.factory import build_racing_translator  # noqa: E402
from snaptranslate.infrastructure.tts.windows_sapi import WindowsSapiTts  # noqa: E402

URL = "https://code.visualstudio.com/updates/v1_138"
SENTENCE = "The quick brown fox jumps over the lazy dog."


class FakeClipboard:
    """可控剪贴板；``simulate_copy`` 表示目标应用真的把选区写进了剪贴板。"""

    def __init__(self, text: str, sequence: int = 100) -> None:
        self.text = text
        self._sequence = sequence
        self.reads = 0

    def read_text(self) -> str:
        self.reads += 1
        return self.text

    def sequence(self) -> int:
        return self._sequence

    def simulate_copy(self, text: str) -> None:
        self.text = text
        self._sequence += 1


class FakeUser32:
    """按键照发；``on_ctrl_c=None`` 表示目标应用毫无反应（复制失败）。"""

    def __init__(self, on_ctrl_c=None) -> None:
        self._on_ctrl_c = on_ctrl_c
        self.events = 0

    def keybd_event(self, *args) -> None:
        self.events += 1
        if self.events % 4 == 3 and self._on_ctrl_c is not None:
            self._on_ctrl_c()


def capture(clipboard_text: str, *, copy_succeeds: bool, copied_text: str = "") -> tuple[object, FakeClipboard]:
    clipboard = FakeClipboard(clipboard_text)
    user32 = FakeUser32((lambda: clipboard.simulate_copy(copied_text)) if copy_succeeds else None)
    reader = Win32SelectionReader(clipboard, user32=user32, clock=SystemClock(), copy_delay=0.0, stable_wait=0.0)
    return reader.read_selected_text(), clipboard


def translator():
    racing = build_racing_translator(TranslationCache())
    for engine in (racing._gtx, racing._clients5, racing._mymemory):  # noqa: SLF001 - 诊断用，缩短超时
        engine._timeout = (4, 10)  # noqa: SLF001
        engine._retries = 1  # noqa: SLF001
    return racing


def main() -> int:
    print("=== 场景 1：Ctrl+C 没生效，而剪贴板里躺着上次复制的网址（你遇到的情况）===")
    capture_result, clipboard = capture(URL, copy_succeeds=False)
    print(f"  剪贴板内容      : {clipboard.text!r}（读取 {clipboard.reads} 次）")
    print(f"  新版取词结果    : copied={capture_result.copied}  text={capture_result.text!r}")
    print(f"  旧版会怎么做    : 内容没变也算「取到了」，于是把 {URL[:38]}… 当原文送去翻译")
    print("  → 新版在此直接判定取词失败，**不翻译**，并提示原因（见下面的用例输出）\n")

    use_case = TranslateSelectionUseCaseStub(capture_result)
    outcome = use_case.execute(
        progress=ProgressReporter(),
        no_text_hint="未检测到选中文本",
        capture_failed_hint="取词失败：模拟 Ctrl+C 没有生效，本次已放弃翻译（没有拿剪贴板里的旧内容顶替）。",
    )
    print(f"  用例返回值      : kind={outcome.kind.value}  capture_failed={outcome.capture_failed}")
    print(f"  送给翻译器的原文: {outcome.source_text!r}（空 = 没有翻译任何东西）")
    print(f"  界面提示        : {outcome.error_message}\n")

    print("=== 场景 2：Ctrl+C 生效（正常划词）===")
    capture_result, clipboard = capture("旧内容", copy_succeeds=True, copied_text=SENTENCE)
    print(f"  新版取词结果    : copied={capture_result.copied}  text={capture_result.text!r}")
    text_use_case = TranslateTextUseCase(
        lambda source: translator(), lambda: "google", WindowsSapiTts(), RequestsErrorFormatter(), lambda: 0
    )
    result = text_use_case.execute(capture_result.text, progress=ProgressReporter(), no_text_hint="x")
    if result.result is not None:
        print(f"  翻译返回        : {result.result.text!r}")
        print(f"  界面展示        : {result.result.display_text!r}")
    else:
        print(f"  翻译失败        : {result.error_message}")
    print("\n=== 场景 3：网址被有意送进翻译器时（对照，说明「翻译源对网址原样返回」）===")
    translate_url = TranslateTextUseCase(
        lambda source: translator(), lambda: "google", WindowsSapiTts(), RequestsErrorFormatter(), lambda: 0
    ).execute(URL, progress=ProgressReporter(), no_text_hint="x")
    if translate_url.result is not None:
        print(f"  翻译返回        : {translate_url.result.text!r}")
    return 0


class TranslateSelectionUseCaseStub(TranslateSelectionUseCase):
    """把已经取好的结果喂给真实用例（跳过真实取词）。"""

    def __init__(self, capture_result) -> None:
        class _Reader:
            def read_selected_text(self):
                return capture_result

        super().__init__(_Reader(), TranslateTextUseCase(
            lambda source: translator(), lambda: "google", WindowsSapiTts(), RequestsErrorFormatter(), lambda: 0
        ))


if __name__ == "__main__":
    raise SystemExit(main())
