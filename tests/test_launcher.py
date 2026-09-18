"""启动器测试：参数解析、子应用清单、子进程命令、子进程监管（不真的起窗口）。

启动器是"一个 exe 分发到四个窗口"的枢纽，它错了的表现是"点了没反应"或"开出第二个实例"，
所以这里把**判定逻辑**全测掉，真正起窗口的那一步留给 ``--self-check`` 与人工验收。
"""

from __future__ import annotations

import unittest

from snaptranslate.bootstrap import launcher
from snaptranslate.domain.models.launcher import LauncherAppItem
from snaptranslate.infrastructure.process.app_processes import SubprocessAppLauncher


class _FakeActivator:
    """假的窗口适配器：按标题查句柄 + 记录被唤起的句柄。"""

    def __init__(self, windows: dict[str, int] | None = None) -> None:
        self.windows = dict(windows or {})
        self.focused: list[int] = []

    def foreground(self) -> int:
        return 0

    def find_window(self, title: str) -> int:
        return self.windows.get(title, 0)

    def force_foreground(self, hwnd: int) -> None:
        self.focused.append(hwnd)


class _FakeProcess:
    def __init__(self, alive: bool = True) -> None:
        self._alive = alive

    def poll(self):
        return None if self._alive else 0

    def terminate(self) -> None:
        self._alive = False


def _items() -> tuple[LauncherAppItem, ...]:
    return (
        LauncherAppItem("translate", "划词翻译", "h1", "--app=translate", "SnapTranslate"),
        LauncherAppItem("review", "生词复习", "h2", "--app=review", "SnapTranslate — 生词复习"),
        LauncherAppItem("admin", "词表管理", "h3", "--app=admin", "词表后台管理功能"),
    )


class ParseArgsTests(unittest.TestCase):
    def test_default_is_panel(self) -> None:
        self.assertEqual(launcher.parse_args([]), (launcher.APP_PANEL, None))

    def test_app_choices(self) -> None:
        for app in launcher.APP_CHOICES:
            self.assertEqual(launcher.parse_args([f"--app={app}"]), (app, None))

    def test_self_check(self) -> None:
        self.assertEqual(launcher.parse_args(["--self-check"]), (launcher.MODE_SELF_CHECK, None))

    def test_data_dir_is_passed_through(self) -> None:
        mode, data_dir = launcher.parse_args(["--app=review", r"--data-dir=D:\Data"])
        self.assertEqual(mode, launcher.APP_REVIEW)
        self.assertEqual(data_dir, r"D:\Data")

    def test_unknown_is_ignored(self) -> None:
        """快捷方式常常会带上别的开关，不该因此起不来。"""
        self.assertEqual(launcher.parse_args(["--app=nope", "--weird"]), (launcher.APP_PANEL, None))

    def test_panel_flag(self) -> None:
        self.assertEqual(launcher.parse_args(["--panel"]), (launcher.APP_PANEL, None))


class LauncherItemsTests(unittest.TestCase):
    def test_items_match_launcher_text_table(self) -> None:
        from snaptranslate.presentation.texts import LauncherText

        items = launcher.launcher_items()
        self.assertEqual(tuple(item.key for item in items), tuple(k for k, _l, _h in LauncherText.APPS))
        for item in items:
            self.assertEqual(item.arg, f"--app={item.key}")
            self.assertTrue(item.window_title)
            self.assertTrue(item.label)

    def test_window_titles_match_real_windows(self) -> None:
        """标题一字不差才会有意义：FindWindow 是精确匹配。"""
        from snaptranslate.presentation.texts import AdminText, ReviewText, WindowText

        titles = {item.key: item.window_title for item in launcher.launcher_items()}
        self.assertEqual(titles["translate"], WindowText.TITLE)
        self.assertEqual(titles["review"], ReviewText.TITLE)
        self.assertEqual(titles["admin"], AdminText.TITLE)

    def test_child_command_is_self_dispatching(self) -> None:
        prefix = launcher.child_command_prefix(None)
        self.assertTrue(prefix[-1].startswith("--data-dir="))
        # 源码运行：exe + 入口脚本；打包运行：exe 自己（这里只断言前缀形状）
        self.assertIn("python", prefix[0].lower())


class SubprocessLauncherTests(unittest.TestCase):
    def _launcher(self, activator, *, spawned: list | None = None, wait: float = 0.0):
        spawned = spawned if spawned is not None else []

        def spawn(command):
            spawned.append(command)
            return _FakeProcess(alive=True)

        return (
            SubprocessAppLauncher(
                _items(),
                command_prefix=["py", "--data-dir=X"],
                activator=activator,
                spawn=spawn,
                sleeper=lambda _s: None,
                window_wait_sec=wait,
            ),
            spawned,
        )

    def test_running_detected_by_window(self) -> None:
        launcher_ = self._launcher(_FakeActivator({"SnapTranslate": 111}))[0]
        self.assertTrue(launcher_.is_running("translate"))
        self.assertFalse(launcher_.is_running("review"))
        self.assertEqual(launcher_.running_keys(), ("translate",))

    def test_existing_window_is_focused_not_respawned(self) -> None:
        activator = _FakeActivator({"SnapTranslate — 生词复习": 222})
        launcher_, spawned = self._launcher(activator)

        launcher_.open_or_focus("review")

        self.assertEqual(spawned, [])  # 不该再起一个
        self.assertEqual(activator.focused, [222])

    def test_missing_window_is_spawned_with_arg(self) -> None:
        activator = _FakeActivator()
        launcher_, spawned = self._launcher(activator)

        launcher_.open_or_focus("admin")

        self.assertEqual(spawned, [["py", "--data-dir=X", "--app=admin"]])

    def test_second_click_does_not_spawn_twice(self) -> None:
        """进程刚起来、窗口还没画出来时连点两次，不能开出两个实例。"""
        activator = _FakeActivator()
        launcher_, spawned = self._launcher(activator, wait=0.0)

        launcher_.open_or_focus("translate")
        launcher_.open_or_focus("translate")

        self.assertEqual(len(spawned), 1)

    def test_terminate_all_closes_children(self) -> None:
        activator = _FakeActivator()
        launcher_, spawned = self._launcher(activator)
        launcher_.open_or_focus("translate")

        launcher_.terminate_all()

        self.assertFalse(launcher_.is_running("translate"))
        self.assertEqual(len(spawned), 1)

    def test_window_appears_after_launch_and_gets_focused(self) -> None:
        """冷启动：先起进程，窗口画出来后要自动唤到前台。"""
        activator = _FakeActivator()
        spawned = []

        def spawn(command):
            spawned.append(command)
            activator.windows["SnapTranslate"] = 333  # 模拟窗口随即出现
            return _FakeProcess()

        launcher_ = SubprocessAppLauncher(
            _items(), command_prefix=["py"], activator=activator, spawn=spawn, sleeper=lambda _s: None
        )
        launcher_.open_or_focus("translate")

        self.assertEqual(activator.focused, [333])


if __name__ == "__main__":
    unittest.main()
