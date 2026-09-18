"""子进程式子应用监管（实现 :class:`~snaptranslate.domain.ports.app_launcher.AppLauncher`）。

为什么用"子进程"而不是把三个窗口塞进一个进程：

- **零改造**：``TranslateApp`` / ``ReviewApp`` / ``AdminApp`` 一行都不用动，现有测试与
  gui_smoke 门禁继续有效；
- **隔离**：某个窗口崩了不影响启动器，反之亦然；
- **热键只有一份**：只有划词窗口会跑 8ms 轮询监听器，启动器自己不跑。

代价（写在这里免得以后惊讶）：打开三个窗口 ≈ 三个 Python 进程；窗口之间不共享内存，
例如在划词窗口收录的生词，已经开着的复习窗口要重开才看得到。

**状态判定是这一版的重点**（第一版只有"运行中/未运行"）：

============================  ==================================================================
窗口状态                        判定
============================  ==================================================================
有窗口且可见                    ``running``
有窗口但不可见（隐藏到托盘）      ``hidden``（打开时先 ``ShowWindow`` 再置前）
没窗口、进程是我们刚拉起的        ``starting``（**不显示成"运行中"**，避免"说开好了却点不动"）
没窗口、进程活着超过宽限期        ``stuck``（允许"关闭/重启"）
进程与窗口都没有                ``stopped``
============================  ==================================================================

"关闭"永远可用：进程句柄在我们手上就直接 terminate；不在手上（用户从快捷方式直接启动的）
就**按窗口标题**找到窗口 → 取 PID → 结束进程。
"""

from __future__ import annotations

import time
from typing import Callable, Mapping, Sequence

from snaptranslate.domain.models.launcher import LauncherAppItem
from snaptranslate.domain.ports.app_launcher import AppState
from snaptranslate.domain.ports.process_control import ProcessController
from snaptranslate.domain.ports.window import WindowActivator
from snaptranslate.infrastructure.process.no_window import popen_hidden

#: 启动后等待窗口出现的最长时间（秒）——冷启动要 import tkinter，给宽一点
WINDOW_WAIT_SEC = 12.0
#: 轮询间隔
POLL_SEC = 0.2
#: 超过这个秒数还没有窗口就认为"卡住"（不是启动中）
STUCK_AFTER_SEC = 25.0


class _Child:
    """一路子应用的本进程记录（句柄 + 拉起时刻）。

    ``started_at`` 取自注入的时钟（测试里可以拨快时间，从而验证"启动中 → 无响应"的判定）。
    """

    __slots__ = ("handle", "started_at")

    def __init__(self, handle: object, started_at: float) -> None:
        self.handle = handle
        self.started_at = started_at

    def alive(self) -> bool:
        try:
            return self.handle.poll() is None  # type: ignore[attr-defined]
        except Exception:
            return False


class SubprocessAppLauncher:
    """按 :class:`LauncherAppItem` 清单启动 / 唤起 / 关闭 / 重启用子应用。"""

    def __init__(
        self,
        items: Sequence[LauncherAppItem],
        *,
        command_prefix: Sequence[str],
        activator: WindowActivator,
        processes: ProcessController,
        spawn: Callable[..., object] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        window_wait_sec: float = WINDOW_WAIT_SEC,
        stuck_after_sec: float = STUCK_AFTER_SEC,
    ) -> None:
        self._items: Mapping[str, LauncherAppItem] = {item.key: item for item in items}
        self._command_prefix = list(command_prefix)
        self._activator = activator
        self._processes = processes
        self._spawn = spawn or self._default_spawn
        self._sleep = sleeper
        self._clock = clock
        self._window_wait_sec = window_wait_sec
        self._stuck_after_sec = stuck_after_sec
        self._children: dict[str, _Child] = {}

    # ———————————————————————————— 端口 ————————————————————————————

    def state(self, key: str) -> AppState:
        item = self._items.get(key)
        if item is None:
            return AppState.STOPPED
        hwnd = self._window_of(item)
        if hwnd:
            return AppState.RUNNING if self._activator.is_visible(hwnd) else AppState.HIDDEN
        child = self._children.get(key)
        if child is not None and child.alive():
            elapsed = self._clock() - child.started_at
            return AppState.STUCK if elapsed > self._stuck_after_sec else AppState.STARTING
        if child is not None:
            self._children.pop(key, None)  # 进程已经退出，顺手清掉
        return AppState.STOPPED

    def running_keys(self) -> tuple[str, ...]:
        return tuple(key for key in self._items if self.state(key) is AppState.RUNNING)

    def open_or_focus(self, key: str) -> bool:
        """打开或唤起；返回是否确认已有可见窗口（失败要如实上报给用户）。"""
        item = self._items.get(key)
        if item is None:
            return False

        hwnd = self._window_of(item)
        if hwnd:
            # 先"显示"再"置前"：隐藏到托盘的窗口只 SetForegroundWindow 是不会出现的
            self._activator.show_window(hwnd)
            self._focus(hwnd)
            return self._activator.is_visible(hwnd)

        state = self.state(key)
        if state is AppState.STARTING:
            # 已经在启动中：别再拉一个，等它把窗口画出来
            hwnd = self._wait_for_window(item)
        elif state is AppState.STUCK:
            # 卡住的那份留着没用（还会占着单实例互斥量），关掉重来
            self.close(key)
            hwnd = self._launch_and_wait(item)
        else:
            hwnd = self._launch_and_wait(item)

        if hwnd:
            self._activator.show_window(hwnd)
            self._focus(hwnd)
            return self._activator.is_visible(hwnd)
        return False

    def close(self, key: str) -> bool:
        """结束该子应用：优先用自己的句柄，否则按窗口标题找进程结束。"""
        item = self._items.get(key)
        if item is None:
            return False
        closed = False

        child = self._children.pop(key, None)
        if child is not None:
            try:
                if child.handle.poll() is None:  # type: ignore[attr-defined]
                    child.handle.terminate()  # type: ignore[attr-defined]
                    closed = True
            except Exception:
                pass

        hwnd = self._window_of(item)
        if hwnd:
            pid = self._processes.pid_of_window(hwnd)
            if pid and self._processes.terminate_pid(pid):
                closed = True
        return closed

    def restart(self, key: str) -> bool:
        self.close(key)
        # 等一下让进程真正退出（否则单实例互斥量还占着，新实例会立刻退出）
        deadline = self._clock() + 5.0
        while self._clock() < deadline and self._window_of(self._items[key]):
            self._sleep(POLL_SEC)
        return self.open_or_focus(key)

    def terminate_all(self) -> None:
        for key in list(self._items):
            try:
                self.close(key)
            except Exception:
                pass
        self._children.clear()

    # ———————————————————————————— 内部 ————————————————————————————

    def _window_of(self, item: LauncherAppItem) -> int:
        try:
            return int(self._activator.find_window(item.window_title))
        except Exception:
            return 0

    def _focus(self, hwnd: int) -> None:
        try:
            self._activator.force_foreground(hwnd)
        except Exception:
            pass

    def _launch_and_wait(self, item: LauncherAppItem) -> int:
        self._launch(item)
        return self._wait_for_window(item)

    def _launch(self, item: LauncherAppItem) -> None:
        command = [*self._command_prefix, item.arg]
        try:
            self._children[item.key] = _Child(self._spawn(command), self._clock())
        except OSError:
            # 拉不起来（例如 exe 被删）时不要把启动器拖崩
            self._children.pop(item.key, None)

    def _wait_for_window(self, item: LauncherAppItem) -> int:
        waited = 0.0
        while waited < self._window_wait_sec:
            hwnd = self._window_of(item)
            if hwnd:
                return hwnd
            self._sleep(POLL_SEC)
            waited += POLL_SEC
        return 0

    @staticmethod
    def _default_spawn(command: Sequence[str]) -> object:
        """起子进程：一律走"不弹窗"参数（打包成窗口程序后尤其重要，见 ``no_window``）。"""
        return popen_hidden(command, close_fds=True)


__all__ = [
    "POLL_SEC",
    "STUCK_AFTER_SEC",
    "WINDOW_WAIT_SEC",
    "SubprocessAppLauncher",
]
