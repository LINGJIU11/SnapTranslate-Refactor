"""Web 包的 exe 入口（PyInstaller 用它当 ``Analysis`` 的第一个脚本）。

只做一件事：把命令行交给 :func:`snaptranslate.bootstrap.web_launcher.main`。
"""

from __future__ import annotations

import sys

from snaptranslate.bootstrap.web_launcher import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
