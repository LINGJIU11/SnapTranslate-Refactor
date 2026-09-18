"""起子进程时"绝不弹出窗口"的统一参数。

**为什么必须有这个模块**：打包成窗口程序（PyInstaller ``console=False``）之后，
进程自己**没有控制台**；此时任何控制台子程序（``powershell.exe`` / ``cmd.exe`` /
``tesseract.exe`` …）被拉起时，Windows 都会给它**新分配一个控制台窗口**——
用户看到的就是"翻译一下闪一个黑框"。源码运行时因为父进程有控制台，子进程直接继承，
反而不容易发现（这就是 KNOWN_ISSUES.md §八 N3 记的那个"第一版打包"问题）。

两道保险一起上：

1. ``CREATE_NO_WINDOW``（0x08000000）：不分配控制台；
2. ``STARTUPINFO`` + ``STARTF_USESHOWWINDOW`` + ``SW_HIDE``：即使被分配了也隐藏。

所有起子进程的地方**都要走本模块**（``tests/test_no_window.py`` 会静态检查这一点）。
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Sequence

#: ``CREATE_NO_WINDOW``：进程不分配控制台（XP 时代没有，所以按属性取 + 兜底常量）
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
#: 启动信息里"显示窗口"标志与"隐藏"取值
STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
SW_HIDE = getattr(subprocess, "SW_HIDE", 0)


def hidden_kwargs() -> dict[str, Any]:
    """可直接展开进 ``subprocess`` 调用的"不弹窗"参数（非 Windows 返回空字典）。"""
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = SW_HIDE
    return {"creationflags": CREATE_NO_WINDOW, "startupinfo": startupinfo}


def run_hidden(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """``subprocess.run`` + 不弹窗参数（调用方可用同名参数覆盖）。"""
    params = {**hidden_kwargs(), **kwargs}
    return subprocess.run(list(command), **params)


def popen_hidden(command: Sequence[str], **kwargs: Any) -> subprocess.Popen:
    """``subprocess.Popen`` + 不弹窗参数（调用方可用同名参数覆盖）。"""
    params = {**hidden_kwargs(), **kwargs}
    return subprocess.Popen(list(command), **params)


__all__ = [
    "CREATE_NO_WINDOW",
    "STARTF_USESHOWWINDOW",
    "SW_HIDE",
    "hidden_kwargs",
    "popen_hidden",
    "run_hidden",
]
