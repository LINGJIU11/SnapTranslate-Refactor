"""用例：界面设置的读取与保存。

两个设置文件的写入语义不同（见 ARCHITECTURE.md §4.3），因此分成两个用例类，
分别封装原 ``main.py`` 的"合并写"与 ``vocab_review.py`` 的"覆盖写"。
"""

from __future__ import annotations

from typing import Any, Mapping

from snaptranslate.config.proxy import DEFAULT_MODE, MODES, normalize_proxy_url
from snaptranslate.domain.models.hotkey import Hotkey, feature_hotkeys, normalize

#: 当前程序完整的默认热键（原版三组 + 新增的输入框一组）；老设置文件缺 ``input`` 时用它补齐
FEATURE_HOTKEYS = feature_hotkeys()
from snaptranslate.domain.ports.settings_repository import SettingsRepository

DEFAULT_TTS_VOLUME = 100


class TranslateSettingsUseCase:
    """``main_settings.json``：热键 + 朗读音量（合并写入，保留其它键）。"""

    def __init__(self, repository: SettingsRepository, defaults: Mapping[str, str] | None = None) -> None:
        self._repository = repository
        self._defaults = dict(defaults or FEATURE_HOTKEYS)

    def load_hotkeys(self) -> dict[str, str]:
        """原 ``_load_hotkeys``：非法或缺失的组合回退默认值。"""
        data = self._repository.read()
        got = data.get("hotkeys")
        if not isinstance(got, dict):
            return dict(self._defaults)
        result = dict(self._defaults)
        for key in result:
            value = got.get(key)
            if isinstance(value, str) and Hotkey.parse(value) is not None:
                result[key] = normalize(value)
        return result

    def save_hotkeys(self, hotkeys: Mapping[str, str]) -> None:
        """原 ``_save_hotkeys``：写失败静默（不打断界面操作）。"""
        try:
            self._repository.merge({"hotkeys": dict(hotkeys)})
        except Exception:
            pass

    def load_tts_volume(self) -> int:
        data = self._repository.read()
        try:
            value = int(data.get("tts_volume", DEFAULT_TTS_VOLUME))
        except Exception:
            value = DEFAULT_TTS_VOLUME
        return max(0, min(100, value))

    def save_tts_volume(self, volume: int) -> None:
        value = max(0, min(100, int(volume)))
        try:
            self._repository.merge({"tts_volume": value})
        except Exception:
            pass

    def read_all(self) -> dict[str, Any]:
        return self._repository.read()

    # —— 代理（KNOWN_ISSUES.md #25）——

    def load_proxy(self) -> tuple[str, str]:
        """读回 ``(mode, url)``；非法值回退"直连"。"""
        data = self._repository.read()
        mode = str(data.get("proxy_mode", DEFAULT_MODE) or DEFAULT_MODE).strip().lower()
        if mode not in MODES:
            mode = DEFAULT_MODE
        url = normalize_proxy_url(str(data.get("proxy_url", "") or ""))
        return mode, url

    def save_proxy(self, mode: str, url: str) -> None:
        """写失败静默（与其它设置一致，不打断界面操作）。"""
        try:
            self._repository.merge(
                {"proxy_mode": mode if mode in MODES else DEFAULT_MODE, "proxy_url": normalize_proxy_url(url)}
            )
        except Exception:
            pass


class ReviewSettingsUseCase:
    """``vocab_review_settings.json``：朗读音量（**整体覆盖**写，原版如此）。"""

    def __init__(self, repository: SettingsRepository) -> None:
        self._repository = repository

    def load_tts_volume(self) -> int:
        data = self._repository.read()
        try:
            value = int(data.get("tts_volume", DEFAULT_TTS_VOLUME))
        except Exception:
            value = DEFAULT_TTS_VOLUME
        return max(0, min(100, value))

    def save_tts_volume(self, volume: int) -> None:
        self._repository.replace({"tts_volume": max(0, min(100, int(volume)))})
