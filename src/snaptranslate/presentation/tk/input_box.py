"""中译英输入框（**新增功能**：可复用的浮层输入 / 输出框）。

它和 :class:`~snaptranslate.presentation.tk.floating_card.FloatingCard` 是"同类不同用"：

======================  ====================================  ==================================
                        ``FloatingCard``（原版行为）            ``OverlayInputBox``（新增）
======================  ====================================  ==================================
内容                     只读：原文 => 译文                      上：可编辑输入框；下：只读输出区
谁产生内容               划词/OCR 自动                           用户自己敲中文
关闭时机                 下一次输入（键/鼠标左右键）              同左，外加"输入期间不算"
======================  ====================================  ==================================

用户明确要求的交互（逐条落实）：

1. **热键弹出**：以"热键按下瞬间"的鼠标位置为锚点（与卡片同一套几何，见 ``overlay_geometry``）；
2. **Enter 翻译**：中文留在输入框里（不清空），英文显示在下半区；
3. **翻译回来后释放键盘焦点**：把焦点还给"按热键时你正在用的那个窗口"，
   于是"再按其他键"既关闭对话框、按键也照常送到那个窗口里；
4. **点回框内 = 下一次输入**：鼠标左键落在框内**不算关闭**，而是把焦点放回输入框
   （第一次点击会全选原文，方便直接覆盖重写）；
5. **框外按键 / 框外点击 / Esc → 关闭**；
6. **不自动消失**（沿用"卡片不自动隐藏"的约定，见 KNOWN_ISSUES.md #24）。

组件只依赖端口（``Pointer`` / ``InputWatcher`` / ``WindowActivator``）与一个提交回调，
因此可以被别的地方复用（例如将来做"英译中"或"发一句话给 LLM"）。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from snaptranslate.application.dto import TranslationOutcome
from snaptranslate.application.translate_input import INPUT_MAX_LENGTH
from snaptranslate.config.theme import (
    UI_FLOAT_BG,
    UI_FLOAT_BTN,
    UI_FLOAT_FG,
    UI_FLOAT_MUTED,
)
from snaptranslate.domain.ports.input_watcher import InputWatcher
from snaptranslate.domain.ports.pointer import Pointer
from snaptranslate.domain.ports.window import WindowActivator
from snaptranslate.presentation.texts import InputText
from snaptranslate.presentation.tk.overlay_geometry import Bounds, is_inside, place_near
from snaptranslate.presentation.tk.ui_kit import FLOAT_BORDER_COLOR, floating_label, small_button, ui_font

#: 浮层尺寸（比卡片大一些：上面输入、下面输出）
BOX_WIDTH = 560
BOX_HEIGHT = 250
#: 输入/输出区各显示几行
INPUT_LINES = 4
OUTPUT_LINES = 4
#: 原版浮层同款透明度
FLOAT_ALPHA = 0.97

#: 提交回调：``(中文, 结果回调)``；结果回调**必须**在主线程被调用（由装配方保证）
SubmitCallback = Callable[[str, Callable[[TranslationOutcome], None]], None]


class OverlayInputBox:
    """可复用的浮层输入/输出框。

    :param root: 主窗口
    :param pointer: 取鼠标屏幕坐标（Win32，线程安全）
    :param input_watcher: 监听"任意键 / 鼠标左右键"
    :param window_activator: 抢/还前台窗口（翻译完成后把焦点还回去）
    :param marshal: 把回调切回主线程（``root.after(0, ...)``）
    :param on_submit: 提交回调，见 :data:`SubmitCallback`
    :param max_length: 与用例一致的长度上限（只用于拼"已截断"提示）
    """

    def __init__(
        self,
        root: tk.Tk,
        *,
        pointer: Pointer,
        input_watcher: InputWatcher,
        window_activator: WindowActivator,
        marshal: Callable[[Callable[[], None]], None],
        on_submit: SubmitCallback,
        max_length: int = INPUT_MAX_LENGTH,
    ) -> None:
        self._root = root
        self._pointer = pointer
        self._input_watcher = input_watcher
        self._window_activator = window_activator
        self._marshal = marshal
        self._on_submit = on_submit
        self._max_length = max_length

        self._window: tk.Toplevel | None = None
        self._input: tk.Text | None = None
        self._output: tk.Text | None = None
        #: 当前浮层的屏幕矩形（主线程写、监听线程读，整体替换 → 天然安全）
        self._bounds: Bounds | None = None
        #: 是否处于"正在输入"：为真时监听到的按键是**输入**而不是关闭信号
        self._accepting_input = False
        #: 每次提交一个自增号，用来丢弃"过期结果"（用户连按两次回车时只认最后一次）
        self._request_id = 0
        #: 按热键时用户正在用的窗口，翻译完成后要把焦点还给它
        self._previous_foreground = 0

    # ———————————————————————————— 对外 ————————————————————————————

    def show(self, anchor: tuple[int, int] | None = None) -> None:
        """显示输入框并把焦点给输入区（要求主线程调用）。

        :param anchor: 锚点（一般是热键按下瞬间的鼠标位置）；``None`` 时退回当前鼠标位置。
        """
        if self._window is None:
            self._build()
        window = self._window
        if window is None:  # pragma: no cover - _build 必然成功
            return
        if not self.is_visible():
            # 只在"从隐藏变可见"时记录前台窗口，避免自己抢自己的焦点
            self._previous_foreground = self._safe_foreground()

        point = anchor if anchor is not None else self._pointer.position()
        x, y, bounds = place_near(
            point,
            (BOX_WIDTH, BOX_HEIGHT),
            (self._root.winfo_screenwidth(), self._root.winfo_screenheight()),
        )
        self._bounds = bounds
        window.geometry(f"{BOX_WIDTH}x{BOX_HEIGHT}+{x}+{y}")
        window.deiconify()
        window.lift()
        window.attributes("-topmost", True)

        self._request_id += 1  # 上一轮未回来的请求作废
        self._set_output(InputText.OUTPUT_PLACEHOLDER, muted=True)
        self._arm_dismiss_watcher()
        self._focus_input(select_all=True)

    def hide(self) -> None:
        """关闭浮层（要求主线程调用）；停止输入监听并把焦点还回去。"""
        self._input_watcher.stop()
        self._accepting_input = False
        self._release_focus()
        window = self._window
        if window is None:
            return
        try:
            window.withdraw()
        except tk.TclError:
            pass

    def shutdown(self) -> None:
        """程序退出时清理：停掉监听线程，不再碰 Tk。"""
        self._input_watcher.stop()

    def is_visible(self) -> bool:
        window = self._window
        return self._bounds is not None and window is not None and bool(window.winfo_viewable())

    def current_anchor(self) -> tuple[int, int] | None:
        """浮层当前左上角（供其它浮层就地显示参考）。"""
        if self._bounds is None:
            return None
        return (self._bounds[0], self._bounds[1])

    def input_text(self) -> str:
        """当前输入框里的文本（自检/测试用）。"""
        if self._input is None:
            return ""
        return self._input.get("1.0", "end").strip()

    def output_text(self) -> str:
        """当前输出区里的文本（自检/测试用）。"""
        if self._output is None:
            return ""
        return self._output.get("1.0", "end").strip()

    def is_accepting_input(self) -> bool:
        return self._accepting_input

    # ———————————————————————————— 内部：提交 ————————————————————————————

    def _submit(self, _event: object = None) -> str:
        """回车/点按钮：把中文交给用例，结果回来后再画到输出区。"""
        text = self.input_text()
        if not text:
            self._set_output(InputText.EMPTY, muted=True)
            self._focus_input()
            return "break"

        self._request_id += 1
        request_id = self._request_id
        self._set_output(InputText.PENDING, muted=True)

        def done(outcome: TranslationOutcome) -> None:
            if request_id != self._request_id:
                return  # 过期结果：用户已经又提交了一次
            self._render(outcome)

        self._on_submit(text, done)
        return "break"

    def _render(self, outcome: TranslationOutcome) -> None:
        """把用例结果画到输出区（主线程）。"""
        if outcome.ok and outcome.result is not None:
            text = outcome.result.card_text
            if outcome.truncated:
                text = f"{text}\n（{InputText.TRUNCATED.format(limit=self._max_length)}）"
            self._set_output(text)
        elif outcome.error_message:
            self._set_output(outcome.error_message)
        else:
            self._set_output(InputText.EMPTY, muted=True)
        # 翻译完成 → 交还键盘焦点：于是"再按其他键"关闭浮层，而且按键会送到原来的窗口
        self._release_focus()

    # ———————————————————————————— 内部：焦点 / 关闭 ————————————————————————————

    def _focus_input(self, *, select_all: bool = False) -> None:
        """把键盘焦点放到输入区，并进入"正在输入"状态。"""
        window, widget = self._window, self._input
        if window is None or widget is None:
            return
        try:
            window.focus_force()
        except tk.TclError:
            pass
        # overrideredirect 的窗口在 Windows 上常常拿不到键盘焦点，仍需 Win32 抢一次前台
        try:
            self._window_activator.force_foreground(int(window.winfo_id()))
        except Exception:
            pass
        try:
            widget.focus_set()
        except tk.TclError:
            pass
        self._accepting_input = True
        if select_all:
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "end-1c")

    def _release_focus(self) -> None:
        """交还键盘焦点（并把"正在输入"状态置回）。"""
        self._accepting_input = False
        previous = self._previous_foreground
        if previous:
            try:
                self._window_activator.force_foreground(int(previous))
            except Exception:
                pass

    def _arm_dismiss_watcher(self) -> None:
        self._input_watcher.stop()
        self._input_watcher.start(self._on_any_input)

    def _on_any_input(self) -> None:
        """输入监听线程的回调：决定"这次输入"是继续输入还是关闭浮层。

        - 正在输入（焦点在框内）→ 是打字，什么都不做；
        - 鼠标落在框内 → **下一次输入**：不关闭，把焦点放回输入框；
        - 其余（框外按键 / 框外点击）→ 关闭。
        """
        if self._bounds is None:
            return
        if self._accepting_input:
            return
        if self._pointer_inside():
            self._marshal(lambda: self._focus_input(select_all=True))
            return
        self._marshal(self.hide)

    def _pointer_inside(self) -> bool:
        bounds = self._bounds
        if bounds is None:
            return False
        return is_inside(bounds, self._pointer.position())

    def _safe_foreground(self) -> int:
        try:
            return int(self._window_activator.foreground())
        except Exception:
            return 0

    def _on_escape(self, _event: object = None) -> str:
        self.hide()
        return "break"

    def _on_return(self, event: tk.Event) -> str:
        """Enter 提交；Shift+Enter 换行。"""
        if getattr(event, "state", 0) & 0x0001:  # Shift
            widget = self._input
            if widget is not None:
                widget.insert("insert", "\n")
            return "break"
        return self._submit()

    # ———————————————————————————— 内部：Tk 构建 ————————————————————————————

    def _build(self) -> None:
        top = tk.Toplevel(self._root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", FLOAT_ALPHA)
        top.configure(bg=UI_FLOAT_BG, highlightbackground=FLOAT_BORDER_COLOR, highlightthickness=1)
        top.bind("<Escape>", self._on_escape)

        body = tk.Frame(top, bg=UI_FLOAT_BG, padx=14, pady=12)
        body.pack(fill="both", expand=True)

        floating_label(body, InputText.TITLE, font=ui_font(10, weight="bold")).pack(anchor="w")

        self._input = self._text_widget(body, INPUT_LINES)
        self._input.pack(fill="both", expand=True, pady=(6, 8))
        self._input.bind("<Return>", self._on_return)
        self._input.bind("<Escape>", self._on_escape)

        separator = tk.Frame(body, bg=FLOAT_BORDER_COLOR, height=1)
        separator.pack(fill="x")

        self._output = self._text_widget(body, OUTPUT_LINES, readonly=True)
        self._output.pack(fill="both", expand=True, pady=(8, 8))

        bottom = tk.Frame(body, bg=UI_FLOAT_BG)
        bottom.pack(fill="x")
        floating_label(bottom, InputText.HINT, font=ui_font(8)).pack(side="left")
        small_button(bottom, command=self.hide, text=InputText.CLOSE_BUTTON).pack(side="right")
        small_button(bottom, command=self._submit, text=InputText.TRANSLATE_BUTTON).pack(
            side="right", padx=(0, 8)
        )

        self._window = top
        self._set_output(InputText.OUTPUT_PLACEHOLDER, muted=True)

    def _text_widget(self, master: tk.Misc, lines: int, *, readonly: bool = False) -> tk.Text:
        widget = tk.Text(
            master,
            height=lines,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=6,
            bg=FLOAT_BORDER_COLOR,
            fg=UI_FLOAT_FG,
            insertbackground=UI_FLOAT_FG,
            selectbackground=UI_FLOAT_BTN,
            selectforeground=UI_FLOAT_FG,
            font=ui_font(10),
        )
        if readonly:
            widget.configure(state="disabled")
        return widget

    def _set_output(self, text: str, *, muted: bool = False) -> None:
        widget = self._output
        if widget is None:
            return
        widget.configure(state="normal", fg=UI_FLOAT_MUTED if muted else UI_FLOAT_FG)
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


__all__ = ["BOX_HEIGHT", "BOX_WIDTH", "FLOAT_ALPHA", "SubmitCallback", "OverlayInputBox"]
