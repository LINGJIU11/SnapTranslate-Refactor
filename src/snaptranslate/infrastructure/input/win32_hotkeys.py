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

from snaptranslate.domain.models.hotkey import Hotkey
from snaptranslate.domain.ports.hotkey_listener import HotkeyBindings, HotkeyCallbacks
from snaptranslate.infrastructure.input.win32_keys import (
    HOTKEY_ID,
    MOD_CONTROL,
    WM_HOTKEY,
    WM_QUIT,
    modifier_vk,
    vk_from_key_token,
)

#: 原 ``main.py:1455``：轮询间隔 8ms
POLL_INTERVAL_SEC = 0.008


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

    # —— 端口实现 ——
    def start(self, bindings: HotkeyBindings, callbacks: HotkeyCallbacks) -> None:
        if self._thread is not None:
            return
        self._stopping = False
        self._thread = threading.Thread(
            target=self._loop,
            args=(bindings, callbacks),
            daemon=True,
            name="snaptranslate-hotkeys",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)

    # —— 内部 ——
    def _loop(self, bindings: HotkeyBindings, callbacks: HotkeyCallbacks) -> None:
        prev_translate = False
        prev_snip = False
        prev_save = False
        prev_snip_tab = False
        prev_snip_key = False
        prev_save_tab = False
        prev_save_key = False

        while not self._stopping:
            pressed_translate = self._is_hotkey_pressed(bindings.translate)

            if bindings.snip.modifier == "tab":
                pressed_snip, prev_snip_tab, prev_snip_key = self._tab_mod_key_fire_edge(
                    bindings.snip, prev_snip_tab, prev_snip_key
                )
            else:
                pressed_snip = self._is_hotkey_pressed(bindings.snip)
                prev_snip_tab = False
                prev_snip_key = False

            if bindings.save_last.modifier == "tab":
                pressed_save, prev_save_tab, prev_save_key = self._tab_mod_key_fire_edge(
                    bindings.save_last, prev_save_tab, prev_save_key
                )
            else:
                pressed_save = self._is_hotkey_pressed(bindings.save_last)
                prev_save_tab = False
                prev_save_key = False

            if pressed_translate and not prev_translate:
                callbacks.on_translate()
            if pressed_snip and not prev_snip:
                callbacks.on_snip()
            if pressed_save and not prev_save:
                callbacks.on_save_last()

            prev_translate = pressed_translate
            prev_snip = pressed_snip
            prev_save = pressed_save
            time.sleep(self._poll_interval)

    def _is_down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _is_hotkey_pressed(self, hotkey: Hotkey) -> bool:
        key_vk = vk_from_key_token(hotkey.key)
        mod_vk = modifier_vk(hotkey)
        if key_vk is None or mod_vk is None:
            return False
        return self._is_down(mod_vk) and self._is_down(key_vk)

    def _tab_mod_key_fire_edge(
        self, hotkey: Hotkey, prev_tab: bool, prev_key: bool
    ) -> tuple[bool, bool, bool]:
        """``Tab+X`` 组合的边沿检测（原 ``_tab_mod_key_fire_edge`` 逐行等价）。"""
        key_vk = vk_from_key_token(hotkey.key)
        if key_vk is None:
            return False, False, False
        tab_down = self._is_down(0x09)
        key_down = self._is_down(key_vk)
        fire = (
            (key_down and not prev_key and tab_down)
            or (tab_down and not prev_tab and key_down)
            or ((tab_down and key_down) and not (prev_tab and prev_key))
        )
        return fire, tab_down, key_down


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

    def start(self, bindings: HotkeyBindings, callbacks: HotkeyCallbacks) -> None:
        del bindings  # 原版硬编码 Ctrl+L，不使用界面配置
        if self._thread is not None:
            return
        self._stopping = False
        self._thread = threading.Thread(target=self._loop, args=(callbacks,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopping = True
        if self._thread_id:
            self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)

    def _loop(self, callbacks: HotkeyCallbacks) -> None:
        self._thread_id = self._kernel32.GetCurrentThreadId()
        if not self._user32.RegisterHotKey(None, self._hotkey_id, MOD_CONTROL, vk_from_key_token(self._hotkey.key)):
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
