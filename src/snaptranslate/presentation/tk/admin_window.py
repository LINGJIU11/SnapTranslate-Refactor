"""词表后台管理窗口（对应原版 ``set.py`` 全文，197 行）。

职责：把原 ``AdminApp`` 的朴素 Tk 布局与三个动作（刷新状态 / 重置评分 / 清理备份）
原样搬过来；业务逻辑全部交给 ``deps.admin`` 用例，本文件只做取值、弹窗与状态栏文案。

原版行号对照：
- 窗口与变量 ``set.py:80-95``
- 布局 ``set.py:97-133``
- ``refresh_status`` ``set.py:135-158``
- ``on_reset_scores`` ``set.py:160-172``
- ``on_cleanup_backups`` ``set.py:174-186``
- ``run`` ``set.py:188-189``

行为等价说明：原版这个窗口**没有**用主题色（只有状态栏一个 ``fg="#334155"``），
重构后保持一致；文案全部取自 :class:`~snaptranslate.presentation.texts.AdminText`。
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from snaptranslate.application.deps import AdminAppDeps
from snaptranslate.domain.errors import VocabularyFileMissingError
from snaptranslate.presentation.texts import AdminText

#: 原 ``set.py:133`` 状态栏前景色（原版未纳入主题常量，这里就地保留）
_STATUS_FG = "#334155"


class AdminApp:
    """词表后台管理界面（原 ``set.py:AdminApp``）。"""

    def __init__(self, deps: AdminAppDeps) -> None:
        self._deps = deps

        self.root = tk.Tk()
        self.root.title(AdminText.TITLE)
        self.root.geometry("760x520")
        self.root.minsize(680, 460)
        # Tk 变量必须在 root 创建之后绑定（原版同一顺序，见 set.py:81-92）
        self.vocab_path_var = tk.StringVar(master=self.root, value=deps.vocab_path)
        self.backup_dir_var = tk.StringVar(master=self.root, value=deps.backup_dir)
        self.total_var = tk.StringVar(master=self.root, value="-")
        self.with_example_var = tk.StringVar(master=self.root, value="-")
        self.pending_var = tk.StringVar(master=self.root, value="-")
        self.backup_count_var = tk.StringVar(master=self.root, value="-")
        self.latest_backup_var = tk.StringVar(master=self.root, value=AdminText.NONE)
        self.status_var = tk.StringVar(master=self.root, value=AdminText.READY)

        self._build_ui()
        self.refresh_status()

    # —————————————————————————— 界面 ——————————————————————————

    def _build_ui(self) -> None:
        f_title = tkfont.Font(family="Microsoft YaHei UI", size=18, weight="bold")
        f_label = tkfont.Font(family="Microsoft YaHei UI", size=10)
        f_value = tkfont.Font(family="Consolas", size=10)

        outer = tk.Frame(self.root, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text=AdminText.TITLE, font=f_title).pack(anchor="w", pady=(0, 10))

        p1 = tk.Frame(outer)
        p1.pack(fill="x", pady=(0, 6))
        tk.Label(p1, text=AdminText.VOCAB_PATH, font=f_label, width=10, anchor="w").pack(side="left")
        tk.Entry(p1, textvariable=self.vocab_path_var, font=f_value).pack(side="left", fill="x", expand=True)

        p2 = tk.Frame(outer)
        p2.pack(fill="x", pady=(0, 10))
        tk.Label(p2, text=AdminText.BACKUP_DIR, font=f_label, width=10, anchor="w").pack(side="left")
        tk.Entry(p2, textvariable=self.backup_dir_var, font=f_value).pack(side="left", fill="x", expand=True)

        status_box = tk.LabelFrame(outer, text=AdminText.STATUS_BOX)
        status_box.pack(fill="x", pady=(0, 12))
        tk.Label(status_box, textvariable=self.total_var, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        tk.Label(status_box, textvariable=self.with_example_var, anchor="w").pack(fill="x", padx=10)
        tk.Label(status_box, textvariable=self.pending_var, anchor="w").pack(fill="x", padx=10)
        tk.Label(status_box, textvariable=self.backup_count_var, anchor="w").pack(fill="x", padx=10)
        tk.Label(
            status_box,
            textvariable=self.latest_backup_var,
            anchor="w",
            wraplength=700,
            justify="left",
        ).pack(fill="x", padx=10, pady=(0, 8))

        btn_row = tk.Frame(outer)
        btn_row.pack(fill="x", pady=(0, 8))
        tk.Button(btn_row, text=AdminText.REFRESH, command=self.refresh_status).pack(side="left")
        tk.Button(btn_row, text=AdminText.RESET_SCORES, command=self.on_reset_scores).pack(side="left", padx=(8, 0))
        tk.Button(btn_row, text=AdminText.CLEANUP_BACKUPS, command=self.on_cleanup_backups).pack(
            side="left", padx=(8, 0)
        )

        tk.Label(outer, textvariable=self.status_var, anchor="w", fg=_STATUS_FG).pack(fill="x")

    # —————————————————————————— 动作 ——————————————————————————

    def refresh_status(self) -> None:
        """原 ``set.py:135-158``：词表读取失败也要照常展示备份信息。"""
        status = self._deps.admin.status(self.vocab_path_var.get().strip(), self.backup_dir_var.get().strip())

        if status.read_error is None:
            self.total_var.set(AdminText.TOTAL.format(value=status.total))
            self.with_example_var.set(AdminText.WITH_EXAMPLE.format(value=status.with_example))
            self.pending_var.set(AdminText.PENDING.format(value=status.pending))
        else:
            self.total_var.set(AdminText.TOTAL.format(value=AdminText.READ_FAILED))
            self.with_example_var.set(AdminText.WITH_EXAMPLE.format(value=AdminText.READ_FAILED))
            self.pending_var.set(AdminText.PENDING.format(value=AdminText.READ_FAILED))
            self.status_var.set(AdminText.READ_FAILED_STATUS.format(error=status.read_error))

        self.backup_count_var.set(AdminText.BACKUP_COUNT.format(value=status.backup_count))
        if status.latest_backup:
            self.latest_backup_var.set(AdminText.LATEST_BACKUP.format(value=os.path.basename(status.latest_backup)))
        else:
            self.latest_backup_var.set(AdminText.LATEST_BACKUP.format(value=AdminText.NONE))

    def on_reset_scores(self) -> None:
        """原 ``set.py:160-172``：先查文件存在性，再确认，最后执行。"""
        vocab_path = self.vocab_path_var.get().strip()
        if not os.path.isfile(vocab_path):
            messagebox.showerror(AdminText.ERROR_TITLE, AdminText.VOCAB_MISSING.format(path=vocab_path))
            return
        if not messagebox.askyesno(AdminText.RESET_CONFIRM_TITLE, AdminText.RESET_CONFIRM_BODY):
            return
        try:
            count = self._deps.admin.reset_scores(vocab_path)
        except VocabularyFileMissingError as exc:
            messagebox.showerror(AdminText.ERROR_TITLE, AdminText.VOCAB_MISSING.format(path=exc.path))
            return
        except Exception as exc:  # noqa: BLE001 - 原版就是"其它异常 → 失败弹窗"
            messagebox.showerror(AdminText.FAILED_TITLE, str(exc))
            return
        self.status_var.set(AdminText.RESET_DONE.format(count=count))
        self.refresh_status()

    def on_cleanup_backups(self) -> None:
        """原 ``set.py:174-186``。"""
        backup_dir = self.backup_dir_var.get().strip()
        if not messagebox.askyesno(AdminText.RESET_CONFIRM_TITLE, AdminText.CLEANUP_CONFIRM_BODY):
            return
        try:
            removed, keep = self._deps.admin.cleanup_backups(backup_dir)
        except Exception as exc:  # noqa: BLE001 - 原版同一处 except
            messagebox.showerror(AdminText.FAILED_TITLE, str(exc))
            return
        if keep:
            self.status_var.set(AdminText.CLEANUP_DONE.format(removed=removed, name=os.path.basename(keep)))
        else:
            self.status_var.set(AdminText.CLEANUP_NOTHING)
        self.refresh_status()

    # —————————————————————————— 启动 ——————————————————————————

    def run(self) -> None:
        """原 ``set.py:188-189``。"""
        self.root.mainloop()


__all__ = ["AdminApp"]
