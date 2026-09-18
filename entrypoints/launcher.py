"""兼容入口：``python entrypoints/launcher.py [--app=...]``。

打包成 exe 后不需要这个文件（exe 自己就是入口），保留它是为了源码运行时
启动器能用同一条命令行拉起子窗口（见 ``bootstrap/launcher.child_command_prefix``）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")))

from snaptranslate.bootstrap.launcher import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
