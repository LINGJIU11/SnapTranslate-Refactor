"""子进程式子应用监管（实现 :class:`~snaptranslate.domain.ports.app_launcher.AppLauncher`）。

为什么用"子进程"而不是把三个窗口塞进一个进程：

- **零改造**：``TranslateApp`` / ``ReviewApp`` / ``AdminApp`` 一行都不用动，现有 232 项测试与
  gui_smoke 门禁继续有效；
- **隔离**：某个窗口崩了不影响启动器，反之亦然；
- **热键只有一份**：只有划词窗口会跑 8ms 轮询监听器，启动器自己不跑；
  再加上单实例互斥，绝不会出现"一次划词被翻译两遍"。

代价（写在这里免得以后惊讶）：打开三个窗口 ≈ 三个 Python 进程；窗口之间不共享内存，
例如在划词窗口收录的生词，已经开着的复习窗口要重开才看得到。

"是否已经开着"以**窗口标题**为准（用户看到的就是窗口），进程句柄作为辅助：
刚启动、窗口还没画出来时靠句柄判定，避免连点两下按钮开出两个实例。
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Callable, Mapping, Sequence

from snaptranslate.domain.models.launcher import LauncherAppItem
from snaptranslate.domain.ports.window import WindowActivator

#: 启动后等待窗口出现的最长时间（秒）——冷启动要 import tkinter，给宽一点
WINDOW_WAIT_SEC = 12.0
#: 轮询间隔
POLL_SEC = 0.2


class SubprocessAppLauncher:
    """按 :class:`LauncherAppItem` 清单启动/唤起子应用。"""

    def __init__(
        self,
        items: Sequence[LauncherAppItem],
        *,
        command_prefix: Sequence[str],
        activator: WindowActivator,
        spawn: Callable[..., object] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        window_wait_sec: float = WINDOW_WAIT_SEC,
    ) -> None:
        self._items: Mapping[str, LauncherAppItem] = {item.key: item for item in items}
        self._command_prefix = list(command_prefix)
        self._activator = activator
        self._spawn = spawn or self._default_spawn
        self._sleep = sleeper
        self._window_wait_sec = window_wait_sec
        #: 由本启动器拉起的子进程（key → Popen）
        self._children: dict[str, object] = {}

    # ———————————————————————————— 端口 ————————————————————————————

    def is_running(self, key: str) -> bool:
        item = self._items.get(key)
        if item is None:
            return False
        if self._window_of(item):
            return True
        return self._process_alive(key)

    def running_keys(self) -> tuple[str, ...]:
        return tuple(key for key in self._items if self.is_running(key))

    def open_or_focus(self, key: str) -> None:
        item = self._items.get(key)
        if item is None:
            return
        hwnd = self._window_of(item)
        if hwnd:
            self._focus(hwnd)
            return
        if not self._process_alive(key):
            self._launch(item)
        # 冷启动要等窗口画出来；拿到就唤到前台（用户点了按钮就该立刻看到东西）
        hwnd = self._wait_for_window(item)
        if hwnd:
            self._focus(hwnd)

    def terminate_all(self) -> None:
        for handle in list(self._children.values()):
            try:
                if handle.poll() is None:  # type: ignore[attr-defined]
                    handle.terminate()  # type: ignore[attr-defined]
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

    def _process_alive(self, key: str) -> bool:
        handle = self._children.get(key)
        if handle is None:
            return False
        try:
            if handle.poll() is None:  # type: ignore[attr-defined]
                return True
        except Exception:
            return False
        self._children.pop(key, None)
        return False

    def _launch(self, item: LauncherAppItem) -> None:
        command = [*self._command_prefix, item.arg]
        try:
            self._children[item.key] = self._spawn(command)
        except OSError:
            # 拉不起来（例如 exe 被删）时不要把启动器拖崩
            self._children.pop(item.key, None)

    def _wait_for_window(self, item: LauncherAppItem) -> int:
        deadline = self._window_wait_sec
        waited = 0.0
        while waited < deadline:
            hwnd = self._window_of(item)
            if hwnd:
                return hwnd
            self._sleep(POLL_SEC)
            waited += POLL_SEC
        return 0

    @staticmethod
    def _default_spawn(command: Sequence[str]) -> object:
        """起子进程：Windows 上不要弹控制台窗口。"""
        flags = 0
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return subprocess.Popen(list(command), creationflags=flags, close_fds=True)


__all__ = ["POLL_SEC", "WINDOW_WAIT_SEC", "SubprocessAppLauncher"]
