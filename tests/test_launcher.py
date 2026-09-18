"""启动器测试：参数解析、子应用清单、状态判定、打开/关闭/重启（不真的起窗口）。

启动器的失败模式是"点了没反应"或者"显示已打开其实打不开"，所以这里把**判定与动作逻辑**
全测掉；真正起窗口的那一步留给 ``--self-check`` 与人工验收。
"""

from __future__ import annotations

import unittest

from snaptranslate.bootstrap import launcher
from snaptranslate.domain.models.launcher import LauncherAppItem
from snaptranslate.domain.ports.app_launcher import AppState
from snaptranslate.infrastructure.process.app_processes import SubprocessAppLauncher


class _FakeActivator:
    """假的窗口适配器：按标题查句柄、可见性可控、记录被显示/置前的句柄。"""

    def __init__(self, windows: dict[str, int] | None = None, *, visible: bool = True) -> None:
        self.windows = dict(windows or {})
        self.visible = visible
        self.shown: list[int] = []
        self.focused: list[int] = []

    def foreground(self) -> int:
        return 0

    def find_window(self, title: str) -> int:
        return self.windows.get(title, 0)

    def is_visible(self, hwnd: int) -> bool:
        return bool(hwnd) and self.visible

    def show_window(self, hwnd: int) -> None:
        self.shown.append(hwnd)
        self.visible = True

    def force_foreground(self, hwnd: int) -> None:
        self.focused.append(hwnd)


class _FakeProcess:
    def __init__(self, alive: bool = True) -> None:
        self._alive = alive
        self.terminated = False

    def poll(self):
        return None if self._alive else 0

    def terminate(self) -> None:
        self._alive = False
        self.terminated = True


class _FakeProcesses:
    """假的进程控制：记录被结束的 PID。"""

    def __init__(self) -> None:
        self.terminated: list[int] = []

    def pid_of_window(self, hwnd: int) -> int:
        return hwnd * 10  # 约定：窗口句柄 ×10 就是它的 PID

    def terminate_pid(self, pid: int) -> bool:
        self.terminated.append(pid)
        return True

    def is_pid_alive(self, pid: int) -> bool:
        return False


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

    def test_panel_is_not_singleton_protected(self) -> None:
        """控制台不进单实例名单：否则"缩在托盘里的控制台"会把用户挡在门外（N5）。"""
        self.assertNotIn(launcher.APP_PANEL, launcher.SINGLETON_APPS)
        self.assertEqual(
            set(launcher.SINGLETON_APPS),
            {launcher.APP_TRANSLATE, launcher.APP_REVIEW, launcher.APP_ADMIN},
        )

    def test_child_command_is_self_dispatching(self) -> None:
        prefix = launcher.child_command_prefix(None)
        self.assertTrue(prefix[-1].startswith("--data-dir="))
        self.assertIn("python", prefix[0].lower())


class _LauncherMixin:
    def make(self, activator, *, processes=None, spawned=None, clock=None, wait=0.0, stuck_after=25.0):
        spawned = spawned if spawned is not None else []
        processes = processes or _FakeProcesses()

        def spawn(command):
            spawned.append(command)
            return _FakeProcess(alive=True)

        launcher_ = SubprocessAppLauncher(
            _items(),
            command_prefix=["py"],
            activator=activator,
            processes=processes,
            spawn=spawn,
            sleeper=lambda _s: None,
            clock=clock or (lambda: 0.0),
            window_wait_sec=wait,
            stuck_after_sec=stuck_after,
        )
        return launcher_, spawned, processes


class StateTests(_LauncherMixin, unittest.TestCase):
    """状态必须是**诚实**的：看不见的窗口不能算"运行中"（N5）。"""

    def test_stopped_when_nothing(self) -> None:
        launcher_, _spawned, _p = self.make(_FakeActivator())
        self.assertIs(launcher_.state("translate"), AppState.STOPPED)
        self.assertEqual(launcher_.running_keys(), ())

    def test_running_only_when_window_visible(self) -> None:
        launcher_, _spawned, _p = self.make(_FakeActivator({"SnapTranslate": 111}, visible=True))
        self.assertIs(launcher_.state("translate"), AppState.RUNNING)
        self.assertEqual(launcher_.running_keys(), ("translate",))

    def test_hidden_window_is_not_reported_as_running(self) -> None:
        launcher_, _spawned, _p = self.make(_FakeActivator({"SnapTranslate": 111}, visible=False))
        self.assertIs(launcher_.state("translate"), AppState.HIDDEN)
        self.assertEqual(launcher_.running_keys(), ())

    def test_starting_then_stuck(self) -> None:
        """刚拉起（窗口还没出现）是"启动中"，超过宽限期才叫"无响应"。"""
        now = {"t": 0.0}
        launcher_, _spawned, _p = self.make(_FakeActivator(), clock=lambda: now["t"])
        launcher_.open_or_focus("translate")  # 拉起进程，窗口一直没出现
        self.assertIs(launcher_.state("translate"), AppState.STARTING)
        now["t"] = 30.0
        self.assertIs(launcher_.state("translate"), AppState.STUCK)

    def test_state_labels_are_chinese(self) -> None:
        self.assertEqual(AppState.STOPPED.label, "未运行")
        self.assertEqual(AppState.STARTING.label, "启动中…")
        self.assertEqual(AppState.RUNNING.label, "运行中")
        self.assertEqual(AppState.HIDDEN.label, "已隐藏")
        self.assertEqual(AppState.STUCK.label, "无响应")


class OpenCloseRestartTests(_LauncherMixin, unittest.TestCase):
    def test_existing_visible_window_is_focused_not_respawned(self) -> None:
        activator = _FakeActivator({"SnapTranslate — 生词复习": 222})
        launcher_, spawned, _p = self.make(activator)

        self.assertTrue(launcher_.open_or_focus("review"))

        self.assertEqual(spawned, [])
        self.assertEqual(activator.focused, [222])

    def test_hidden_window_is_shown_before_focus(self) -> None:
        """隐藏到托盘的窗口必须先 ShowWindow，否则"打开"看起来毫无反应。"""
        activator = _FakeActivator({"SnapTranslate": 333}, visible=False)
        launcher_, spawned, _p = self.make(activator)

        self.assertTrue(launcher_.open_or_focus("translate"))

        self.assertEqual(spawned, [])
        self.assertEqual(activator.shown, [333])
        self.assertEqual(activator.focused, [333])

    def test_missing_window_is_spawned_with_arg(self) -> None:
        activator = _FakeActivator()
        launcher_, spawned, _p = self.make(activator)

        launcher_.open_or_focus("admin")

        self.assertEqual(spawned, [["py", "--app=admin"]])

    def test_returns_false_when_window_never_appears(self) -> None:
        """打不开要如实返回 False（面板据此报错，而不是假装"已唤起"）。"""
        launcher_, _spawned, _p = self.make(_FakeActivator(), wait=0.0)
        self.assertFalse(launcher_.open_or_focus("translate"))

    def test_second_click_while_starting_does_not_spawn_twice(self) -> None:
        """进程刚起来、窗口还没画出来时连点两次，不能开出两个实例。"""
        launcher_, spawned, _p = self.make(_FakeActivator(), wait=0.0)
        launcher_.open_or_focus("translate")
        launcher_.open_or_focus("translate")
        self.assertEqual(len(spawned), 1)

    def test_stuck_process_is_closed_and_relaunched(self) -> None:
        now = {"t": 0.0}
        activator = _FakeActivator()
        spawned: list = []

        def spawn(command):
            spawned.append(command)
            return _FakeProcess(alive=True)

        launcher_ = SubprocessAppLauncher(
            _items(),
            command_prefix=["py"],
            activator=activator,
            processes=_FakeProcesses(),
            spawn=spawn,
            sleeper=lambda _s: None,
            clock=lambda: now["t"],
            window_wait_sec=0.0,
            stuck_after_sec=25.0,
        )
        launcher_.open_or_focus("translate")  # 第一次：拉起
        now["t"] = 30.0  # 变成"无响应"
        launcher_.open_or_focus("translate")

        self.assertEqual(len(spawned), 2, "卡住的那份应当先关掉再重开")

    def test_close_uses_tracked_handle(self) -> None:
        launcher_, _spawned, _p = self.make(_FakeActivator())
        launcher_.open_or_focus("translate")
        child = launcher_._children["translate"]  # noqa: SLF001 - 断言用

        self.assertTrue(launcher_.close("translate"))

        self.assertTrue(child.handle.terminated)
        self.assertNotIn("translate", launcher_._children)  # noqa: SLF001

    def test_close_falls_back_to_window_title(self) -> None:
        """不是本控制台拉起来的窗口也要能关——按窗口标题找 PID 结束。"""
        activator = _FakeActivator({"SnapTranslate": 555})
        processes = _FakeProcesses()
        launcher_, _spawned, _p = self.make(activator, processes=processes)

        self.assertTrue(launcher_.close("translate"))

        self.assertEqual(processes.terminated, [5550])  # 555 × 10

    def test_close_reports_failure_when_nothing_found(self) -> None:
        launcher_, _spawned, _p = self.make(_FakeActivator())
        self.assertFalse(launcher_.close("translate"))

    def test_restart_closes_then_opens(self) -> None:
        activator = _FakeActivator({"SnapTranslate": 777})
        processes = _FakeProcesses()
        spawned: list = []

        def spawn(command):
            spawned.append(command)
            activator.windows.pop("SnapTranslate", None)  # 关掉后窗口消失
            return _FakeProcess(alive=True)

        launcher_ = SubprocessAppLauncher(
            _items(),
            command_prefix=["py"],
            activator=activator,
            processes=processes,
            spawn=spawn,
            sleeper=lambda _s: None,
        )
        launcher_.restart("translate")

        self.assertEqual(processes.terminated, [7770], "重启的第一步必须是关掉旧的")

    def test_terminate_all_closes_tracked_children(self) -> None:
        launcher_, spawned, _p = self.make(_FakeActivator())
        launcher_.open_or_focus("translate")

        launcher_.terminate_all()

        self.assertEqual(launcher_._children, {})  # noqa: SLF001
        self.assertEqual(len(spawned), 1)


if __name__ == "__main__":
    unittest.main()
