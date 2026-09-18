"""启动器：**一个 exe 分发到四个窗口 + 控制台 + 自检**（新增功能）。

用法（打包后就是同一个 exe 的不同参数）::

    SnapTranslate.exe                      # 控制台窗口（默认）+ 托盘常驻
    SnapTranslate.exe --app=translate      # 划词翻译
    SnapTranslate.exe --app=review         # 生词复习（桌面）
    SnapTranslate.exe --app=admin          # 词表后台管理
    SnapTranslate.exe --app=web            # 生词复习（网页，需要带 streamlit 的那个包）
    SnapTranslate.exe --self-check         # 打包产物自检（数据目录/容器/托盘/热键/图标）

设计要点：

1. **自派发**：控制台不复制一份窗口代码，而是用同一份 exe 加 ``--app=`` 起子进程
   （见 ``infrastructure/process/app_processes.py`）；
2. **单实例**：每个子应用一个命名互斥量（``#17`` 的"无单实例"在打包形态下必须解决——
   热键是轮询式的，两个划词实例会同时响应同一次划词并互相覆盖 ``vocab.json``）；
3. **数据目录一路透传**：控制台把解析出的数据目录用 ``--data-dir=`` 传给每个子进程，
   保证"数据跟着 exe"这条约定在子进程里也成立。
"""

from __future__ import annotations

import sys
from pathlib import Path

from snaptranslate.domain.models.launcher import LauncherAppItem
from snaptranslate.bootstrap.container import Container, DataPaths
from snaptranslate.config import paths as config_paths
from snaptranslate.domain.models.hotkey import label_or_placeholder
from snaptranslate.domain.ports.single_instance import SingleInstanceGuard
from snaptranslate.domain.ports.tray import TrayMenuItem
from snaptranslate.presentation.texts import AdminText, LauncherText, ReviewText, WindowText

APP_TRANSLATE = "translate"
APP_REVIEW = "review"
APP_ADMIN = "admin"
APP_WEB = "web"
APP_PANEL = "panel"
MODE_SELF_CHECK = "self-check"

#: 需要单实例保护的三种子应用（``web`` 是 streamlit，自己会占端口，不重复保护）
SINGLETON_APPS: tuple[str, ...] = (APP_PANEL, APP_TRANSLATE, APP_REVIEW, APP_ADMIN)

#: ``--app=`` 允许的取值
APP_CHOICES: tuple[str, ...] = (APP_TRANSLATE, APP_REVIEW, APP_ADMIN, APP_WEB)


# ———————————————————————————— 参数 ————————————————————————————


def parse_args(argv: list[str]) -> tuple[str, str | None]:
    """解析命令行，返回 ``(模式, 数据目录或 None)``。

    支持 ``--app=translate``、``--panel``、``--self-check``、``--data-dir=路径``；
    未知参数忽略（打包后的快捷方式常常还会带上别的开关，不该因此起不来）。
    """
    mode = APP_PANEL
    data_dir: str | None = None
    for arg in argv:
        if arg.startswith("--app="):
            value = arg.split("=", 1)[1].strip().lower()
            if value in APP_CHOICES:
                mode = value
        elif arg == f"--{MODE_SELF_CHECK}":
            mode = MODE_SELF_CHECK
        elif arg == "--panel":
            mode = APP_PANEL
        elif arg.startswith("--data-dir="):
            value = arg.split("=", 1)[1].strip()
            if value:
                data_dir = value
    return mode, data_dir


def _paths(data_dir: str | None) -> DataPaths:
    if data_dir:
        return DataPaths.under(data_dir)
    return DataPaths.default()


def _resolved_data_dir(data_dir: str | None) -> str:
    return _paths(data_dir).vocab and str(Path(_paths(data_dir).vocab).parent)


# ———————————————————————————— 子应用清单 ————————————————————————————


def launcher_items() -> tuple[LauncherAppItem, ...]:
    """可启动/唤起的子应用清单。

    窗口标题必须与子窗口真实标题**一字不差**（:func:`WindowActivator.find_window` 用它判定是否已开）。
    """
    titles = {
        APP_TRANSLATE: WindowText.TITLE,
        APP_REVIEW: ReviewText.TITLE,
        APP_ADMIN: AdminText.TITLE,
    }
    return tuple(
        LauncherAppItem(
            key=key,
            label=label,
            hint=hint,
            arg=f"--app={key}",
            window_title=titles[key],
        )
        for key, label, hint in LauncherText.APPS
    )


def child_command_prefix(data_dir: str | None = None) -> list[str]:
    """子进程的命令前缀（自派发：打包后用 exe 自己，源码运行用入口脚本）。"""
    if config_paths.is_frozen():
        prefix = [sys.executable]
    else:
        launcher_entry = Path(config_paths.project_root()) / "entrypoints" / "launcher.py"
        prefix = [sys.executable, str(launcher_entry)]
    prefix.append(f"--data-dir={_resolved_data_dir(data_dir)}")
    return prefix


# ———————————————————————————— 入口 ————————————————————————————


def main(argv: list[str] | None = None, *, guard: SingleInstanceGuard | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    mode, data_dir = parse_args(args)

    if mode == MODE_SELF_CHECK:
        return run_self_check(data_dir)

    if mode == APP_WEB:
        from snaptranslate.bootstrap.wiring import run_review_web

        run_review_web(data_dir)
        return 0

    if mode == APP_PANEL:
        return run_launcher_panel(data_dir, guard=guard)

    # 三个子窗口：先抢单实例，抢不到就把已开的那个唤到前台
    if not _acquire_single_instance(mode, guard):
        _focus_existing(mode)
        return 0
    return run_child_app(mode, data_dir)


def run_child_app(mode: str, data_dir: str | None = None) -> int:
    from snaptranslate.bootstrap.wiring import run_admin_app, run_review_app, run_translate_app

    runners = {
        APP_TRANSLATE: run_translate_app,
        APP_REVIEW: run_review_app,
        APP_ADMIN: run_admin_app,
    }
    runner = runners.get(mode)
    if runner is None:
        return 2
    runner(data_dir)
    return 0


def run_launcher_panel(data_dir: str | None = None, *, guard: SingleInstanceGuard | None = None) -> int:
    """控制台窗口 + 托盘常驻。"""
    from snaptranslate.infrastructure.process.app_processes import SubprocessAppLauncher
    from snaptranslate.presentation.tk.launcher_window import LauncherApp

    if not _acquire_single_instance(APP_PANEL, guard):
        _focus_existing(APP_PANEL)
        return 0

    container = Container(_paths(data_dir))
    items = launcher_items()
    deps = LauncherAppDepsFactory(container, items, data_dir).build()
    LauncherApp(deps).run()
    return 0


class LauncherAppDepsFactory:
    """把容器里的适配器组装成启动器依赖包（放在这里是为了让 ``main`` 保持一行一件事）。"""

    def __init__(self, container: Container, items: tuple[LauncherAppItem, ...], data_dir: str | None) -> None:
        self._container = container
        self._items = items
        self._data_dir = data_dir

    def build(self):
        from snaptranslate.application.deps import LauncherAppDeps
        from snaptranslate.infrastructure.process.app_processes import SubprocessAppLauncher

        activator = self._container.window_activator()
        launcher = SubprocessAppLauncher(
            self._items,
            command_prefix=child_command_prefix(self._data_dir),
            activator=activator,
        )
        hotkeys = self._container.translate_settings().load_hotkeys()
        return LauncherAppDeps(
            apps=self._items,
            launcher=launcher,
            tray=self._container.tray_icon(),
            data_dir=_resolved_data_dir(self._data_dir),
            icon_path=config_paths.icon_path(),
            hotkey_label=label_or_placeholder(hotkeys.get("translate", "")),
        )


# ———————————————————————————— 自检（打包验收） ————————————————————————————


def run_self_check(data_dir: str | None = None) -> int:
    """打包产物自检：把"打包后最容易坏的东西"逐条验一遍。

    源码运行也能跑（返回 0），但它的主要用途是在 **exe 上**跑：
    路径、日志、容器装配、托盘、热键、图标、单实例——都是打错包就会当场报错的项。

    **报告同时写文件**：主包是窗口程序（``console=False``），冻结后 ``sys.stdout`` 是 ``None``，
    裸 ``print`` 会直接抛异常（第一次构建就是这样静默失败的）。所以报告写到数据目录的
    ``self-check.txt``，退出码表示成败——顺带也证明了"数据跟着 exe"这条约定。
    """
    from snaptranslate.infrastructure.input.win32_hotkeys import Win32PollingHotkeyListener
    from snaptranslate.infrastructure.input.win32_single_instance import Win32SingleInstance

    failures: list[str] = []
    lines: list[str] = []
    paths = _paths(data_dir)

    def say(text: str = "") -> None:
        lines.append(text)

    def check(label: str, ok: bool, detail: str = "") -> None:
        say(f"  [{'OK' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
        if not ok:
            failures.append(label)

    mode = "打包运行（frozen）" if config_paths.is_frozen() else "源码运行"
    say(f"SnapTranslate 自检 — {mode}")
    say(f"  程序目录 = {config_paths.base_dir()}")
    say(f"  数据目录 = {paths.vocab} 的父目录")

    # 1) 数据目录可写
    try:
        probe = Path(paths.vocab).parent
        probe.mkdir(parents=True, exist_ok=True)
        probe_file = probe / ".self-check.tmp"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        check("数据目录可写", True, str(probe))
    except OSError as exc:
        check("数据目录可写", False, f"{type(exc).__name__}: {exc}")

    # 2) 日志文件
    container = None
    try:
        container = Container(paths)
        container.log_sink.write("自检：日志通道正常")
        check("日志文件可写", Path(paths.log).is_file(), paths.log)
    except Exception as exc:  # noqa: BLE001
        check("日志文件可写", False, f"{type(exc).__name__}: {exc}")

    # 3) 图标
    check("图标文件存在", Path(config_paths.icon_path()).is_file(), config_paths.icon_path())

    # 4) 容器与三套依赖
    if container is not None:
        for name, factory in (
            ("划词翻译", container.translate_app_deps),
            ("生词复习", container.review_app_deps),
            ("词表管理", container.admin_app_deps),
        ):
            try:
                factory()
                check(f"{name}依赖装配", True)
            except Exception as exc:  # noqa: BLE001
                check(f"{name}依赖装配", False, f"{type(exc).__name__}: {exc}")

    # 5) tkinter（打包最容易漏的运行时）
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.destroy()
        check("tkinter 可用", True)
    except Exception as exc:  # noqa: BLE001
        check("tkinter 可用", False, f"{type(exc).__name__}: {exc}")

    # 6) 轮询热键监听器可构造
    try:
        listener = Win32PollingHotkeyListener()
        listener.stop()
        check("热键监听器可构造", True)
    except Exception as exc:  # noqa: BLE001
        check("热键监听器可构造", False, f"{type(exc).__name__}: {exc}")

    # 7) 指定模块
    for name in ("requests", "pyperclip", "PIL", "pytesseract", "openai"):
        try:
            __import__(name)
            check(f"依赖 {name}", True)
        except Exception as exc:  # noqa: BLE001
            check(f"依赖 {name}", False, f"{type(exc).__name__}: {exc}")

    # 8) 托盘注册 / 注销
    try:
        tray = Container(paths).tray_icon()
        ok = tray.start(
            "SnapTranslate 自检", config_paths.icon_path(), [TrayMenuItem("quit", "退出")], lambda _k: None
        )
        tray.stop()
        check("托盘注册/注销", bool(ok))
    except Exception as exc:  # noqa: BLE001
        check("托盘注册/注销", False, f"{type(exc).__name__}: {exc}")

    # 9) 单实例互斥
    try:
        probe_guard = Win32SingleInstance()
        first = probe_guard.acquire("self-check")
        second = Win32SingleInstance().acquire("self-check")
        probe_guard.release()
        check("单实例互斥可用", first and not second, f"first={first} second={second}")
    except Exception as exc:  # noqa: BLE001
        check("单实例互斥可用", False, f"{type(exc).__name__}: {exc}")

    # 10) 子应用清单（启动器按标题唤起，标题为空就等于唤起不了）
    try:
        items = launcher_items()
        complete = all(item.window_title and item.arg for item in items)
        check("子应用清单完整", complete and len(items) == 3, f"{[i.key for i in items]}")
    except Exception as exc:  # noqa: BLE001
        check("子应用清单完整", False, f"{type(exc).__name__}: {exc}")

    say()
    if failures:
        say(f"[FAIL] 自检未通过：{len(failures)} 项 → {', '.join(failures)}")
        code = 1
    else:
        say("[OK] 自检全部通过")
        code = 0

    _emit_report(paths, lines, code)
    return code


#: 自检报告文件名（打包后没有控制台，报告写文件）
SELF_CHECK_REPORT = "self-check.txt"


def _emit_report(paths, lines: list[str], code: int) -> None:
    """把自检报告写文件（并尽量回显到控制台）。"""
    report_path = Path(paths.vocab).parent / SELF_CHECK_REPORT
    text = "\n".join(lines) + "\n"
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    except OSError:
        pass
    stream = sys.stdout
    if stream is not None:  # 窗口程序里 stdout 是 None，绝不能直接 print
        try:
            stream.write(text)
            stream.flush()
        except (OSError, ValueError, AttributeError):
            pass
    if code != 0:
        # 窗口程序里用户看不到任何东西，至少弹一条系统提示
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, f"自检未通过，详见：\n{report_path}", "SnapTranslate 自检", 0x10
            )
        except Exception:
            pass


# ———————————————————————————— 单实例 ————————————————————————————


def _guard(guard: SingleInstanceGuard | None) -> SingleInstanceGuard:
    if guard is not None:
        return guard
    from snaptranslate.infrastructure.input.win32_single_instance import Win32SingleInstance

    return Win32SingleInstance()


def _acquire_single_instance(mode: str, guard: SingleInstanceGuard | None) -> bool:
    if mode not in SINGLETON_APPS:
        return True
    return _guard(guard).acquire(mode)


def _focus_existing(mode: str) -> None:
    """第二个实例：把已开的窗口唤到前台，并当场退出。"""
    from snaptranslate.infrastructure.input.win32_window import Win32WindowActivator

    title = LauncherText.TITLE if mode == APP_PANEL else next(
        (item.window_title for item in launcher_items() if item.key == mode), ""
    )
    if not title:
        return
    activator = Win32WindowActivator()
    hwnd = activator.find_window(title)
    if hwnd:
        activator.force_foreground(hwnd)


__all__ = [
    "APP_ADMIN",
    "APP_CHOICES",
    "APP_PANEL",
    "APP_REVIEW",
    "APP_TRANSLATE",
    "APP_WEB",
    "MODE_SELF_CHECK",
    "SINGLETON_APPS",
    "child_command_prefix",
    "launcher_items",
    "main",
    "parse_args",
    "run_self_check",
]
