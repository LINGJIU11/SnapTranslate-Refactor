"""面向入口的装配函数（原版 4 个脚本的 ``main()`` 等价物）。

表示层模块在此**延迟导入**，这样 CLI 的其它子命令（例如只跑网页版复习）不会
因为 tkinter 不可用而失败。
"""

from __future__ import annotations

import sys
from pathlib import Path

from snaptranslate.bootstrap.container import Container, DataPaths


def _container(data_dir: str | None = None) -> Container:
    if data_dir:
        return Container(DataPaths.under(data_dir))
    return Container()


def run_translate_app(data_dir: str | None = None) -> None:
    """划词翻译主窗口（``python main.py``）。"""
    from snaptranslate.presentation.tk.translate_window import TranslateApp

    TranslateApp(_container(data_dir).translate_app_deps()).run()


def run_review_app(data_dir: str | None = None) -> None:
    """生词复习桌面端（``python vocab_review.py``）。"""
    from snaptranslate.presentation.tk.review_window import ReviewApp

    ReviewApp(_container(data_dir).review_app_deps()).run()


def run_admin_app(data_dir: str | None = None) -> None:
    """词表后台管理（``python set.py``）。"""
    from snaptranslate.presentation.tk.admin_window import AdminApp

    AdminApp(_container(data_dir).admin_app_deps()).run()


def run_review_web(data_dir: str | None = None) -> None:
    """生词复习 Web 端。

    在 ``streamlit run`` 环境下直接渲染页面；直接当普通命令执行时，
    自行拉起一个 streamlit 子进程指向 ``bootstrap/streamlit_entry.py``。
    """
    try:
        from streamlit.runtime import exists as runtime_exists
    except Exception:  # pragma: no cover - 未安装 streamlit
        raise SystemExit("未安装 streamlit，请先执行：pip install streamlit")

    if runtime_exists():
        from snaptranslate.presentation.web.streamlit_review import render_page

        render_page(_container(data_dir).web_review_deps())
        return

    entry = Path(__file__).with_name("streamlit_entry.py")
    command = [sys.executable, "-m", "streamlit", "run", str(entry)]
    if data_dir:
        command.extend(["--", "--data-dir", data_dir])
    # 走"不弹窗"参数：窗口程序（打包后）里起控制台子进程会闪一个黑框
    from snaptranslate.infrastructure.process.no_window import run_hidden

    raise SystemExit(run_hidden(command).returncode)
