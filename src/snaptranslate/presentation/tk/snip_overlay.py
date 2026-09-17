"""截图遮罩与框选（OCR 取词区域）。

职责：全屏半透明遮罩 + ``crosshair`` 画布，拖拽出矩形后回调 :class:`BBox`。
对应原版：

- ``_snip_cancel``                 ``main.py:1265-1277``
- ``_begin_screen_snip``           ``main.py:1279-1390``
- ``_finalize_snip_overlay``       ``main.py:1392-1408``
- ``_win32_activate_snip_overlay`` ``main.py:1242-1263``

与原版一致的关键点：

1. **必须先 ``-fullscreen`` 再 ``overrideredirect``**（原注释：反了会报
   ``TclError: can't set fullscreen ... override-redirect flag is set``，``main.py:1291``）；
2. ``<Map>`` 事件里再设一次 ``alpha``（Win32 合成器会"吃掉"过早设置的透明度）；
3. 松手时宽或高 < 6 像素视为误触，取消（``BBox.is_valid_snip()``）；
4. ESC 取消；
5. 拖拽/松手用 ``event.x_root/y_root`` 与 ``winfo_rootx/rooty`` 换算（原版未处理多屏负坐标，
   此处原样保留）；
6. Win32 抢焦点**不再自己写 ctypes**，改为调用 ``deps.window_activator.force_foreground(hwnd)``。
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from snaptranslate.config.theme import (
    FONT_FAMILY,
    SNIP_HINT_FG,
    SNIP_INFO_FG,
    SNIP_OVERLAY_ALPHA,
    SNIP_OVERLAY_CANVAS_BG,
)
from snaptranslate.domain.models.geometry import BBox
from snaptranslate.domain.ports.window import WindowActivator
from snaptranslate.presentation.texts import WindowText

#: 原 ``main.py:1335`` / ``main.py:1322``
RECT_OUTLINE = "#38bdf8"
HINT_POS = (18, 20)
INFO_POS = (18, 48)
HINT_FONT_SIZE = 12
INFO_FONT_SIZE = 10
RECT_WIDTH = 3


class SnipOverlay:
    """截图遮罩控件。

    :param root: 主窗口。
    :param window_activator: 抢前台端口（原 ``_win32_force_foreground_hwnd``）。
    :param set_status: 设置主窗口状态栏文案（原 ``status_var.set``）。
    :param on_bbox: 松手且区域合法时的回调。
    """

    def __init__(
        self,
        root: tk.Tk,
        *,
        window_activator: WindowActivator,
        set_status: Callable[[str], None],
        on_bbox: Callable[[BBox], None],
    ) -> None:
        self._root = root
        self._window_activator = window_activator
        self._set_status = set_status
        self._on_bbox = on_bbox

        self._overlay: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._start: tuple[int, int] | None = None
        self._rect_id: int | None = None
        self._info_id: int | None = None
        #: 原 ``_snip_busy``：遮罩存在期间为 True，阻止重复开图
        self.busy = False

    # ———————————————————————— 对外入口 ————————————————————————

    def begin(self) -> None:
        """原 ``_begin_screen_snip``（必须从主线程调用）。"""
        if self.busy:
            return
        self.busy = True
        self._set_status(WindowText.SNIP_HINT_SHORT)

        overlay: tk.Toplevel | None = None
        try:
            overlay = tk.Toplevel(self._root)
            self._overlay = overlay
            # Win32：必须先全屏再 overrideredirect，否则会 TclError（原版注释）
            overlay.attributes("-fullscreen", True)
            overlay.overrideredirect(True)
            overlay.configure(bg=SNIP_OVERLAY_CANVAS_BG)

            canvas = tk.Canvas(
                overlay,
                bg=SNIP_OVERLAY_CANVAS_BG,
                highlightthickness=0,
                cursor="crosshair",
            )
            canvas.pack(fill="both", expand=True)
            canvas.create_text(
                HINT_POS[0],
                HINT_POS[1],
                text=WindowText.SNIP_CANVAS_HINT,
                fill=SNIP_HINT_FG,
                anchor="w",
                font=(FONT_FAMILY, HINT_FONT_SIZE, "bold"),
            )
            overlay.bind("<Map>", lambda _event=None: self._apply_alpha(overlay))

            self._canvas = canvas
            self._start = None
            self._rect_id = None
            self._info_id = canvas.create_text(
                INFO_POS[0],
                INFO_POS[1],
                text="",
                fill=SNIP_INFO_FG,
                anchor="w",
                font=(FONT_FAMILY, INFO_FONT_SIZE, "bold"),
            )

            canvas.bind("<ButtonPress-1>", self._on_press)
            canvas.bind("<B1-Motion>", self._on_drag)
            canvas.bind("<ButtonRelease-1>", self._on_release)
            overlay.bind("<Escape>", lambda _event: self.cancel(WindowText.SNIP_CANCELLED))
            self._finalize(overlay)
            self._activate(overlay)
        except Exception as exc:  # noqa: BLE001 - 原版把开图失败提示写在状态栏
            if overlay is not None:
                try:
                    overlay.destroy()
                except Exception:
                    pass
            self._overlay = None
            self._canvas = None
            self._start = None
            self._rect_id = None
            self._info_id = None
            self.busy = False
            self._set_status(WindowText.SNIP_FAILED.format(error=exc))

    def cancel(self, message: str | None = None) -> None:
        """原 ``_snip_cancel``：销毁遮罩并可选地在状态栏提示一句。"""
        if self._overlay is not None:
            try:
                self._overlay.destroy()
            except Exception:
                pass
        self._overlay = None
        self._canvas = None
        self._start = None
        self._rect_id = None
        self.busy = False
        if message:
            self._set_status(message)

    # ———————————————————————— 鼠标事件 ————————————————————————

    def _on_press(self, event: tk.Event) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        self._start = (event.x_root, event.y_root)
        if self._rect_id is not None:
            canvas.delete(self._rect_id)
        self._rect_id = canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline=RECT_OUTLINE,
            width=RECT_WIDTH,
            fill=RECT_OUTLINE,
            stipple="gray50",
        )

    def _on_drag(self, event: tk.Event) -> None:
        canvas = self._canvas
        overlay = self._overlay
        if canvas is None or overlay is None or self._start is None or self._rect_id is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x_root, event.y_root
        canvas.coords(
            self._rect_id,
            x0 - overlay.winfo_rootx(),
            y0 - overlay.winfo_rooty(),
            event.x,
            event.y,
        )
        if self._info_id is not None:
            canvas.itemconfigure(
                self._info_id,
                text=WindowText.SNIP_SIZE.format(width=abs(x1 - x0), height=abs(y1 - y0)),
            )

    def _on_release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        x0, y0 = self._start
        x1, y1 = event.x_root, event.y_root
        bbox = BBox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if not bbox.is_valid_snip():
            self.cancel(WindowText.SNIP_TOO_SMALL)
            return
        self.cancel(WindowText.SNIP_OCR_RUNNING)
        self._on_bbox(bbox)

    # ———————————————————————— 视觉与激活 ————————————————————————

    @staticmethod
    def _apply_alpha(overlay: tk.Toplevel) -> None:
        try:
            overlay.attributes("-alpha", SNIP_OVERLAY_ALPHA)
        except tk.TclError:
            pass

    def _finalize(self, overlay: tk.Toplevel) -> None:
        """原 ``_finalize_snip_overlay``：置顶 + 映射后重复设置透明度。"""
        overlay.update_idletasks()
        try:
            overlay.attributes("-topmost", True)
        except tk.TclError:
            pass
        for _ in range(2):
            try:
                overlay.attributes("-alpha", SNIP_OVERLAY_ALPHA)
            except tk.TclError:
                break
            overlay.update_idletasks()
        try:
            overlay.lift(self._root)
        except tk.TclError:
            overlay.lift()

    def _activate(self, overlay: tk.Toplevel) -> None:
        """原 ``_win32_activate_snip_overlay``：把主窗与遮罩一并抢到前台。"""
        try:
            self._root.deiconify()
        except tk.TclError:
            pass
        self._root.update_idletasks()
        overlay.update_idletasks()
        for widget in (self._root, overlay):
            try:
                self._window_activator.force_foreground(int(widget.winfo_id()))
            except Exception:
                pass
        try:
            overlay.focus_force()
        except tk.TclError:
            pass
