"""兼容入口：`python entrypoints/main.py` 等价于原版的 `python main.py`。

不需要 ``pip install``：自动把 ``src`` 加入 ``sys.path``。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")))

from snaptranslate.bootstrap.wiring import run_translate_app  # noqa: E402

if __name__ == "__main__":
    run_translate_app()
