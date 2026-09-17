"""兼容入口：`python entrypoints/set.py`（原 `python set.py` / `reset_vocab_scores.py`）。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")))

from snaptranslate.bootstrap.wiring import run_admin_app  # noqa: E402

if __name__ == "__main__":
    run_admin_app()
