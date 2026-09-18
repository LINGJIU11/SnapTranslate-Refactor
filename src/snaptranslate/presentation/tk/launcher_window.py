"""启动器控制台窗口（**新增功能**）。

它是"一个入口管三个窗口"的落点：

- 三个按钮分别启动/唤起 划词翻译、生词复习、词表管理（已开则**唤到前台**，不会开出第二个）；
- 一行状态显示每个子窗口"运行中 / 未运行"；
- 勾选"关闭窗口时最小化到托盘常驻"后，关窗只是隐藏，托盘图标继续在；
- 托盘菜单同样能切换这三个窗口，双击图标回到本窗口；
- "退出"会一并结束由本启动器拉起的子进程（否则划词窗口的热键监听会变成孤儿进程）。

表示层只认识 :class:`~snaptranslate.domain.ports.app_launcher.AppLauncher` 与
:class:`~snaptranslate.domain.ports.tray.TrayIcon` 两个端口，不认识 ``subprocess`` 与 Win32。
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

from snaptranslate.application.deps import LauncherAppDeps
from snaptranslate.config import theme
from snaptranslate.presentation.texts import LauncherText
from snaptranslate.presentation.tk.ui_kit import (
    WINDOW_BG,
    card_frame,
    ghost_button,
    primary_button,
    ui_font,
)

#: 窗口几何
WINDOW_GEOMETRY = "520x420"
#: 子窗口状态刷新间隔（毫秒）
REFRESH_MS = 1200


class LauncherApp:
    """控制台窗口；对外接口只有 :meth:`run`。"""

    def __init__(self, deps: LauncherAppDeps) -> None:
        self.deps = deps
        self.root = tk.Tk()
        self.root.title(LauncherText.TITLE)
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(440, 360)
        self.root.configure(bg=WINDOW_BG)

        self.stay_var = tk.BooleanVar(master=self.root, value=True)
        self.status_var = tk.StringVar(master=self.root, value="")
        self._status_vars: dict[str, tk.StringVar] = {}
        self._tray_ready = False
        self._closing = False

        self._build_ui()
        self._start_tray()
        self._refresh()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ———————————————————————————— 对外 ————————————————————————————

    def run(self) -> None:
        self.root.mainloop()

    # ———————————————————————————— 界面 ————————————————————————————

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=WINDOW_BG, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer, text=LauncherText.TITLE, bg=WINDOW_BG, fg=theme.UI_TEXT, font=ui_font(14, weight="bold")
        ).pack(anchor="w")
        tk.Label(
            outer,
            text=LauncherText.SUBTITLE,
            bg=WINDOW_BG,
            fg=theme.UI_TEXT_MUTED,
            font=ui_font(9),
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        card = card_frame(outer, padx=12, pady=10)
        card.pack(fill="x")
        for key, label, hint in LauncherText.APPS:
            row = tk.Frame(card, bg=theme.UI_CARD)
            row.pack(fill="x", pady=4)
            primary_button(row, command=lambda k=key: self._open(k), text=label).pack(side="left")
            state_var = tk.StringVar(master=self.root, value=LauncherText.STOPPED)
            self._status_vars[key] = state_var
            tk.Label(
                row, textvariable=state_var, bg=theme.UI_CARD, fg=theme.UI_TEXT_MUTED, font=ui_font(9)
            ).pack(side="left", padx=(10, 0))
            tk.Label(
                row, text=hint, bg=theme.UI_CARD, fg=theme.UI_TEXT_MUTED, font=ui_font(8)
            ).pack(side="left", padx=(8, 0))

        tk.Checkbutton(
            outer,
            text=LauncherText.STAY_IN_TRAY,
            variable=self.stay_var,
            bg=WINDOW_BG,
            fg=theme.UI_TEXT,
            activebackground=WINDOW_BG,
            activeforeground=theme.UI_TEXT,
            selectcolor=theme.UI_CHIP,
            font=ui_font(9),
        ).pack(anchor="w", pady=(10, 2))

        tk.Label(
            outer,
            text=LauncherText.DATA_DIR_LINE.format(path=self.deps.data_dir),
            bg=WINDOW_BG,
            fg=theme.UI_TEXT_MUTED,
            font=ui_font(8),
            wraplength=460,
            justify="left",
        ).pack(anchor="w")
        tk.Label(
            outer,
            text=f"划词热键：{self.deps.hotkey_label}",
            bg=WINDOW_BG,
            fg=theme.UI_TEXT_MUTED,
            font=ui_font(8),
        ).pack(anchor="w")

        tk.Label(
            outer, textvariable=self.status_var, bg=WINDOW_BG, fg=theme.UI_ACCENT, font=ui_font(9)
        ).pack(anchor="w", pady=(8, 0))

        actions = tk.Frame(outer, bg=WINDOW_BG)
        actions.pack(fill="x", pady=(10, 0))
        ghost_button(actions, command=self._open_data_dir, text=LauncherText.OPEN_DATA_DIR).pack(side="left")
        ghost_button(actions, command=self.quit, text=LauncherText.QUIT).pack(side="right")

    # ———————————————————————————— 托盘 ————————————————————————————

    def _tray_items(self):
        from snaptranslate.domain.ports.tray import TrayMenuItem

        items = [TrayMenuItem("panel", LauncherText.TRAY_PANEL, checked=True)]
        for key, label, _hint in LauncherText.APPS:
            items.append(TrayMenuItem(key, label, separator_before=(key == "translate")))
        items.append(TrayMenuItem("quit", LauncherText.TRAY_QUIT, separator_before=True))
        return items

    def _start_tray(self) -> None:
        self._tray_ready = bool(
            self.deps.tray.start(
                LauncherText.TRAY_TOOLTIP,
                self.deps.icon_path,
                self._tray_items(),
                self._on_tray_select,
            )
        )
        self.status_var.set(LauncherText.TRAY_HINT if self._tray_ready else LauncherText.TRAY_UNAVAILABLE)

    def _on_tray_select(self, key: str) -> None:
        """托盘线程的回调 → 切回主线程再动 Tk。"""
        self.root.after(0, lambda: self._handle_tray(key))

    def _handle_tray(self, key: str) -> None:
        if key == "quit":
            self.quit()
            return
        if key == "panel":
            self._show_panel()
            return
        self._open(key)

    # ———————————————————————————— 行为 ————————————————————————————

    def _open(self, key: str) -> None:
        was_running = self.deps.launcher.is_running(key)
        self.deps.launcher.open_or_focus(key)
        label = dict((k, v) for k, v, _h in LauncherText.APPS).get(key, key)
        template = LauncherText.FOCUSED if was_running else LauncherText.LAUNCHED
        self.status_var.set(template.format(label=label))
        self._refresh()

    def _refresh(self) -> None:
        if self._closing:
            return
        running = set(self.deps.launcher.running_keys())
        for key, _label, _hint in LauncherText.APPS:
            var = self._status_vars.get(key)
            if var is not None:
                var.set(LauncherText.RUNNING if key in running else LauncherText.STOPPED)
        self.root.after(REFRESH_MS, self._refresh)

    def _show_panel(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def _open_data_dir(self) -> None:
        """在资源管理器里打开数据目录（词表/设置/备份/日志都在这里）。

        用系统外壳打开文件夹（``os.startfile``），不起任何子进程——本项目只在 Windows 上跑。
        """
        try:
            os.startfile(self.deps.data_dir)  # noqa: S606 - 打开自己程序的数据目录
        except OSError:
            self.status_var.set(f"打开失败：{self.deps.data_dir}")

    def _on_close(self) -> None:
        """关窗：托盘可用且勾了"常驻"就只隐藏，否则真退出。"""
        if self._tray_ready and self.stay_var.get():
            self.root.withdraw()
            return
        self.quit()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            self.deps.tray.stop()
        except Exception:
            pass
        try:
            self.deps.launcher.terminate_all()
        except Exception:
            pass
        self.root.destroy()


__all__ = ["REFRESH_MS", "WINDOW_GEOMETRY", "LauncherApp"]
