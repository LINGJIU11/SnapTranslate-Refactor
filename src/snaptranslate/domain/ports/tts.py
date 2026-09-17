"""语音朗读端口。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TextToSpeech(Protocol):
    """英文（或中文）朗读能力。

    - ``speak``：阻塞到朗读结束（复习窗口使用，原版超时 60/120 秒）；
    - ``speak_async``：后台线程朗读，不阻塞调用方（划词翻译窗口使用，原版超时 8 秒）。
    """

    def speak(self, text: str, *, volume: int = 100, prefer_en: bool = True, timeout_sec: float = 120.0) -> None:
        ...

    def speak_async(
        self, text: str, *, volume: int = 100, prefer_en: bool = True, timeout_sec: float = 8.0
    ) -> None:
        ...
