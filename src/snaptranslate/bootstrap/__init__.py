"""bootstrap 层：组合根。

唯一允许 import 所有层的地方；负责把配置、适配器与用例装配起来交给表示层
（见 ARCHITECTURE.md §2.6）。
"""

from __future__ import annotations
