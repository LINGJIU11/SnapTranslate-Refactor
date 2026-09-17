"""domain 层：领域模型、领域服务与端口（Protocol）。

**零 IO、零框架依赖**：不 import config / application / infrastructure / presentation，
只用标准库与 ``domain.*``（见 ARCHITECTURE.md §1 依赖方向表）。
"""

from __future__ import annotations
