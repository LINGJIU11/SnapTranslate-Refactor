"""Windows 系统语音朗读适配器（原 ``main.py:1019-1041`` 与 ``vocab_review.py:636-659``）。

原版用 ``powershell -Command "Add-Type -AssemblyName System.Speech; ..."`` 朗读，
好处是零新增 Python 依赖，代价是每次朗读都要起一个 PowerShell 进程（见 KNOWN_ISSUES.md #6）。
重构**不改实现**，只是把这份脚本收拢到一处，并区分阻塞/异步两种用法。

**必须走 :func:`~snaptranslate.infrastructure.process.no_window.run_hidden`**：
打包成窗口程序后父进程没有控制台，直接 ``subprocess.run(["powershell", ...])``
会让 Windows 给 PowerShell 新分配一个控制台窗口——用户看到"翻译一下闪个黑框"
（KNOWN_ISSUES.md §八 N3，第一版打包的实际体验问题）。
"""

from __future__ import annotations

import subprocess
import threading

from snaptranslate.infrastructure.process.no_window import run_hidden


def build_speak_script(text: str, volume: int, prefer_en: bool) -> str:
    """生成 PowerShell 朗读脚本（与原版逐字一致，含单引号转义规则）。"""
    escaped = text.replace("'", "''")
    voice_filter = "en-*" if prefer_en else "zh-*"
    return (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Volume={max(0, min(100, int(volume)))}; "
        f"$voice=$s.GetInstalledVoices() | Where-Object {{$_.VoiceInfo.Culture.Name -like '{voice_filter}'}} | Select-Object -First 1; "
        "if($voice){$s.SelectVoice($voice.VoiceInfo.Name)}; "
        f"$s.Speak('{escaped}')"
    )


class WindowsSapiTts:
    """实现 :class:`~snaptranslate.domain.ports.tts.TextToSpeech`。"""

    def speak(
        self,
        text: str,
        *,
        volume: int = 100,
        prefer_en: bool = True,
        timeout_sec: float = 120.0,
    ) -> None:
        if not (text and str(text).strip()):
            return
        script = build_speak_script(str(text), volume, prefer_en)
        try:
            run_hidden(
                ["powershell", "-NoProfile", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout_sec,
                check=False,
            )
        except Exception:
            # 原版对朗读失败完全静默
            pass

    def speak_async(
        self,
        text: str,
        *,
        volume: int = 100,
        prefer_en: bool = True,
        timeout_sec: float = 8.0,
    ) -> None:
        if not (text and str(text).strip()):
            return
        threading.Thread(
            target=self.speak,
            args=(text,),
            kwargs={"volume": volume, "prefer_en": prefer_en, "timeout_sec": timeout_sec},
            daemon=True,
        ).start()
