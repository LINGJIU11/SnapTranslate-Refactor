"""Win32 虚拟键码映射（原 ``main.py:29-40`` 与 ``495-520``）。

应用层不认识虚拟键码，只有本层做"热键 → VK"的翻译。
"""

from __future__ import annotations

from snaptranslate.domain.models.hotkey import Hotkey

VK_TAB = 0x09
VK_SHIFT = 0x10
VK_CTRL = 0x11
VK_ALT = 0x12
VK_SPACE = 0x20
VK_L = 0x4C

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004

#: ``RegisterHotKey`` 的修饰键标志（原版只用到 MOD_CONTROL）
MODIFIER_FLAGS: dict[str, int] = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "shift": MOD_SHIFT,
}

#: 轮询检测用的修饰键虚拟码（原 ``_is_hotkey_pressed`` 里的映射表）
MODIFIER_VK: dict[str, int] = {
    "ctrl": VK_CTRL,
    "tab": VK_TAB,
    "shift": VK_SHIFT,
    "alt": VK_ALT,
}

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
HOTKEY_ID = 1

_NAMED_VK: dict[str, int] = {"TAB": VK_TAB, "SPACE": VK_SPACE}


def vk_from_key_token(token: str) -> int | None:
    """键名 → 虚拟键码（原 ``_vk_from_key_token``）。"""
    key = (token or "").strip().upper()
    if len(key) == 1 and "A" <= key <= "Z":
        return ord(key)
    if len(key) == 1 and "0" <= key <= "9":
        return ord(key)
    if key.startswith("F") and key[1:].isdigit():
        number = int(key[1:])
        if 1 <= number <= 12:
            return 0x70 + number - 1
    return _NAMED_VK.get(key)


def modifier_vk(hotkey: Hotkey) -> int | None:
    return MODIFIER_VK.get(hotkey.modifier)


def modifier_flag(hotkey: Hotkey) -> int | None:
    return MODIFIER_FLAGS.get(hotkey.modifier)
