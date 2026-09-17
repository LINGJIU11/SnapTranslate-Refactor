"""兼容入口：`streamlit run entrypoints/vocab_review_web.py`（原 `streamlit run vocab_review_web.py`）。"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")))

from snaptranslate.bootstrap.streamlit_entry import main  # noqa: E402

if __name__ == "__main__":
    main()
