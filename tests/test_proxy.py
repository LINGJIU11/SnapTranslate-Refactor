"""代理层测试（KNOWN_ISSUES.md #1 的修复：请求层终于能走代理了）。

覆盖四件事：
1. 三种模式的解析与私有地址直连；
2. 代理连不上时**自动回退直连**（否则"跟随系统代理"会因 Clash 被关而拖死翻译）；
3. 设置往返（``main_settings.json`` 的 ``proxy_mode`` / ``proxy_url``）；
4. 翻译引擎确实把策略用上了。
"""

from __future__ import annotations

import unittest
from pathlib import Path

import requests

from snaptranslate.application.settings import TranslateSettingsUseCase
from snaptranslate.config.proxy import (
    MODE_CUSTOM,
    MODE_OFF,
    MODE_SYSTEM,
    PRESET_CLASH,
    PRESET_HONGKONG,
    normalize_proxy_url,
)
from snaptranslate.infrastructure.network.http import get as http_get
from snaptranslate.infrastructure.network.proxy_policy import ProxyPolicy, is_private_host
from snaptranslate.infrastructure.persistence.json_settings import JsonSettingsRepository
from snaptranslate.infrastructure.translation.cache import TranslationCache
from snaptranslate.infrastructure.translation.factory import build_translator
from tests._tmp import temp_dir


class NormalizeTests(unittest.TestCase):
    def test_adds_scheme_and_strips_slash(self) -> None:
        self.assertEqual(normalize_proxy_url("127.0.0.1:7897"), "http://127.0.0.1:7897")
        self.assertEqual(normalize_proxy_url("socks5://127.0.0.1:7897/"), "socks5://127.0.0.1:7897")
        self.assertEqual(normalize_proxy_url("   "), "")

    def test_presets_documented_in_config(self) -> None:
        self.assertEqual(PRESET_CLASH, "http://127.0.0.1:7897")
        self.assertTrue(PRESET_HONGKONG.startswith("http://10.8.0.6"))


class PrivateHostTests(unittest.TestCase):
    def test_private_and_public(self) -> None:
        for host in ("localhost", "127.0.0.1", "10.8.0.6", "192.168.1.5", "172.16.0.1", "172.31.255.9", "nas"):
            self.assertTrue(is_private_host(host), msg=host)
        for host in ("translate.googleapis.com", "clients5.google.com", "api.mymemory.translated.net", "8.8.8.8"):
            self.assertFalse(is_private_host(host), msg=host)


class ProxyPolicyTests(unittest.TestCase):
    def test_off_mode_is_direct(self) -> None:
        policy = ProxyPolicy(MODE_OFF)
        self.assertIsNone(policy.effective_url())
        self.assertIsNone(policy.proxies_for("translate.googleapis.com"))
        self.assertIn("直连", policy.describe())

    def test_system_mode_reads_windows_registry_value(self) -> None:
        policy = ProxyPolicy(MODE_SYSTEM, system_reader=lambda: "127.0.0.1:7897")
        self.assertEqual(policy.effective_url(), "http://127.0.0.1:7897")
        self.assertEqual(
            policy.proxies_for("translate.googleapis.com"),
            {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"},
        )

    def test_system_mode_without_registry_proxy_is_direct(self) -> None:
        policy = ProxyPolicy(MODE_SYSTEM, system_reader=lambda: None)
        self.assertIsNone(policy.effective_url())
        self.assertIn("系统未启用代理", policy.describe())

    def test_custom_mode(self) -> None:
        policy = ProxyPolicy(MODE_CUSTOM, "10.8.0.6:8080")
        self.assertEqual(policy.effective_url(), "http://10.8.0.6:8080")

    def test_invalid_mode_falls_back_to_off(self) -> None:
        policy = ProxyPolicy("nonsense")
        self.assertEqual(policy.mode, MODE_OFF)

    def test_private_hosts_bypass_proxy(self) -> None:
        policy = ProxyPolicy(MODE_CUSTOM, PRESET_CLASH)
        self.assertIsNone(policy.proxies_for("10.8.0.6"))
        self.assertIsNone(policy.proxies_for_url("http://10.8.0.1:8090/"))
        self.assertIsNotNone(policy.proxies_for_url("https://clients5.google.com/translate_a/t"))

    def test_reconfigure_takes_effect_immediately(self) -> None:
        policy = ProxyPolicy(MODE_OFF)
        policy.configure(MODE_CUSTOM, "127.0.0.1:7897")
        self.assertEqual(policy.effective_url(), "http://127.0.0.1:7897")
        policy.configure(MODE_OFF)
        self.assertIsNone(policy.effective_url())


class _FakeResponse:
    status_code = 200


class _FakeSession:
    """第一次调用抛 ProxyError，第二次成功；记录每次的 proxies。"""

    def __init__(self, *, fail_first: int = 1) -> None:
        self.calls: list[dict] = []
        self._fail_first = fail_first

    def get(self, url, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self._fail_first:
            raise requests.exceptions.ProxyError("proxy is dead")
        return _FakeResponse()

    def close(self) -> None:
        pass


class HttpFallbackTests(unittest.TestCase):
    def test_proxy_failure_falls_back_to_direct(self) -> None:
        session = _FakeSession()
        policy = ProxyPolicy(MODE_CUSTOM, PRESET_CLASH)

        response = http_get(
            "https://clients5.google.com/translate_a/t",
            timeout=(1, 2),
            policy=policy,
            session_factory=lambda: session,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[0]["proxies"], {"http": PRESET_CLASH, "https": PRESET_CLASH})
        self.assertEqual(session.calls[1]["proxies"], {}, "回退时必须真直连（空 dict + trust_env=False）")

    def test_direct_mode_uses_no_proxy(self) -> None:
        session = _FakeSession(fail_first=0)
        http_get("https://example.com", timeout=1, policy=ProxyPolicy(MODE_OFF), session_factory=lambda: session)
        self.assertIsNone(session.calls[0]["proxies"])

    def test_no_policy_means_no_proxy(self) -> None:
        session = _FakeSession(fail_first=0)
        http_get("https://example.com", timeout=1, session_factory=lambda: session)
        self.assertIsNone(session.calls[0]["proxies"])


class SettingsRoundTripTests(unittest.TestCase):
    def test_save_and_load_proxy(self) -> None:
        with temp_dir() as directory:
            repository = JsonSettingsRepository(str(Path(directory) / "main_settings.json"))
            use_case = TranslateSettingsUseCase(repository)
            self.assertEqual(use_case.load_proxy(), (MODE_OFF, ""))

            use_case.save_proxy(MODE_CUSTOM, "127.0.0.1:7897")
            self.assertEqual(use_case.load_proxy(), (MODE_CUSTOM, "http://127.0.0.1:7897"))
            # 不能把热键/音量这些同文件设置写丢
            use_case.save_tts_volume(66)
            use_case.save_hotkeys({"translate": "ctrl+f9", "snip": "tab+q", "save_last": "tab+e"})
            self.assertEqual(use_case.load_tts_volume(), 66)
            self.assertEqual(use_case.load_hotkeys()["translate"], "ctrl+f9")
            self.assertEqual(use_case.load_proxy()[0], MODE_CUSTOM)

    def test_invalid_mode_in_file_falls_back(self) -> None:
        with temp_dir() as directory:
            path = Path(directory) / "main_settings.json"
            path.write_text('{"proxy_mode": "weird", "proxy_url": "1.2.3.4:8080"}', encoding="utf-8")
            mode, url = TranslateSettingsUseCase(JsonSettingsRepository(str(path))).load_proxy()
            self.assertEqual(mode, MODE_OFF)
            self.assertEqual(url, "http://1.2.3.4:8080")


class EngineWiringTests(unittest.TestCase):
    """翻译引擎必须把策略传给 HTTP 层（否则界面上改了也没用）。"""

    def test_engines_receive_policy(self) -> None:
        policy = ProxyPolicy(MODE_CUSTOM, PRESET_CLASH)
        translator = build_translator("google", TranslationCache(), policy=policy)
        engines = [translator._gtx, translator._clients5, translator._mymemory, *translator._lingvas]  # noqa: SLF001
        for engine in engines:
            self.assertIs(engine._policy, policy, msg=type(engine).__name__)  # noqa: SLF001

    def test_mymemory_only_source_receives_policy(self) -> None:
        policy = ProxyPolicy(MODE_CUSTOM, PRESET_CLASH)
        translator = build_translator("mymemory", TranslationCache(), policy=policy)
        self.assertIs(translator._policy, policy)  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
