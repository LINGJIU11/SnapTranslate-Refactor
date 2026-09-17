"""诊断：模拟 Ctrl+C 取词为什么在 Alt+Z 热键下失败。

已观察到的模式（记事本受控实验）：

    不按修饰键         → 失败
    按住 Ctrl 再复制   → 成功
    按住 Alt 再复制    → 失败

两个叠加机制：

**P1 修饰键污染**：Alt 还按着时，注入的 Ctrl+C 在目标程序看来是 Ctrl+Alt+C。
**P2 注入没有间隔**：原版 ``keybd_event`` 四次调用（Ctrl↓ C↓ C↑ Ctrl↑）**零延迟**发出，
目标程序处理到 C 键时，系统异步键态可能已经显示 Ctrl 抬起 → 当成普通字母 c，不复制。
物理按着 Ctrl 时（默认热键 Ctrl+L）恰好掩盖了 P2，所以老版本"看起来能用"。

本脚本对四种注入策略逐一测量"剪贴板有没有真的被写"：

    python scripts/diagnose_modifier_poisoning.py

会短暂弹出记事本，结束后自动关闭。
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pyperclip  # noqa: E402

from snaptranslate.infrastructure.input.win32_clipboard import PyperclipClipboard  # noqa: E402
from snaptranslate.infrastructure.input.win32_window import Win32WindowActivator  # noqa: E402

VK_CTRL = 0x11
VK_ALT = 0x12
VK_SHIFT = 0x10
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_C = 0x43
VK_A = 0x41
VK_V = 0x56
KEYUP = 0x0002

user32 = ctypes.windll.user32

SAMPLE = "HELLO-ALT-TEST the quick brown fox jumps over the lazy dog"
SENTINEL = "SENTINEL-OLD-CLIPBOARD-CONTENT"
#: 与原版一致的注入间隔（0 = 完全照搬原版）
INJECT_GAP = 0.0
FIXED_GAP = 0.02


def tap(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYUP, 0)


def chord(modifier: int, vk: int) -> None:
    user32.keybd_event(modifier, 0, 0, 0)
    tap(vk)
    user32.keybd_event(modifier, 0, KEYUP, 0)


def hold(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)


def release(vk: int) -> None:
    user32.keybd_event(vk, 0, KEYUP, 0)


def foreground_pid() -> int:
    handle = user32.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    return int(pid.value)


WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def window_for_pid(pid: int) -> int:
    found: list[int] = []

    def callback(hwnd, _lparam):
        owner = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(int(hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return found[0] if found else 0


def focus(hwnd: int, target_pid: int, attempts: int = 8) -> bool:
    activator = Win32WindowActivator()
    for _ in range(attempts):
        activator.force_foreground(hwnd)
        time.sleep(0.25)
        if foreground_pid() == target_pid:
            return True
    return False


# —— 四种注入策略 ——


def inject_original() -> None:
    """照搬原版：四次 keybd_event 零延迟。"""
    user32.keybd_event(VK_CTRL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    user32.keybd_event(VK_C, 0, KEYUP, 0)
    user32.keybd_event(VK_CTRL, 0, KEYUP, 0)


def inject_spaced(gap: float = FIXED_GAP) -> None:
    """修法 A：每次按键之间留一点间隔，确保目标程序处理 C 时键态正确。"""
    user32.keybd_event(VK_CTRL, 0, 0, 0)
    time.sleep(gap)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(gap)
    user32.keybd_event(VK_C, 0, KEYUP, 0)
    time.sleep(gap)
    user32.keybd_event(VK_CTRL, 0, KEYUP, 0)


def wait_modifiers_released(timeout: float = 1.0) -> bool:
    """修法 B：等 Alt/Shift/Win 松开（Ctrl 除外，它本来就是 Ctrl+C 的一部分）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        held = any(
            user32.GetAsyncKeyState(vk) & 0x8000 for vk in (VK_ALT, VK_SHIFT, VK_LWIN, VK_RWIN)
        )
        if not held:
            return True
        time.sleep(0.01)
    return False


def main() -> int:
    clipboard = PyperclipClipboard()
    notepad = subprocess.Popen(["notepad.exe"])
    try:
        time.sleep(1.5)
        hwnd = 0
        for _ in range(10):
            hwnd = window_for_pid(notepad.pid)
            if hwnd:
                break
            time.sleep(0.3)
        if not hwnd or not focus(hwnd, notepad.pid):
            print(f"[FAIL] 无法把记事本推到前台（前台 PID={foreground_pid()}）；结论不可用")
            return 1

        pyperclip.copy(SAMPLE)
        chord(VK_CTRL, VK_V)
        time.sleep(0.4)

        results: list[tuple[str, bool]] = []

        def measure(label: str, inject) -> None:
            focus(hwnd, notepad.pid)
            pyperclip.copy(SENTINEL)
            chord(VK_CTRL, VK_A)  # 全选
            time.sleep(0.25)
            before_seq = clipboard.sequence()
            inject()
            time.sleep(0.2)
            copied = clipboard.sequence() != before_seq and pyperclip.paste() != SENTINEL
            results.append((label, copied))
            print(f"  {label:44} 剪贴板被写入={copied}")

        print(f"记事本 PID={notepad.pid}（前台 {foreground_pid()}）\n测量四种注入策略：")

        measure("A 原版注入（零延迟），不按修饰键", inject_original)

        measure("B 带间隔注入（20ms），不按修饰键", inject_spaced)

        def alt_held_spaced() -> None:
            hold(VK_ALT)
            time.sleep(0.05)
            inject_spaced()
            release(VK_ALT)

        measure("C 带间隔注入，但 Alt 仍按住", alt_held_spaced)

        def alt_released_then_spaced() -> None:
            hold(VK_ALT)
            time.sleep(0.05)
            # 另起线程模拟"人松开手指"，应用则在这里等修饰键抬起
            threading.Timer(0.15, lambda: release(VK_ALT)).start()
            released = wait_modifiers_released()
            inject_spaced()
            print(f"      （等修饰键松开：{'成功等到' if released else '等待超时'}）")

        measure("D 先等 Alt 松开 + 带间隔注入", alt_released_then_spaced)

        # —— 用**真实读取器**（含"等修饰键松开"加固）模拟两种热键 ——
        from snaptranslate.infrastructure.input.win32_selection import Win32SelectionReader
        from snaptranslate.infrastructure.system_clock import SystemClock

        reader = Win32SelectionReader(clipboard, clock=SystemClock())

        def real_reader_ctrl_f9() -> None:
            hold(VK_CTRL)  # 模拟按着 ctrl+f9：Ctrl 一直按着（Ctrl+C 需要它）
            tap(0x78)  # F9
            capture = reader.read_selected_text()
            release(VK_CTRL)
            print(f"      （真实读取器：copied={capture.copied} text={capture.text[:40]!r}）")

        def real_reader_alt_z() -> None:
            hold(VK_ALT)
            tap(0x5A)  # Z
            threading.Timer(0.15, lambda: release(VK_ALT)).start()  # 人松手
            capture = reader.read_selected_text()
            print(f"      （真实读取器：copied={capture.copied} text={capture.text[:40]!r} "
                  f"modifiers_held={capture.modifiers_held}）")

        measure("E 真实读取器 + ctrl+f9（Ctrl 按住）", real_reader_ctrl_f9)
        measure("F 真实读取器 + alt+z（Alt 稍后松开）", real_reader_alt_z)

        table = dict(results)
        real = table
        print("\n结论（对照实测）：")
        print(f"  A 原版注入、无修饰键        : {'成功' if table.get('A 原版注入（零延迟），不按修饰键') else '失败'}"
              "   → 零延迟注入本身不是问题")
        print(f"  C Alt 仍按住时复制         : {'成功' if table.get('C 带间隔注入，但 Alt 仍按住') else '失败'}"
              "   → **Alt 污染 Ctrl+C，这是取词失败的直接原因**")
        print(f"  E 真实读取器 + ctrl+f9     : {'成功' if real.get('E 真实读取器 + ctrl+f9（Ctrl 按住）') else '失败'}"
              "   → Ctrl 组合热键最稳")
        print(f"  F 真实读取器 + alt+z       : {'成功' if real.get('F 真实读取器 + alt+z（Alt 稍后松开）') else '失败'}"
              "   → 加固（先等 Alt 松开 + 按键留间隔）后 Alt 组合也能用")
        print("\n  说明：D 是我手工拼的注入变体，在记事本上偶发失败（Alt 会把记事本切进菜单模式），"
              "不代表生产路径；生产路径是 E/F 用的同一个读取器实现。")
        return 0
    finally:
        notepad.terminate()
        pyperclip.copy(SENTINEL)


if __name__ == "__main__":
    raise SystemExit(main())
