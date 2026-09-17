"""热键值对象与解析规则。

对应原版 ``main.py:461-548``（``_normalize_hotkey`` / ``_parse_hotkey`` /
``_vk_from_key_token`` / ``_hotkey_label``）。这里只保留**纯字符串规则**，
虚拟键码映射（Win32 相关）放在 ``infrastructure/input/win32_keys.py``。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 原版 ``main.py:91-95``：**对拍基线，不要再往里加东西**
#: （新增功能的热键写在 :data:`DEFAULT_INPUT_HOTKEY` 里，由 :func:`feature_hotkeys` 合并）
DEFAULT_HOTKEYS: dict[str, str] = {
    "translate": "ctrl+l",
    "snip": "tab+q",
    "save_last": "tab+e",
}

#: **新增功能**：中译英输入框的热键键名与默认值（原版只有上面三组）
INPUT_HOTKEY_KEY = "input"
DEFAULT_INPUT_HOTKEY = "ctrl+i"

#: 界面上真正会读写的全部热键：原版三组 + 新增的输入框一组
ALL_HOTKEY_KEYS: tuple[str, ...] = ("translate", "snip", "save_last", INPUT_HOTKEY_KEY)


def feature_hotkeys() -> dict[str, str]:
    """包含新增功能的默认热键（**每次返回新 dict**，调用方可安全修改）。

    与 :data:`DEFAULT_HOTKEYS` 的关系：后者是原版基线，前者是当前程序完整的默认值。
    设置文件里没有 ``input`` 字段（老版本写下的）时，就会补上这里的默认值，
    因此升级不会让老用户的其它热键被重置。
    """
    return {**DEFAULT_HOTKEYS, INPUT_HOTKEY_KEY: DEFAULT_INPUT_HOTKEY}

VALID_MODIFIERS: tuple[str, ...] = ("ctrl", "tab", "shift", "alt")
_NAMED_KEYS: tuple[str, ...] = ("TAB", "SPACE")
_PLACEHOLDER = "（未设置）"


def normalize(combo: str) -> str:
    """原版 ``_normalize_hotkey``：去空白、转小写、去掉所有空格。"""
    return (combo or "").strip().lower().replace(" ", "")


def is_valid_key_token(token: str) -> bool:
    """原版 ``_vk_from_key_token`` 的合法性部分：单字母 / 单数字 / F1..F12 / TAB / SPACE。"""
    key = (token or "").strip().upper()
    if len(key) == 1 and ("A" <= key <= "Z" or "0" <= key <= "9"):
        return True
    if key.startswith("F") and key[1:].isdigit():
        return 1 <= int(key[1:]) <= 12
    return key in _NAMED_KEYS


@dataclass(frozen=True)
class Hotkey:
    """一个合法的热键组合。"""

    modifier: str
    key: str

    @classmethod
    def parse(cls, combo: str) -> "Hotkey | None":
        """解析 ``ctrl+l`` / ``tab+q`` 这类字符串，非法返回 ``None``（原版语义）。"""
        text = normalize(combo)
        if "+" not in text:
            return None
        modifier, key = text.split("+", 1)
        if modifier not in VALID_MODIFIERS:
            return None
        if not key or not is_valid_key_token(key):
            return None
        return cls(modifier, key)

    @property
    def label(self) -> str:
        """展示用标签，如 ``CTRL+L``（原版 ``f"{mod.upper()}+{k.upper()}"``）。"""
        return f"{self.modifier.upper()}+{self.key.upper()}"

    @property
    def is_win32_registrable(self) -> bool:
        """``RegisterHotKey`` 只接受真实修饰键；``tab`` 组合必须走轮询监听器。"""
        return self.modifier != "tab"


def parse(combo: str) -> Hotkey | None:
    return Hotkey.parse(combo)


def label_or_placeholder(combo: str, placeholder: str = _PLACEHOLDER) -> str:
    """原版 ``_hotkey_label``：非法或空组合返回占位符。"""
    parsed = Hotkey.parse(combo)
    return parsed.label if parsed else placeholder
