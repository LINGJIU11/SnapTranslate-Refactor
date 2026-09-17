"""Win32 全局热键监听器。

原版有两套实现，重构后都保留，但**默认只装配轮询那一套**——因为原版的
``RegisterHotKey`` 消息循环（``main.py:1505-1528``）定义了却从未被启动过
（``run()`` 里只起了 ``_tab_combo_loop``）。详见 KNOWN_ISSUES.md #1。
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable

from snaptranslate.domain.models.hotkey import Hotkey
from snaptranslate.domain.ports.hotkey_listener import HotkeyBindings, HotkeyCallbacks
from snaptranslate.infrastructure.input.win32_keys import (
    HOTKEY_ID,
    MOD_CONTROL,
    VK_TAB,
    WM_HOTKEY,
    WM_QUIT,
    modifier_vk,
    vk_from_key_token,
)

#: 原 ``main.py:1455``：轮询间隔 8ms
POLL_INTERVAL_SEC = 0.008

#: 热键动作的固定顺序（原版循环里就是 translate → snip → save_last 这个次序）
_BINDING_ORDER: tuple[str, ...] = ("translate", "snip", "save_last", "input")


def _binding_of(bindings: HotkeyBindings, action: str) -> Hotkey | None:
    """按动作名取组合；``input`` 是新增的第 4 组，可能未绑定。"""
    return getattr(bindings, action, None)


def _callback_of(callbacks: HotkeyCallbacks, action: str) -> Callable[[], None] | None:
    return getattr(callbacks, f"on_{action}", None)


class Win32PollingHotkeyListener:
    """8ms 轮询 ``GetAsyncKeyState``（原 ``_tab_combo_loop``，实际生效的那一套）。

    ``Tab+X`` 组合无法用 ``RegisterHotKey`` 表达（Tab 不是合法修饰键），原版用
    "边沿检测"兼容"先按 Tab 再按 X / 先按 X 再按 Tab / 同时按"三种手法，这里原样保留。
    """

    def __init__(self, *, user32=None, poll_interval: float = POLL_INTERVAL_SEC) -> None:
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stopping = False
        #: 当前生效的组合：界面改热键后由 ``update_bindings`` 替换，循环每轮重新读取
        self._bindings: HotkeyBindings | None = None
        self._bindings_lock = threading.Lock()

    # —— 端口实现 ——
    def start(self, bindings: HotkeyBindings, callbacks: HotkeyCallbacks) -> None:
        if self._thread is not None:
            return
        self.update_bindings(bindings)
        self._stopping = False
        self._thread = threading.Thread(
            target=self._loop,
            args=(callbacks,),
            daemon=True,
            name="snaptranslate-hotkeys",
        )
        self._thread.start()

    def update_bindings(self, bindings: HotkeyBindings) -> None:
        """原版每轮重新读 ``self.hotkeys``，因此改热键**立即生效**；这里等价地替换快照。"""
        with self._bindings_lock:
            self._bindings = bindings

    def stop(self) -> None:
        self._stopping = True
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)

    # —— 内部 ——
    def _current_bindings(self) -> HotkeyBindings | None:
        with self._bindings_lock:
            return self._bindings

    def _loop(self, callbacks: HotkeyCallbacks) -> None:
        #: 每一路热键一个检测器（``tab+X`` 用 Tab 边沿，其余用"修饰键+键同按"）
        detectors: dict[str, "_BindingDetector"] = {
            action: _BindingDetector(self._is_down) for action in _BINDING_ORDER
        }

        while not self._stopping:
            bindings = self._current_bindings()
            if bindings is None:  # pragma: no cover - start() 之后不可能为空
                time.sleep(self._poll_interval)
                continue

            # 先全部判定、再统一触发：与原版"三个 pressed_* 都算完再 if"的顺序一致
            fired: dict[str, bool] = {}
            for action in _BINDING_ORDER:
                hotkey = _binding_of(bindings, action)
                fired[action] = False if hotkey is None else detectors[action].fired(hotkey)

            for action in _BINDING_ORDER:
                callback = _callback_of(callbacks, action)
                if fired[action] and callback is not None:
                    callback()

            time.sleep(self._poll_interval)

    def _is_down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)


class _BindingDetector:
    """一路热键的边沿检测（把原来散在循环里的 7 个 ``prev_*`` 变量收进来）。

    - 普通组合（``ctrl+l`` / ``alt+z`` / …）：修饰键与目标键**同时按下**，且上一轮没按下；
    - ``tab+X``：Tab 不是真正的修饰键，用"边沿检测"兼容"先按 Tab 再按 X / 先按 X 再按 Tab /
      同时按"三种手法（原 ``main.py:_tab_mod_key_fire_edge`` 逐行等价）。
    """

    def __init__(self, is_down: Callable[[int], bool]) -> None:
        self._is_down = is_down
        self._prev_pressed = False
        self._prev_tab = False
        self._prev_key = False

    def fired(self, hotkey: Hotkey) -> bool:
        if hotkey.modifier == "tab":
            return self._tab_edge(hotkey)
        self._prev_tab = False
        self._prev_key = False
        pressed = self._plain(hotkey)
        fired = pressed and not self._prev_pressed
        self._prev_pressed = pressed
        return fired

    def _plain(self, hotkey: Hotkey) -> bool:
        key_vk = vk_from_key_token(hotkey.key)
        mod_vk = modifier_vk(hotkey)
        if key_vk is None or mod_vk is None:
            return False
        return self._is_down(mod_vk) and self._is_down(key_vk)

    def _tab_edge(self, hotkey: Hotkey) -> bool:
        """``Tab+X`` 组合的边沿检测（原 ``_tab_mod_key_fire_edge`` 逐行等价）。"""
        key_vk = vk_from_key_token(hotkey.key)
        if key_vk is None:
            return False
        tab_down = self._is_down(VK_TAB)
        key_down = self._is_down(key_vk)
        fire = (
            (key_down and not self._prev_key and tab_down)
            or (tab_down and not self._prev_tab and key_down)
            or ((tab_down and key_down) and not (self._prev_tab and self._prev_key))
        )
        self._prev_tab = tab_down
        self._prev_key = key_down
        return fire


class Win32RegisteredHotkeyListener:
    """``RegisterHotKey`` + ``GetMessageW`` 消息循环（原 ``hotkey_loop``）。

    **原版定义了但从未启动**，因此 bootstrap 默认不装配它；保留实现是为了：
    ① 行为等价（不产生任何额外效果）；② 未来要真正启用时无需重写。
    """

    def __init__(
        self,
        *,
        hotkey: Hotkey | None = None,
        user32=None,
        kernel32=None,
        hotkey_id: int = HOTKEY_ID,
        on_error: str = "错误：Ctrl + L 注册失败，可能被占用",
    ) -> None:
        self._hotkey = hotkey or Hotkey("ctrl", "l")
        self._user32 = user32 if user32 is not None else ctypes.windll.user32
        self._kernel32 = kernel32 if kernel32 is not None else ctypes.windll.kernel32
        self._hotkey_id = hotkey_id
        self._error_message = on_error
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._stopping = False
        self._callbacks: HotkeyCallbacks | None = None
        self._bindings: HotkeyBindings | None = None

    def start(self, bindings: HotkeyBindings, callbacks: HotkeyCallbacks) -> None:
        if self._thread is not None:
            return
        self._callbacks = callbacks
        self.update_bindings(bindings)
        self._stopping = False
        self._thread = threading.Thread(target=self._loop, args=(callbacks,), daemon=True)
        self._thread.start()

    def update_bindings(self, bindings: HotkeyBindings) -> None:
        """注册式监听器同样支持热更新：正在跑就按新组合重注册。

        注意：``RegisterHotKey`` 不接受 ``tab`` 作为修饰键，这类组合只能走轮询监听器
        （原版也正是因此才两套并存）。本类默认不装配，见 KNOWN_ISSUES.md #1。
        """
        self._bindings = bindings
        if self._thread is not None and self._callbacks is not None:
            callbacks = self._callbacks
            self.stop()
            self.start(bindings, callbacks)

    def stop(self) -> None:
        self._stopping = True
        if self._thread_id:
            self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)

    def _active_hotkey(self) -> Hotkey:
        if self._bindings is None:
            return self._hotkey
        return self._bindings.translate

    def _loop(self, callbacks: HotkeyCallbacks) -> None:
        hotkey = self._active_hotkey()
        self._thread_id = self._kernel32.GetCurrentThreadId()
        if not self._user32.RegisterHotKey(None, self._hotkey_id, MOD_CONTROL, vk_from_key_token(hotkey.key)):
            if callbacks.on_error is not None:
                callbacks.on_error(self._error_message)
            return
        message = wintypes.MSG()
        try:
            while not self._stopping:
                result = self._user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == 0 or result == -1:
                    break
                if message.message == WM_HOTKEY and message.wParam == self._hotkey_id:
                    callbacks.on_translate()
                self._user32.TranslateMessage(ctypes.byref(message))
                self._user32.DispatchMessageW(ctypes.byref(message))
        finally:
            self._user32.UnregisterHotKey(None, self._hotkey_id)
