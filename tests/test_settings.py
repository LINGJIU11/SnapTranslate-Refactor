"""设置仓储与用例测试（合并写 vs 覆盖写）。"""

from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from pathlib import Path

from snaptranslate.application.settings import ReviewSettingsUseCase, TranslateSettingsUseCase
from snaptranslate.domain.models.hotkey import DEFAULT_HOTKEYS, feature_hotkeys
from snaptranslate.infrastructure.persistence.api_key_file import FileApiKeyStore
from snaptranslate.infrastructure.persistence.json_settings import JsonSettingsRepository
from tests._tmp import nonexistent_path, temp_dir


@contextmanager
def settings_file(payload=None):
    with temp_dir() as directory:
        path = directory / "settings.json"
        if payload is not None:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        yield path


class SettingsRepositoryTests(unittest.TestCase):
    def test_read_missing_or_broken(self) -> None:
        with settings_file() as path:
            self.assertEqual(JsonSettingsRepository(str(path)).read(), {})
        with temp_dir() as directory:
            broken = directory / "broken.json"
            broken.write_text("{ broken", encoding="utf-8")
            self.assertEqual(JsonSettingsRepository(str(broken)).read(), {})

    def test_merge_keeps_other_keys(self) -> None:
        with settings_file({"tts_volume": 10, "keep": "me"}) as path:
            repository = JsonSettingsRepository(str(path))
            repository.merge({"tts_volume": 20})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"tts_volume": 20, "keep": "me"})

    def test_replace_drops_other_keys(self) -> None:
        with settings_file({"tts_volume": 10, "keep": "me"}) as path:
            repository = JsonSettingsRepository(str(path))
            repository.replace({"tts_volume": 33})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"tts_volume": 33})

    def test_replace_swallows_errors(self) -> None:
        repository = JsonSettingsRepository(str(nonexistent_path("no-such-dir") / "x.json"))
        repository.replace({"tts_volume": 1})  # 不抛异常（与原版一致）


class TranslateSettingsTests(unittest.TestCase):
    def test_hotkeys_fall_back_to_defaults(self) -> None:
        with settings_file() as path:
            use_case = TranslateSettingsUseCase(JsonSettingsRepository(str(path)))
            # 新增功能：默认值里多了第 4 组 input（中译英输入框）
            self.assertEqual(use_case.load_hotkeys(), feature_hotkeys())

    def test_old_settings_without_input_get_default_input_hotkey(self) -> None:
        """老设置文件只写了原版三组 → ``input`` 补默认值，其余三组**不动**（升级不重置用户设置）。"""
        payload = {"hotkeys": {"translate": "alt+z", "snip": "tab+q", "save_last": "tab+e"}}
        with settings_file(payload) as path:
            use_case = TranslateSettingsUseCase(JsonSettingsRepository(str(path)))
            self.assertEqual(
                use_case.load_hotkeys(),
                {"translate": "alt+z", "snip": "tab+q", "save_last": "tab+e", "input": "ctrl+i"},
            )

    def test_hotkeys_ignore_invalid_entries(self) -> None:
        payload = {"hotkeys": {"translate": "CTRL + L", "snip": "bad", "save_last": "alt+f1"}}
        with settings_file(payload) as path:
            use_case = TranslateSettingsUseCase(JsonSettingsRepository(str(path)))
            self.assertEqual(
                use_case.load_hotkeys(),
                {
                    "translate": "ctrl+l",
                    "snip": feature_hotkeys()["snip"],
                    "save_last": "alt+f1",
                    "input": "ctrl+i",
                },
            )

    def test_tts_volume_clamped(self) -> None:
        with settings_file({"tts_volume": 500}) as path:
            self.assertEqual(TranslateSettingsUseCase(JsonSettingsRepository(str(path))).load_tts_volume(), 100)
        with settings_file({"tts_volume": "bad"}) as path:
            self.assertEqual(TranslateSettingsUseCase(JsonSettingsRepository(str(path))).load_tts_volume(), 100)

    def test_save_hotkeys_and_volume_merge(self) -> None:
        with settings_file({"keep": 1}) as path:
            use_case = TranslateSettingsUseCase(JsonSettingsRepository(str(path)))
            use_case.save_hotkeys(feature_hotkeys())
            use_case.save_tts_volume(70)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["keep"], 1)
            self.assertEqual(data["hotkeys"], feature_hotkeys())
            self.assertEqual(data["tts_volume"], 70)

    def test_save_errors_are_swallowed(self) -> None:
        class _Broken:
            path = ""

            def read(self):
                return {}

            def merge(self, patch):
                raise OSError("boom")

            def replace(self, payload):
                raise OSError("boom")

        use_case = TranslateSettingsUseCase(_Broken())
        use_case.save_hotkeys(feature_hotkeys())
        use_case.save_tts_volume(10)


class ReviewSettingsTests(unittest.TestCase):
    def test_volume_default_and_roundtrip(self) -> None:
        with settings_file() as path:
            use_case = ReviewSettingsUseCase(JsonSettingsRepository(str(path)))
            self.assertEqual(use_case.load_tts_volume(), 100)
            use_case.save_tts_volume(45)
            self.assertEqual(use_case.load_tts_volume(), 45)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"tts_volume": 45})

    def test_replace_semantics_drop_unknown_keys(self) -> None:
        with settings_file({"tts_volume": 5, "other": "x"}) as path:
            ReviewSettingsUseCase(JsonSettingsRepository(str(path))).save_tts_volume(9)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"tts_volume": 9})


class ApiKeyStoreTests(unittest.TestCase):
    def test_missing_file_returns_none(self) -> None:
        store = FileApiKeyStore(str(nonexistent_path("api_key.txt")))
        self.assertIsNone(store.read())

    def test_write_then_read_first_non_empty_line(self) -> None:
        with temp_dir() as directory:
            path = Path(directory) / "api_key.txt"
            store = FileApiKeyStore(str(path))
            store.write("  sk-abc  ")
            self.assertEqual(store.read(), "sk-abc")
            self.assertEqual(path.read_text(encoding="utf-8"), "sk-abc\n")
            path.write_text("\n\n  sk-second  \nsk-third\n", encoding="utf-8")
            self.assertEqual(store.read(), "sk-second")


if __name__ == "__main__":
    unittest.main()
