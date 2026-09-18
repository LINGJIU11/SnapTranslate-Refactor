"""追加式日志文件适配器（实现 :class:`~snaptranslate.domain.ports.log_sink.LogSink`）。

为什么需要它：原版（以及重构初期）的日志都是 ``print`` 到控制台。打包成
``--noconsole`` 的窗口程序后没有控制台，``print`` 会直接丢掉甚至报错，
用户也就看不到"取词失败：Ctrl+C 未生效"这类关键排查信息了。

写入策略刻意保持"笨但可靠"：

- **追加**（不轮转、不截断），一行一条，UTF-8；
- 多线程安全（翻译 worker / 取词 worker 都会写）；
- **写失败静默**——日志永远不该把业务拖垮；
- 目录不存在时自动创建（打包后数据目录可能还没有）。
"""

from __future__ import annotations

import os
import sys
import threading


class AppendOnlyLog:
    """:class:`LogSink` 的文件实现（可选同时回显到控制台）。"""

    def __init__(self, path: str, *, echo: bool = True) -> None:
        self.path = path
        self._echo = echo
        self._lock = threading.Lock()
        self._prepared = False

    def write(self, line: str) -> None:
        text = line if line.endswith("\n") else line + "\n"
        with self._lock:
            if self._echo:
                self._echo_to_console(text)
            try:
                self._ensure_ready()
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                # 日志写失败不打断业务流程（磁盘满 / 无权限 / 路径被删）
                pass

    def clear(self) -> None:
        """清空日志（界面"清空记录"时同步清掉文件，保持两边一致）。"""
        with self._lock:
            try:
                self._ensure_ready()
                with open(self.path, "w", encoding="utf-8"):
                    pass
            except OSError:
                pass

    # —— 内部 ——

    def _ensure_ready(self) -> None:
        if self._prepared:
            return
        parent = os.path.dirname(os.path.abspath(self.path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._prepared = True

    @staticmethod
    def _echo_to_console(text: str) -> None:
        """回显到控制台；打包成窗口程序后 ``sys.stdout`` 可能是 None，直接跳过。"""
        stream = sys.stdout
        if stream is None:
            return
        try:
            stream.write(text)
            stream.flush()
        except (OSError, ValueError, AttributeError):
            pass


__all__ = ["AppendOnlyLog"]
