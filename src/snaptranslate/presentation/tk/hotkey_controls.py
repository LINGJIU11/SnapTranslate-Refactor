"""主窗口的热键设置：校验、解析与状态文案。

职责：把原版散在 ``TranslatorApp`` 上的热键逻辑收敛成一个可单独测试的对象，
主窗口只负责把结果写到 Tk 变量与状态栏。对应原版：

- ``_normalize_hotkey``       ``main.py:461-462``
- ``_load_hotkeys``           ``main.py:464-474``（重构后由 ``settings`` 用例负责读盘）
- ``_save_hotkeys``           ``main.py:476-480``（重构后由 ``settings`` 用例负责落盘）
- ``_parse_hotkey``           ``main.py:482-493`` → :meth:`Hotkey.parse`
- ``_hotkey_label``           ``main.py:543-548``
- ``_status_enabled_text``    ``main.py:550-554`` → ``WindowText.status_enabled``
- ``_status_disabled_text``   ``main.py:556-560`` → ``WindowText.status_disabled``
- ``_refresh_hotkey_hint``    ``main.py:562-567`` → ``WindowText.hotkey_hint``
- ``_on_apply_hotkeys`` 的校验段 ``main.py:636-657``
"""

from __future__ import annotations

from snaptranslate.domain.models.hotkey import DEFAULT_HOTKEYS, Hotkey, label_or_placeholder
from snaptranslate.presentation.texts import WindowText

#: 三组热键的内部键名（顺序与原版 ``pending`` 字典一致）
HOTKEY_KEYS: tuple[str, ...] = ("translate", "snip", "save_last")


class HotkeyManager:
    """持有当前热键设置，并提供校验 / 标签 / 绑定解析。"""

    def __init__(self, hotkeys: dict[str, str] | None = None) -> None:
        self._hotkeys: dict[str, str] = dict(hotkeys or DEFAULT_HOTKEYS)

    # —— 状态 ——

    @property
    def hotkeys(self) -> dict[str, str]:
        return self._hotkeys

    def set(self, hotkeys: dict[str, str]) -> None:
        self._hotkeys = dict(hotkeys)

    # —— 查询 ——

    def label(self, key: str) -> str:
        """原 ``_hotkey_label``：非法或缺失返回"（未设置）"。"""
        return label_or_placeholder(self._hotkeys.get(key, ""))

    def hint(self) -> str:
        """原 ``_refresh_hotkey_hint``：标题下的那一行提示。"""
        return WindowText.hotkey_hint(self._hotkeys)

    def status_enabled(self) -> str:
        return WindowText.status_enabled(self._hotkeys)

    def status_disabled(self) -> str:
        return WindowText.status_disabled(self._hotkeys)

    def bindings(self) -> dict[str, Hotkey]:
        """解析成三组 :class:`Hotkey`；任一组非法则整体回退默认值并写回。

        与 ``settings.load_hotkeys`` 的语义一致（非法组合回退默认），
        保证监听端口永远拿得到可用组合。
        """
        parsed: dict[str, Hotkey] = {}
        for key in HOTKEY_KEYS:
            hotkey = Hotkey.parse(self._hotkeys.get(key, ""))
            if hotkey is None:
                self._hotkeys = dict(DEFAULT_HOTKEYS)
                return {name: Hotkey.parse(DEFAULT_HOTKEYS[name]) for name in HOTKEY_KEYS}  # type: ignore[misc]
            parsed[key] = hotkey
        return parsed

    # —— 校验 ——

    @staticmethod
    def normalize(combo: str) -> str:
        """原 ``_normalize_hotkey``：去空白、转小写、去掉所有空格。"""
        return (combo or "").strip().lower().replace(" ", "")

    def validate(self, pending: dict[str, str]) -> str | None:
        """校验待保存的三组组合。

        返回 ``None`` 表示通过；否则返回状态栏错误文案。

        与原版一致的两点行为细节：

        1. **格式错误优先于重复**（原 ``main.py:644-652`` 先逐个校验再判重）；
        2. 文案里的 ``{name}`` 用的是**内部键名**（``translate`` / ``snip`` / ``save_last``），
           而不是界面标签 —— 原版 ``main.py:647`` 直接把 ``k`` 拼进字符串，看着像笔误，
           但属于对外文案，行为等价要求原样保留。
        """
        for key in HOTKEY_KEYS:
            value = pending.get(key, "")
            if Hotkey.parse(value) is None:
                return WindowText.HOTKEY_ERROR_FORMAT.format(name=key, value=value)
        if len({pending.get(key, "") for key in HOTKEY_KEYS}) < 3:
            return WindowText.HOTKEY_DUPLICATE
        return None
