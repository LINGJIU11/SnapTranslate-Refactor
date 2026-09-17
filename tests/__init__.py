"""单元测试包。

把 ``src`` 加入 ``sys.path``，使 ``python -m unittest discover -s tests`` 与
``pytest tests`` 都能直接跑，无需先 ``pip install -e .``。
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
